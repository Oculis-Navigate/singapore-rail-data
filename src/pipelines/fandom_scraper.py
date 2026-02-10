"""
Fandom Wiki Scraper for MRT Station Information

This module provides a scraper for fetching HTML content from
Singapore MRT Fandom wiki pages with URL resolution for casing variations.
"""

import requests
from typing import Optional, Dict, Any, List
from urllib.parse import quote
from ..utils.logger import logger
from ..utils.url_cache import URLResolutionCache


class FandomScraper:
    """Scraper for Singapore MRT Fandom pages with URL resolution"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Fandom scraper with configuration"""
        if config:
            fandom_config = config.get('apis', {}).get('fandom', {})
            self.base_url = fandom_config.get('base_url', 'https://singapore-mrt-lines.fandom.com/wiki')
            self.timeout = fandom_config.get('timeout', 30)
        else:
            self.base_url = 'https://singapore-mrt-lines.fandom.com/wiki'
            self.timeout = 30
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        
        # Initialize URL cache
        self.url_cache = URLResolutionCache()
        
        # Load manual URL mappings from config
        self.manual_mappings = self._load_manual_mappings(config)
    
    def _load_manual_mappings(self, config: Optional[Dict[str, Any]]) -> Dict[str, str]:
        """Load manual URL mappings from config."""
        if config:
            # Check both root level and pipeline level for url_mappings
            root_mappings = config.get('url_mappings', {})
            pipeline_mappings = config.get('pipeline', {}).get('url_mappings', {})
            # Merge, with root taking precedence
            merged = {**pipeline_mappings, **root_mappings}
            return merged
        return {}
    
    def resolve_fandom_url(self, station_name: str) -> Optional[str]:
        """
        Resolve Fandom URL for a station, handling casing variations.
        
        Strategy:
        1. Check manual mappings first
        2. Check cache
        3. Try exact match first
        4. Try lowercase articles/prepositions
        5. Try all lowercase
        6. Try Fandom API search
        7. Cache successful resolution
        
        Args:
            station_name: Station display name (e.g., "Gardens By The Bay")
            
        Returns:
            Resolved URL or None if not found
        """
        # 1. Check manual mappings first (highest priority)
        if station_name in self.manual_mappings:
            manual_url = self.manual_mappings[station_name]
            logger.info(f"Using manual URL mapping for {station_name}: {manual_url}")
            return manual_url
        
        # 2. Check cache
        cached_url = self.url_cache.get(station_name)
        if cached_url:
            logger.debug(f"Cache hit for {station_name}: {cached_url}")
            return cached_url
        
        # 3. Generate candidate URLs
        candidates = self._generate_url_candidates(station_name)
        
        # 4. Try each candidate
        for url in candidates:
            if self._url_exists(url):
                logger.info(f"Resolved URL for {station_name}: {url}")
                self.url_cache.set(station_name, url)
                return url
        
        # 5. Try Fandom API as fallback
        api_url = self._search_fandom_api(station_name)
        if api_url:
            logger.info(f"Found URL via Fandom API for {station_name}: {api_url}")
            self.url_cache.set(station_name, api_url)
            return api_url
        
        logger.warning(f"Could not resolve URL for {station_name}")
        return None
    
    def _generate_url_candidates(self, station_name: str) -> List[str]:
        """
        Generate possible URL variations for a station name.
        
        Args:
            station_name: Station display name
            
        Returns:
            List of candidate URLs to try
        """
        candidates = []
        
        # Base name (remove MRT/LRT Station suffix for processing)
        base_name = station_name.replace(' MRT Station', '').replace(' LRT Station', '').replace(' Station', '')
        
        # Determine suffix based on station type
        if 'LRT' in station_name and 'MRT/LRT' not in station_name:
            suffix = 'LRT_Station'
        elif 'MRT/LRT' in station_name:
            suffix = 'MRT/LRT_Station'
        else:
            suffix = 'MRT_Station'
        
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
        
        # 5. Handle special case for MacPherson -> Macpherson
        if base_name.lower() == 'macpherson':
            candidates.append(f"{self.base_url}/Macpherson_{suffix}")
        
        # 6. Handle special case for One-North -> One-north
        if base_name.lower() == 'one-north':
            candidates.append(f"{self.base_url}/One-north_{suffix}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_candidates = []
        for url in candidates:
            if url not in seen:
                seen.add(url)
                unique_candidates.append(url)
        
        return unique_candidates
    
    def _url_exists(self, url: str) -> bool:
        """
        Check if URL returns 200 without downloading full content.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL returns 200 status code
        """
        try:
            response = self.session.head(url, timeout=5, allow_redirects=True)
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def _search_fandom_api(self, station_name: str) -> Optional[str]:
        """
        Use Fandom API to search for station page.
        Fallback when direct URL guessing fails.
        
        Args:
            station_name: Station display name
            
        Returns:
            Found URL or None
        """
        search_term = station_name.replace(' MRT Station', '').replace(' LRT Station', '')
        api_url = f"{self.base_url}/api.php?action=query&list=search&srsearch={quote(search_term)}&format=json"
        
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
    
    def validate_url(self, url: str) -> bool:
        """
        Validate that a Fandom URL exists.
        
        Args:
            url: URL to validate
            
        Returns:
            True if URL is valid (returns 200)
        """
        return self._url_exists(url)
    
    def fetch_page(self, url: str, station_name: str = "") -> Optional[str]:
        """
        Fetch HTML content from Fandom page with better error reporting.
        
        Args:
            url: URL to fetch
            station_name: Optional station name for better error messages
            
        Returns:
            HTML content or None if failed
        """
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                error_msg = (
                    f"404 Error{f' for {station_name}' if station_name else ''}\n"
                    f"  URL: {url}\n"
                    f"  This usually means the URL casing is wrong.\n"
                    f"  Check the actual Fandom page and add a manual mapping to config."
                )
                logger.error(error_msg)
            else:
                logger.error(f"HTTP {e.response.status_code}{f' for {station_name}' if station_name else ''}: {url}")
            return None
        except requests.exceptions.RequestException as e:
            # Log specific HTTP status codes for better debugging
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                if status_code == 404:
                    logger.error(f"Page not found (404): {url}")
                elif status_code == 500:
                    logger.error(f"Server error (500): {url}")
                elif status_code == 429:
                    logger.error(f"Rate limited (429): {url}")
                else:
                    logger.error(f"HTTP {status_code}: {url}")
            else:
                logger.error(f"Failed to fetch {url}: {e}")
            return None
