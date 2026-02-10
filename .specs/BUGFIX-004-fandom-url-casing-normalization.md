# Bugfix: Fandom URL Casing Normalization

## Bugfix ID: BUGFIX-004
**Priority:** P1 (High - causes data extraction failures)
**Estimated Effort:** 2-3 hours
**Dependencies:** FEAT-002, FEAT-003

---

## Context

### Current State
- Stage 1 generates Fandom URLs by converting station display names
- The conversion uses simple title casing: each word capitalized
- Fandom wiki URLs follow specific casing conventions that don't match simple title case
- When URLs don't match exactly, the scraper returns 404 errors
- This causes Stage 2 extraction to fail for affected stations

### Problem
1. **Case-sensitive URL mismatch**: Fandom wiki URLs have arbitrary casing
   - Example: "Gardens By The Bay MRT Station" (generated) vs "Gardens_by_the_Bay_MRT_Station" (actual)
   - The words "by", "the" are lowercase in actual URL but uppercase in generated URL

2. **Inconsistent article casing**: Fandom doesn't follow predictable rules
   - Some words are always lowercase (articles: a, an, the; prepositions: by, in, of, on)
   - But exceptions exist and aren't documented

3. **Silent failures**: 404 errors aren't immediately obvious during pipeline run
   - Stage 2 marks station as "failed" but error message is generic
   - Root cause (URL mismatch) is buried in logs

4. **Manual workaround required**: Currently requires manual URL mapping

### Examples of Mismatches

| Station Name | Generated URL | Actual Fandom URL | Match? |
|--------------|---------------|-------------------|---------|
| Gardens By The Bay | Gardens_By_The_Bay_MRT_Station | Gardens_by_the_Bay_MRT_Station | ❌ |
| MacPherson | MacPherson_MRT_Station | Macpherson_MRT_Station | ❌ |
| One-North | One-North_MRT_Station | One-north_MRT_Station | ❌ |
| Bukit Panjang | Bukit_Panjang_LRT_Station | Bukit_Panjang_LRT_Station | ✅ |
| Yishun | Yishun_MRT_Station | Yishun_MRT_Station | ✅ |

### Goal
Implement robust URL resolution that handles casing variations automatically, ensuring all station URLs resolve correctly regardless of casing mismatches.

---

## Requirements

### 1. Implement Case-Insensitive URL Resolution (src/pipelines/fandom_scraper.py)

Create a URL resolution strategy that tries multiple casing variations:

```python
import requests
from typing import Optional, List
from functools import lru_cache

class FandomScraper:
    def __init__(self, config: dict):
        self.base_url = "https://singapore-mrt-lines.fandom.com/wiki"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        # Cache for resolved URLs
        self._url_cache = {}
    
    def resolve_fandom_url(self, station_name: str) -> Optional[str]:
        """
        Resolve Fandom URL for a station, handling casing variations.
        
        Strategy:
        1. Try exact match first
        2. Try lowercase articles/prepositions
        3. Try all lowercase
        4. Try Fandom API search
        5. Cache successful resolution
        
        Returns: Resolved URL or None if not found
        """
        # Check cache first
        cache_key = station_name.lower().replace(' ', '_')
        if cache_key in self._url_cache:
            return self._url_cache[cache_key]
        
        # Generate candidate URLs
        candidates = self._generate_url_candidates(station_name)
        
        # Try each candidate
        for url in candidates:
            if self._url_exists(url):
                self._url_cache[cache_key] = url
                return url
        
        # Try Fandom API as fallback
        api_url = self._search_fandom_api(station_name)
        if api_url:
            self._url_cache[cache_key] = api_url
            return api_url
        
        return None
    
    def _generate_url_candidates(self, station_name: str) -> List[str]:
        """Generate possible URL variations for a station name."""
        candidates = []
        
        # Base name (remove MRT/LRT Station suffix for processing)
        base_name = station_name.replace(' MRT Station', '').replace(' LRT Station', '').replace(' Station', '')
        suffix = 'MRT_Station' if 'MRT' in station_name else 'LRT_Station' if 'LRT' in station_name else 'Station'
        
        # 1. Title case (current behavior)
        title_case = base_name.title().replace(' ', '_')
        candidates.append(f"{self.base_url}/{title_case}_{suffix}")
        
        # 2. Lowercase articles and prepositions
        words = base_name.split()
        lowercase_words = {'a', 'an', 'the', 'by', 'in', 'of', 'on', 'at', 'to', 'for', 'with', 'and', 'or'}
        processed_words = [
            word.lower() if word.lower() in lowercase_words else word.title()
            for word in words
        ]
        article_case = '_'.join(processed_words)
        candidates.append(f"{self.base_url}/{article_case}_{suffix}")
        
        # 3. All lowercase (Fandom sometimes uses this)
        all_lower = base_name.lower().replace(' ', '_')
        candidates.append(f"{self.base_url}/{all_lower}_{suffix}")
        
        # 4. Exact original (preserve input casing)
        exact = base_name.replace(' ', '_')
        candidates.append(f"{self.base_url}/{exact}_{suffix}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_candidates = []
        for url in candidates:
            if url not in seen:
                seen.add(url)
                unique_candidates.append(url)
        
        return unique_candidates
    
    def _url_exists(self, url: str) -> bool:
        """Check if URL returns 200 without downloading full content."""
        try:
            response = self.session.head(url, timeout=5, allow_redirects=True)
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def _search_fandom_api(self, station_name: str) -> Optional[str]:
        """
        Use Fandom API to search for station page.
        Fallback when direct URL guessing fails.
        """
        search_term = station_name.replace(' MRT Station', '').replace(' LRT Station', '')
        api_url = f"{self.base_url}/api.php?action=query&list=search&srsearch={search_term}&format=json"
        
        try:
            response = self.session.get(api_url, timeout=10)
            data = response.json()
            
            if 'query' in data and 'search' in data['query']:
                results = data['query']['search']
                if results:
                    # Take first result
                    page_title = results[0]['title']
                    return f"{self.base_url}/{page_title.replace(' ', '_')}"
        except Exception:
            pass
        
        return None
```

**Implementation Notes:**
- Use HTTP HEAD requests to check URL existence (faster than GET)
- Implement caching to avoid repeated URL resolution
- Cache should persist across pipeline runs (save to file)
- Handle both MRT and LRT stations
- Respect robots.txt and rate limits

### 2. Add URL Resolution Cache

Implement persistent caching for URL resolutions:

```python
import json
import os
from datetime import datetime, timedelta

class URLResolutionCache:
    """Persistent cache for Fandom URL resolutions."""
    
    def __init__(self, cache_file: str = ".url_cache.json"):
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self.max_age_days = 30  # Refresh cache monthly
    
    def _load_cache(self) -> dict:
        """Load cache from disk."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def save_cache(self):
        """Save cache to disk."""
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
    
    def get(self, station_name: str) -> Optional[str]:
        """Get cached URL if exists and not expired."""
        key = station_name.lower().replace(' ', '_')
        if key in self.cache:
            entry = self.cache[key]
            cached_date = datetime.fromisoformat(entry['timestamp'])
            if datetime.now() - cached_date < timedelta(days=self.max_age_days):
                return entry['url']
        return None
    
    def set(self, station_name: str, url: str):
        """Cache a URL resolution."""
        key = station_name.lower().replace(' ', '_')
        self.cache[key] = {
            'url': url,
            'timestamp': datetime.now().isoformat(),
            'station_name': station_name
        }
```

### 3. Update Stage 1 URL Generation

Modify Stage 1 to use the resolver instead of naive generation:

```python
class Stage1Ingestion:
    def __init__(self, config: dict):
        # ... existing init ...
        self.scraper = FandomScraper(config)
    
    def generate_fandom_url(self, station: Stage1Station) -> str:
        """
        Generate or resolve Fandom URL for a station.
        Uses resolver to handle casing variations.
        """
        # Try to resolve URL
        resolved_url = self.scraper.resolve_fandom_url(station.display_name)
        
        if resolved_url:
            logger.info(f"Resolved URL for {station.display_name}: {resolved_url}")
            return resolved_url
        else:
            # Fallback to generated URL (will likely fail but provides something)
            fallback = self._naive_url_generation(station.display_name)
            logger.warning(f"Could not resolve URL for {station.display_name}, using fallback: {fallback}")
            return fallback
    
    def _naive_url_generation(self, display_name: str) -> str:
        """Original naive URL generation as fallback."""
        # ... existing implementation ...
        pass
```

### 4. Add URL Validation Step

Add explicit URL validation in Stage 1:

```python
def validate_fandom_urls(self, stations: List[Stage1Station]) -> List[Stage1Station]:
    """
    Validate all Fandom URLs and report failures.
    Called after URL generation to catch issues early.
    """
    logger.section("Validating Fandom URLs")
    
    invalid_stations = []
    for station in stations:
        if not self.scraper.validate_url(station.fandom_url):
            invalid_stations.append(station)
            logger.warning(f"Invalid URL for {station.official_name}: {station.fandom_url}")
    
    if invalid_stations:
        logger.error(f"Found {len(invalid_stations)} stations with invalid Fandom URLs")
        # Option: raise error or continue with warnings
    
    return [s for s in stations if s not in invalid_stations]
```

### 5. Create URL Mapping Fallback

For stations that can't be auto-resolved, support manual mapping:

```yaml
# config/pipeline.yaml
url_mappings:
  # Manual overrides for stations with unusual URLs
  "Gardens By The Bay": "https://singapore-mrt-lines.fandom.com/wiki/Gardens_by_the_Bay_MRT_Station"
  "One-North": "https://singapore-mrt-lines.fandom.com/wiki/One-north_MRT_Station"
  "MacPherson": "https://singapore-mrt-lines.fandom.com/wiki/Macpherson_MRT_Station"
```

```python
def apply_manual_mappings(self, station: Stage1Station) -> str:
    """Apply manual URL mappings from config."""
    mappings = self.config.get('url_mappings', {})
    if station.display_name in mappings:
        logger.info(f"Using manual URL mapping for {station.display_name}")
        return mappings[station.display_name]
    return None
```

### 6. Update Error Reporting

Improve error messages when URL resolution fails:

```python
def fetch_page(self, url: str, station_name: str) -> Optional[str]:
    """Fetch HTML with better error reporting."""
    try:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.error(
                f"404 Error for {station_name}\n"
                f"  URL: {url}\n"
                f"  This usually means the URL casing is wrong.\n"
                f"  Check the actual Fandom page and add a manual mapping."
            )
        else:
            logger.error(f"HTTP {e.response.status_code} for {station_name}: {url}")
        return None
```

---

## Success Criteria

### Functional Requirements
- [ ] All stations resolve to valid Fandom URLs
- [ ] URL resolution handles at least these known problem cases:
  - Gardens By The Bay → Gardens_by_the_Bay_MRT_Station
  - One-North → One-north_MRT_Station
  - MacPherson → Macpherson_MRT_Station
- [ ] URL resolution is cached and persists across runs
- [ ] Failed resolutions are clearly logged with actionable error messages
- [ ] Manual URL mapping fallback works for edge cases

### Test Requirements
- [ ] Unit tests for URL candidate generation
- [ ] Unit tests for article/preposition lowercase handling
- [ ] Integration tests for all known problematic stations
- [ ] Test cache persistence
- [ ] Test manual mapping override

### Performance Requirements
- [ ] URL resolution completes in < 5 seconds per station (including retries)
- [ ] Cache hit reduces resolution time to < 100ms
- [ ] Parallel URL validation for batch processing (optional)

### Data Quality Requirements
- [ ] 100% of Stage 1 stations have valid Fandom URLs
- [ ] Stage 2 extraction success rate > 95% (currently likely much lower due to 404s)
- [ ] All URL mismatches are logged with station name and attempted URLs

### Documentation Requirements
- [ ] Document URL resolution algorithm
- [ ] Document manual mapping configuration
- [ ] Create troubleshooting guide for URL issues

---

## Files to Modify

1. `src/pipelines/fandom_scraper.py` - Add URL resolution logic
2. `src/pipelines/stage1_ingestion.py` - Use resolver, add validation
3. `config/pipeline.yaml` - Add manual URL mappings section
4. `src/utils/url_cache.py` - New file for persistent caching
5. `tests/test_fandom_scraper.py` - Add URL resolution tests

---

## Verification Steps

```bash
# Test URL resolution for problematic stations
python -c "
from src.pipelines.fandom_scraper import FandomScraper
scraper = FandomScraper({})

test_stations = [
    'Gardens By The Bay',
    'One-North',
    'MacPherson',
    'Yishun',
    'Bukit Panjang'
]

for station in test_stations:
    url = scraper.resolve_fandom_url(station)
    print(f'{station}: {\"✓\" if url else \"✗\"} {url}')
"

# Run full Stage 1 and verify no 404s
python scripts/run_stage1.py
cat outputs/latest/stage1_deterministic.json | jq '.stations[] | select(.fandom_url | contains(\"404\"))' | wc -l
# Expected: 0

# Check Stage 2 extraction success rate
python scripts/run_stage2.py --stage1-output outputs/latest/stage1_deterministic.json
# Look for extraction success rate in output
```

---

## Known Edge Cases

1. **Stations without Fandom pages**: Some newer stations may not have pages yet
2. **Disambiguation pages**: Some names may redirect to disambiguation pages
3. **Redirects**: Fandom may redirect old URLs to new ones
4. **Special characters**: Stations with slashes, parentheses, etc. in names
5. **Renamed stations**: Some stations were renamed (e.g., Marina Bay → former name)

---

## Future Improvements

1. **Fandom API integration**: Use Fandom's search API as primary method
2. **Machine learning**: Train a model to predict correct casing from examples
3. **Community contributions**: Allow users to submit URL corrections
4. **Wikidata fallback**: Use Wikidata as alternative source for station info
