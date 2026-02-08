"""
Fandom Wiki Scraper for MRT Station Information

This module provides a scraper for fetching HTML content from
Singapore MRT Fandom wiki pages.
"""

import requests
from typing import Optional
from urllib.parse import quote
from ..utils.logger import logger


class FandomScraper:
    """Scraper for Singapore MRT Fandom pages"""
    
    def __init__(self, config: dict = None):
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
    
    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch HTML content from Fandom page"""
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None