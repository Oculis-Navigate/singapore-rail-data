"""
Tests for Fandom Scraper URL resolution functionality.

These tests verify the URL resolution, caching, and manual mapping features
implemented in BUGFIX-004.
"""

import pytest
import os
import json
import tempfile
from unittest.mock import Mock, patch
from src.pipelines.fandom_scraper import FandomScraper
from src.utils.url_cache import URLResolutionCache


class TestURLResolutionCache:
    """Test the URLResolutionCache class"""
    
    def test_cache_load_and_save(self):
        """Test cache persistence to disk"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        try:
            # Create cache and add entry
            cache = URLResolutionCache(cache_file)
            cache.set("Test Station", "https://example.com/test")
            
            # Create new cache instance with same file
            cache2 = URLResolutionCache(cache_file)
            url = cache2.get("Test Station")
            
            assert url == "https://example.com/test"
        finally:
            os.unlink(cache_file)
    
    def test_cache_expiration(self):
        """Test that expired cache entries are not returned"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        try:
            cache = URLResolutionCache(cache_file)
            cache.max_age_days = -1  # Expired immediately
            cache.set("Test Station", "https://example.com/test")
            
            # Should return None because entry is expired
            url = cache.get("Test Station")
            assert url is None
        finally:
            os.unlink(cache_file)
    
    def test_cache_stats(self):
        """Test cache statistics"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        try:
            cache = URLResolutionCache(cache_file)
            cache.set("Station 1", "https://example.com/1")
            cache.set("Station 2", "https://example.com/2")
            
            stats = cache.get_stats()
            assert stats['total_entries'] == 2
        finally:
            if os.path.exists(cache_file):
                os.unlink(cache_file)
    
    def test_cache_clear(self):
        """Test clearing the cache"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            cache_file = f.name
        
        try:
            cache = URLResolutionCache(cache_file)
            cache.set("Station 1", "https://example.com/1")
            cache.clear()
            
            assert cache.get("Station 1") is None
            assert cache.get_stats()['total_entries'] == 0
        finally:
            if os.path.exists(cache_file):
                os.unlink(cache_file)


class TestFandomScraperURLResolution:
    """Test the FandomScraper URL resolution functionality"""
    
    @pytest.fixture
    def scraper(self):
        """Create a FandomScraper instance with test config"""
        config = {
            'pipeline': {
                'url_mappings': {
                    'Test Station': 'https://example.com/manual'
                }
            }
        }
        return FandomScraper(config)
    
    def test_manual_mapping_priority(self, scraper):
        """Test that manual mappings take priority"""
        url = scraper.resolve_fandom_url('Test Station')
        assert url == 'https://example.com/manual'
    
    def test_generate_url_candidates_title_case(self, scraper):
        """Test title case candidate generation"""
        candidates = scraper._generate_url_candidates('Gardens By The Bay')
        
        # Should include title case version
        assert any('Gardens_By_The_Bay' in c for c in candidates)
    
    def test_generate_url_candidates_lowercase_articles(self, scraper):
        """Test lowercase articles candidate generation"""
        candidates = scraper._generate_url_candidates('Gardens By The Bay')
        
        # Should include lowercase articles version
        assert any('Gardens_by_the_Bay' in c for c in candidates)
    
    def test_generate_url_candidates_all_lowercase(self, scraper):
        """Test all lowercase candidate generation"""
        candidates = scraper._generate_url_candidates('Gardens By The Bay')
        
        # Should include all lowercase version
        assert any('gardens_by_the_bay' in c.lower() for c in candidates)
    
    def test_generate_url_candidates_mrt_suffix(self, scraper):
        """Test MRT suffix is added correctly"""
        candidates = scraper._generate_url_candidates('Yishun')
        
        # All candidates should have MRT_Station suffix
        assert all('_MRT_Station' in c for c in candidates)
    
    def test_generate_url_candidates_lrt_suffix(self, scraper):
        """Test LRT suffix is added correctly"""
        candidates = scraper._generate_url_candidates('Bukit Panjang LRT Station')
        
        # Should have LRT suffix (not MRT/LRT since it's not an interchange)
        assert all('_LRT_Station' in c for c in candidates)
    
    def test_generate_url_candidates_special_cases(self, scraper):
        """Test special casing for known problematic stations"""
        # Test MacPherson -> Macpherson
        candidates = scraper._generate_url_candidates('MacPherson')
        assert any('Macpherson' in c for c in candidates)
        
        # Test One-North -> One-north
        candidates = scraper._generate_url_candidates('One-North')
        assert any('One-north' in c for c in candidates)
    
    @patch.object(FandomScraper, '_url_exists')
    def test_url_exists_check(self, mock_exists, scraper):
        """Test URL existence checking"""
        mock_exists.return_value = True
        
        exists = scraper._url_exists('https://example.com/test')
        assert exists is True
    
    @patch.object(FandomScraper, '_url_exists')
    @patch.object(FandomScraper, '_search_fandom_api')
    def test_resolve_falls_back_to_api(self, mock_api, mock_exists, scraper):
        """Test that API search is used as fallback"""
        mock_exists.return_value = False
        mock_api.return_value = 'https://example.com/api-result'
        
        url = scraper.resolve_fandom_url('Unknown Station')
        
        assert url == 'https://example.com/api-result'
        mock_api.assert_called_once()
    
    @patch.object(FandomScraper, '_url_exists')
    @patch.object(FandomScraper, '_search_fandom_api')
    def test_resolve_returns_none_when_all_fail(self, mock_api, mock_exists, scraper):
        """Test that None is returned when all resolution methods fail"""
        mock_exists.return_value = False
        mock_api.return_value = None
        
        # Use a unique station name to avoid cache interference
        url = scraper.resolve_fandom_url('Completely Unknown Station XYZ123')
        
        assert url is None
    
    def test_caching_after_successful_resolution(self, scraper):
        """Test that successful resolutions are cached"""
        with patch.object(scraper, '_url_exists', return_value=True):
            with patch.object(scraper.url_cache, 'set') as mock_cache_set:
                scraper.resolve_fandom_url('Yishun')
                mock_cache_set.assert_called_once()


class TestFandomScraperIntegration:
    """Integration tests for FandomScraper with real URLs"""
    
    @pytest.fixture
    def real_scraper(self):
        """Create a FandomScraper with real config"""
        return FandomScraper({})
    
    @pytest.mark.slow
    def test_url_exists_real(self, real_scraper):
        """Test URL existence check with real Fandom URLs"""
        # This test makes real HTTP requests - mark as slow
        exists = real_scraper._url_exists(
            'https://singapore-mrt-lines.fandom.com/wiki/Yishun_MRT_Station'
        )
        assert exists is True
    
    @pytest.mark.slow
    def test_resolve_known_stations(self, real_scraper):
        """Test resolving URLs for known stations"""
        # This test makes real HTTP requests - mark as slow
        test_cases = [
            ('Yishun', 'Yishun_MRT_Station'),
            ('Jurong East', 'Jurong_East_MRT_Station'),
        ]
        
        for station_name, expected_fragment in test_cases:
            url = real_scraper.resolve_fandom_url(station_name)
            assert url is not None
            assert expected_fragment in url


class TestStage1URLIntegration:
    """Test Stage1Ingestion integration with FandomScraper"""
    
    def test_stage1_uses_scraper_for_url_generation(self):
        """Test that Stage1Ingestion uses FandomScraper for URL building"""
        from src.pipelines.stage1_ingestion import Stage1Ingestion
        
        config = {'pipeline': {'url_mappings': {}}}
        stage1 = Stage1Ingestion(config)
        
        # Verify FandomScraper is initialized
        assert hasattr(stage1, 'fandom_scraper')
        assert isinstance(stage1.fandom_scraper, FandomScraper)
    
    def test_build_fandom_url_with_display_name(self):
        """Test that _build_fandom_url accepts display_name parameter"""
        from src.pipelines.stage1_ingestion import Stage1Ingestion
        
        config = {'pipeline': {'url_mappings': {}}}
        stage1 = Stage1Ingestion(config)
        
        # Test with display_name
        with patch.object(stage1.fandom_scraper, 'resolve_fandom_url', return_value='https://example.com/test'):
            url = stage1._build_fandom_url('YISHUN MRT STATION', 'Yishun')
            assert url == 'https://example.com/test'
    
    def test_naive_url_generation_fallback(self):
        """Test naive URL generation as fallback"""
        from src.pipelines.stage1_ingestion import Stage1Ingestion
        
        config = {'pipeline': {'url_mappings': {}}}
        stage1 = Stage1Ingestion(config)
        
        url = stage1._naive_url_generation('YISHUN MRT STATION')
        assert 'Yishun_MRT_Station' in url
