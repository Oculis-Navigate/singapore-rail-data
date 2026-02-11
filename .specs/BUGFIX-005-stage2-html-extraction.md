# Bugfix: Stage 2 HTML Content Extraction

## Bugfix ID: BUGFIX-005
**Priority:** P1 (Critical - causes empty extraction results)
**Estimated Effort:** 3-4 hours
**Dependencies:** FEAT-003

---

## Context

### Current State
- Stage 2 extracts enrichment data (exits, bus stops, platforms) from Fandom wiki HTML
- The current implementation blindly truncates HTML to 15,000 characters
- HTML is taken from the **beginning** of the document (`html_content[:15000]`)
- Fandom pages have massive navigation/header content at the start
- Actual station data (exits, bus stops, platforms) is near the **end** of the HTML

### Problem
1. **Truncation removes useful content**: Taking the first 15k characters captures:
   - Navigation menus
   - Wiki headers
   - Advertisements
   - Sidebar content
   - But NOT the actual station data

2. **Empty extraction results**: When LLM processes truncated HTML, it sees:
   - No exit information
   - No bus stop tables
   - No platform details
   - Only navigation structure
   
   Result: Returns empty arrays for all fields

3. **Silent failure pattern**: The LLM returns "success" with empty data because:
   - It correctly parses the HTML
   - Finds no station data (because it was truncated away)
   - Returns valid JSON with empty arrays
   - Pipeline marks extraction as "success" but with "low" confidence

4. **Wasted API calls**: Each truncated request wastes LLM tokens on useless HTML

### Evidence from Current Output

```json
{
  "TE7": {
    "station_id": "TE7",
    "official_name": "BRIGHT HILL MRT STATION",
    "extraction_result": "success",
    "extraction_confidence": "low",
    "exits": [],
    "accessibility_notes": [],
    "source_url": "https://singapore-mrt-lines.fandom.com/wiki/Bright_Hill_MRT_Station"
  }
}
```

Looking at the actual Bright Hill Fandom page HTML:
- First 15k characters: Navigation, headers, menus, categories
- Exit table location: ~35k characters into the document
- Bus stops table: ~38k characters into the document

### Goal
Implement intelligent HTML preprocessing that extracts only the relevant content sections (Exits, Platforms, Bus Stops) before sending to the LLM, ensuring high-quality extraction results.

---

## Requirements

### 1. Implement HTML Content Extractor (src/pipelines/html_extractor.py)

Create a dedicated module for intelligent HTML extraction:

```python
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
import re

class FandomContentExtractor:
    """
    Extract relevant content sections from Fandom wiki HTML.
    Removes navigation, ads, and boilerplate; keeps only station data.
    """
    
    def __init__(self):
        # Section headers that indicate relevant content
        self.relevant_sections = {
            'exits': ['exits', 'exit', 'station exits'],
            'platforms': ['platforms', 'platform', 'platform layout'],
            'bus_stops': ['nearby bus stops', 'bus stops', 'bus interchanges', 'buses'],
            'lines': ['lines', 'line', 'line information'],
            'layout': ['layout', 'station layout'],
        }
        
        # HTML elements to always remove
        self.noise_selectors = [
            'nav', 'header', 'footer', 'aside',
            '.wds-global-navigation', '.wds-community-header',
            '.advertisement', '.ad-slot',
            '.rail-module', '.page-side-tools',
            '.categories', '.page-footer',
            'script', 'style', 'noscript',
        ]
    
    def extract_relevant_content(self, html: str, station_name: str) -> str:
        """
        Extract relevant content from Fandom HTML.
        
        Returns: Clean HTML string or empty string if extraction fails
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove noise elements
            self._remove_noise(soup)
            
            # Extract main content area
            content = self._extract_main_content(soup)
            if not content:
                return ""
            
            # Find and extract relevant sections
            sections = self._extract_sections(content)
            
            # Format for LLM
            formatted = self._format_for_llm(sections, station_name)
            
            return formatted
            
        except Exception as e:
            logger.error(f"Error extracting content for {station_name}: {e}")
            return ""
```

**Implementation Notes:**
- Use BeautifulSoup4 for robust HTML parsing
- Handle malformed HTML gracefully
- Preserve table structures (important for exits/bus stops)
- Remove only structural noise, not content

### 2. Update OpenRouter Client

Modify the extraction method to use the content extractor:

```python
from src.pipelines.html_extractor import FandomContentExtractor

class OpenRouterClient:
    def __init__(self, config: dict):
        # existing init
        self.content_extractor = FandomContentExtractor()
        self.max_content_length = config.get('max_content_length', 10000)
    
    def extract_station_data(self, station_name: str, html_content: str) -> Optional[Dict]:
        """
        Extract station data using preprocessed HTML.
        """
        # Extract relevant content
        clean_html = self.content_extractor.extract_relevant_content(
            html_content, station_name
        )
        
        if not clean_html:
            return {
                "confidence": "low",
                "exits": [],
                "accessibility_notes": [
                    "Could not extract relevant content from source HTML"
                ]
            }
        
        # Truncate if still too long
        if len(clean_html) > self.max_content_length:
            clean_html = clean_html[:self.max_content_length]
        
        # Send to LLM
        # existing implementation
```

**Implementation Notes:**
- Remove the naive `html_content[:15000]` truncation
- Only truncate if content is still too large after extraction
- Log content size before/after extraction for debugging

### 3. Add Content Quality Validation

Validate that extracted content actually contains useful data:

```python
class ContentQualityChecker:
    """Check if extracted HTML content has sufficient information."""
    
    def __init__(self):
        self.min_content_length = 500
        self.required_indicators = ['exit', 'platform', 'line', 'station']
    
    def check_quality(self, html: str, station_name: str) -> Dict:
        """Check quality of extracted content."""
        issues = []
        
        if len(html) < self.min_content_length:
            issues.append(f"Content too short ({len(html)} chars)")
        
        html_lower = html.lower()
        missing_indicators = [
            indicator for indicator in self.required_indicators
            if indicator not in html_lower
        ]
        if missing_indicators:
            issues.append(f"Missing key indicators: {missing_indicators}")
        
        has_tables = '<table' in html_lower
        if not has_tables:
            issues.append("No tables found")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "content_stats": {
                "length": len(html),
                "has_tables": has_tables,
            }
        }
```

### 4. Add Extraction Metrics

Track extraction quality metrics:

```python
class ExtractionMetrics:
    """Track metrics for Stage 2 extraction quality."""
    
    def __init__(self):
        self.stats = {
            "total_processed": 0,
            "content_extraction_success": 0,
            "content_extraction_failed": 0,
            "llm_extraction_success": 0,
            "empty_exits": 0,
            "low_confidence": 0,
        }
    
    def record_extraction(self, station_name: str, 
                          html_size_before: int,
                          html_size_after: int,
                          result: Dict):
        """Record metrics for a single extraction."""
        self.stats["total_processed"] += 1
        
        if html_size_after > 0:
            self.stats["content_extraction_success"] += 1
        else:
            self.stats["content_extraction_failed"] += 1
        
        if result:
            self.stats["llm_extraction_success"] += 1
            if not result.get("exits", []):
                self.stats["empty_exits"] += 1
            if result.get("confidence") == "low":
                self.stats["low_confidence"] += 1
```

---

## Success Criteria

### Functional Requirements
- [ ] HTML content extractor successfully isolates relevant sections (Exits, Platforms, Bus Stops)
- [ ] Navigation, ads, and boilerplate are removed from HTML before LLM processing
- [ ] Average HTML size sent to LLM is reduced by at least 50% (from ~15k to ~7k chars or less)
- [ ] Content extraction succeeds for 95%+ of stations
- [ ] Stage 2 extraction produces non-empty exit data for 80%+ of stations (currently ~0%)

### Test Requirements
- [ ] Unit tests for HTML content extraction
- [ ] Unit tests for content quality validation
- [ ] Integration test with 5 stations from different lines
- [ ] Test that extraction handles malformed HTML gracefully
- [ ] Test that extraction preserves table structures

### Data Quality Requirements
- [ ] Extraction confidence improves from "low" to "medium" or "high" for most stations
- [ ] Empty exits array rate drops from ~100% to <20%
- [ ] Bus stop codes are extracted and validated (5 digits)
- [ ] Platform information is populated

### Performance Requirements
- [ ] HTML extraction completes in < 500ms per station
- [ ] Total Stage 2 processing time does not increase significantly
- [ ] Memory usage remains stable (no memory leaks in BeautifulSoup parsing)

### Observability Requirements
- [ ] Content size before/after extraction is logged for each station
- [ ] Content quality issues are logged with specific details
- [ ] Extraction metrics are reported at end of Stage 2 run
- [ ] Failed extractions include detailed error messages

---

## Files to Modify

1. `src/pipelines/html_extractor.py` - New file for HTML extraction
2. `src/pipelines/openrouter_client.py` - Use content extractor
3. `src/utils/content_quality.py` - New file for quality checking
4. `src/utils/extraction_metrics.py` - New file for metrics tracking
5. `config/pipeline.yaml` - Add content extraction configuration
6. `tests/test_html_extractor.py` - New test file
7. `pyproject.toml` - Add beautifulsoup4 dependency

---

## Verification Steps

```bash
# Test HTML extraction on a single station
python -c "
from src.pipelines.fandom_scraper import FandomScraper
from src.pipelines.html_extractor import FandomContentExtractor

scraper = FandomScraper({})
extractor = FandomContentExtractor()

url = 'https://singapore-mrt-lines.fandom.com/wiki/Bright_Hill_MRT_Station'
html = scraper.fetch_page(url)

print(f'Original HTML size: {len(html)} chars')

clean = extractor.extract_relevant_content(html, 'Bright Hill')
print(f'Extracted content size: {len(clean)} chars')
print(f'Reduction: {(1 - len(clean)/len(html))*100:.1f}%')
print()
print('First 500 chars of extracted content:')
print(clean[:500])
"

# Run full Stage 2 and check extraction quality
python scripts/run_stage2.py --stage1-output outputs/latest/stage1_deterministic.json

# Check metrics
cat outputs/latest/stage2_enrichment.json | jq '
  .stations | 
  to_entries |
  group_by(.value.extraction_confidence) |
  map({confidence: .[0].value.extraction_confidence, count: length})
'

# Expected: high/medium confidence should dominate, low should be minimal

# Check for empty exits
cat outputs/latest/stage2_enrichment.json | jq '
  [.stations[] | select(.exits | length == 0)] | length
'
# Expected: < 20% of stations
```

---

## Dependencies

Add to `pyproject.toml`:
```toml
[project.dependencies]
beautifulsoup4 = "^4.12.0"
lxml = "^4.9.0"  # Faster parser for BeautifulSoup
```

---

## Known Limitations

1. **Dynamic content**: Fandom pages may load some content via JavaScript (unlikely for this wiki)
2. **HTML structure changes**: Fandom may change their HTML structure, breaking selectors
3. **Special pages**: Some stations may have unusual page layouts
4. **Rate limiting**: HTML parsing is fast but scraping many pages may hit rate limits

---

## Future Improvements

1. **Caching extracted content**: Cache processed HTML to avoid re-parsing
2. **Parallel processing**: Extract content in parallel for faster processing
3. **ML-based extraction**: Train a model to extract tables directly
4. **Multiple source fallback**: If Fandom fails, try Wikipedia or other sources
