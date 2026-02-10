"""
URL Resolution Cache for Fandom Wiki URLs

This module provides persistent caching for Fandom URL resolutions
to avoid repeated HTTP requests and improve performance.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path


class URLResolutionCache:
    """Persistent cache for Fandom URL resolutions."""
    
    def __init__(self, cache_file: str = ".url_cache.json"):
        """
        Initialize the URL resolution cache.
        
        Args:
            cache_file: Path to the cache file (default: .url_cache.json)
        """
        self.cache_file = cache_file
        self.cache = self._load_cache()
        self.max_age_days = 30  # Refresh cache monthly
    
    def _load_cache(self) -> dict:
        """Load cache from disk."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def save_cache(self):
        """Save cache to disk."""
        try:
            # Ensure parent directory exists
            cache_path = Path(self.cache_file)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except IOError as e:
            # Fail silently - cache is optimization, not critical
            pass
    
    def get(self, station_name: str) -> Optional[str]:
        """
        Get cached URL if exists and not expired.
        
        Args:
            station_name: Station display name
            
        Returns:
            Cached URL or None if not found/expired
        """
        key = station_name.lower().replace(' ', '_')
        if key in self.cache:
            entry = self.cache[key]
            try:
                cached_date = datetime.fromisoformat(entry['timestamp'])
                if datetime.now() - cached_date < timedelta(days=self.max_age_days):
                    return entry['url']
            except (KeyError, ValueError):
                # Invalid cache entry, remove it
                del self.cache[key]
        return None
    
    def set(self, station_name: str, url: str):
        """
        Cache a URL resolution.
        
        Args:
            station_name: Station display name
            url: Resolved Fandom URL
        """
        key = station_name.lower().replace(' ', '_')
        self.cache[key] = {
            'url': url,
            'timestamp': datetime.now().isoformat(),
            'station_name': station_name
        }
        # Auto-save on every set to persist progress
        self.save_cache()
    
    def clear(self):
        """Clear all cached entries."""
        self.cache = {}
        self.save_cache()
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            'total_entries': len(self.cache),
            'cache_file': self.cache_file
        }
