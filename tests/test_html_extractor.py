"""
Tests for HTML Content Extractor
"""

import pytest
from src.pipelines.html_extractor import FandomContentExtractor


class TestFandomContentExtractor:
    """Test cases for FandomContentExtractor"""
    
    @pytest.fixture
    def extractor(self):
        """Create extractor instance for tests"""
        return FandomContentExtractor()
    
    def test_extract_relevant_content_with_exit_table(self, extractor):
        """Test extraction when exit table is present"""
        html = """
        <html>
        <body>
            <nav>Navigation menu</nav>
            <header>Page header</header>
            <main id="content">
                <h1>Bright Hill MRT Station</h1>
                <h2>Exits</h2>
                <table>
                    <tr><th>Exit</th><th>Location</th></tr>
                    <tr><td>A</td><td>Main Road</td></tr>
                    <tr><td>B</td><td>Shopping Center</td></tr>
                </table>
            </main>
        </body>
        </html>
        """
        
        result = extractor.extract_relevant_content(html, "Bright Hill")
        
        assert "Exit" in result
        assert "Bright Hill" in result
        assert "Navigation menu" not in result
        assert "Page header" not in result
        assert "<table" in result
    
    def test_extract_relevant_content_with_platforms(self, extractor):
        """Test extraction when platform section is present"""
        html = """
        <html>
        <body>
            <main>
                <h2>Platforms</h2>
                <p>Platform A towards Jurong East</p>
                <p>Platform B towards Marina Bay</p>
            </main>
        </body>
        </html>
        """
        
        result = extractor.extract_relevant_content(html, "Test Station")
        
        assert "Platform" in result
        assert "Jurong East" in result
        assert "Marina Bay" in result
    
    def test_extract_relevant_content_with_bus_stops(self, extractor):
        """Test extraction when bus stop section is present"""
        html = """
        <html>
        <body>
            <main>
                <h2>Nearby Bus Stops</h2>
                <table>
                    <tr><th>Bus Stop Code</th><th>Services</th></tr>
                    <tr><td>12345</td><td>123, 456</td></tr>
                </table>
            </main>
        </body>
        </html>
        """
        
        result = extractor.extract_relevant_content(html, "Test Station")
        
        assert "Bus" in result or "bus" in result
        assert "12345" in result
    
    def test_extract_relevant_content_empty_html(self, extractor):
        """Test extraction with empty HTML"""
        result = extractor.extract_relevant_content("", "Test Station")
        assert result == ""
    
    def test_extract_relevant_content_no_relevant_sections(self, extractor):
        """Test extraction when no relevant sections are found"""
        html = """
        <html>
        <body>
            <main>
                <h2>Random Section</h2>
                <p>Some random content</p>
            </main>
        </body>
        </html>
        """
        
        result = extractor.extract_relevant_content(html, "Test Station")
        
        # Should still return some content (just the h1)
        assert "Test Station" in result
    
    def test_extract_relevant_content_removes_noise(self, extractor):
        """Test that noise elements are removed"""
        html = """
        <html>
        <body>
            <nav>Navigation</nav>
            <header>Header</header>
            <script>alert('test');</script>
            <style>.css{}</style>
            <main>
                <h2>Exits</h2>
                <p>Exit A information</p>
            </main>
            <footer>Footer content</footer>
        </body>
        </html>
        """
        
        result = extractor.extract_relevant_content(html, "Test Station")
        
        assert "Navigation" not in result
        assert "Header" not in result
        assert "alert" not in result
        assert ".css" not in result
        assert "Footer" not in result
        assert "Exits" in result
    
    def test_extract_relevant_content_preserves_tables(self, extractor):
        """Test that table structures are preserved"""
        html = """
        <html>
        <body>
            <main>
                <h2>Exits</h2>
                <table border="1">
                    <thead>
                        <tr><th>Exit</th><th>Location</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>A</td><td>Main Entrance</td></tr>
                    </tbody>
                </table>
            </main>
        </body>
        </html>
        """
        
        result = extractor.extract_relevant_content(html, "Test Station")
        
        assert "<table" in result
        assert "Exit" in result
        assert "Main Entrance" in result
    
    def test_extract_relevant_content_handles_malformed_html(self, extractor):
        """Test extraction with malformed HTML"""
        html = """
        <main>
            <h2>Exits
            <p>Exit A
            <table>
                <tr><td>Test</td></tr>
        """
        
        result = extractor.extract_relevant_content(html, "Test Station")
        
        # Should not crash and should return some content
        assert isinstance(result, str)
        assert "Test Station" in result
    
    def test_get_extraction_stats(self, extractor):
        """Test extraction statistics calculation"""
        original = "a" * 10000
        extracted = "b" * 5000
        
        stats = extractor.get_extraction_stats(original, extracted)
        
        assert stats["original_size"] == 10000
        assert stats["extracted_size"] == 5000
        assert stats["reduction_percentage"] == 50.0
        assert stats["reduction_ratio"] == 2.0
    
    def test_get_extraction_stats_zero_original(self, extractor):
        """Test extraction stats with zero original size"""
        stats = extractor.get_extraction_stats("", "test")
        
        assert stats["original_size"] == 0
        assert stats["extracted_size"] == 4
        assert stats["reduction_percentage"] == 0
    
    def test_classify_section_variations(self, extractor):
        """Test section classification with various headers"""
        # Test exit variations
        assert extractor._classify_section("Station Exits") == "exits"
        assert extractor._classify_section("Exit Information") == "exits"
        assert extractor._classify_section("EXITS") == "exits"
        
        # Test platform variations
        assert extractor._classify_section("Platform Layout") == "platforms"
        assert extractor._classify_section("Platforms") == "platforms"
        
        # Test bus stop variations
        assert extractor._classify_section("Nearby Bus Stops") == "bus_stops"
        assert extractor._classify_section("Bus Stops") == "bus_stops"
        
        # Test non-matching
        assert extractor._classify_section("Random Section") is None
    
    def test_extract_relevant_content_multiple_sections(self, extractor):
        """Test extraction with multiple relevant sections"""
        html = """
        <html>
        <body>
            <main>
                <h2>Exits</h2>
                <table><tr><td>Exit A</td></tr></table>
                
                <h2>Platforms</h2>
                <p>Platform A</p>
                
                <h2>Nearby Bus Stops</h2>
                <table><tr><td>12345</td></tr></table>
            </main>
        </body>
        </html>
        """
        
        result = extractor.extract_relevant_content(html, "Test Station")
        
        assert "Exits" in result
        assert "Platforms" in result
        assert "Bus Stops" in result or "Bus" in result
        assert "Exit A" in result
        assert "12345" in result
