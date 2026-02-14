"""
Tests for BUGFIX-003: MRT/LRT Station Type Support

This module tests station type detection and Fandom URL generation
for both MRT and LRT stations, including interchange stations.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.pipelines.stage1_ingestion import Stage1Ingestion
from src.contracts.schemas import StationType, Stage1Station, Exit


class TestStationTypeDetection:
    """Test station type detection logic"""
    
    def test_lrt_station_detection(self):
        """Test that LRT stations are correctly identified"""
        stage = Stage1Ingestion({})
        
        # Test various LRT station names
        assert stage._detect_station_type("BUKIT PANJANG LRT STATION", []) == StationType.LRT
        assert stage._detect_station_type("SENGKANG LRT STATION", []) == StationType.LRT
        assert stage._detect_station_type("PUNGGOL LRT STATION", []) == StationType.LRT
        assert stage._detect_station_type("CHOA CHU KANG LRT STATION", []) == StationType.LRT
        assert stage._detect_station_type("SENJA LRT STATION", []) == StationType.LRT
    
    def test_mrt_station_detection(self):
        """Test that MRT stations are correctly identified"""
        stage = Stage1Ingestion({})
        
        # Test various MRT station names
        assert stage._detect_station_type("YISHUN MRT STATION", []) == StationType.MRT
        assert stage._detect_station_type("WOODLANDS MRT STATION", []) == StationType.MRT
        assert stage._detect_station_type("ORCHARD MRT STATION", []) == StationType.MRT
        assert stage._detect_station_type("RAFFLES PLACE MRT STATION", []) == StationType.MRT
    
    def test_default_to_mrt_for_unknown(self, caplog):
        """Test that unknown station types default to MRT with warning"""
        stage = Stage1Ingestion({})
        
        # Test station name without clear type
        result = stage._detect_station_type("UNKNOWN STATION", [])
        assert result == StationType.MRT


class TestInterchangeStationDetection:
    """Test interchange station detection logic"""
    
    def test_bukit_panjang_interchange(self):
        """Test Bukit Panjang interchange detection"""
        stage = Stage1Ingestion({})
        codes = ["DT1", "BP1"]  # Downtown Line + Bukit Panjang LRT
        assert stage._is_interchange_station(codes) is True
    
    def test_sengkang_interchange(self):
        """Test Sengkang interchange detection"""
        stage = Stage1Ingestion({})
        codes = ["NE16", "STC"]  # North East Line + Sengkang LRT Hub
        assert stage._is_interchange_station(codes) is True
    
    def test_punggol_interchange(self):
        """Test Punggol interchange detection"""
        stage = Stage1Ingestion({}
        )
        codes = ["NE17", "PTC"]  # North East Line + Punggol LRT Hub
        assert stage._is_interchange_station(codes) is True
    
    def test_choa_chu_kang_interchange(self):
        """Test Choa Chu Kang interchange detection"""
        stage = Stage1Ingestion({})
        codes = ["NS4", "BP1"]  # North South Line + Bukit Panjang LRT
        assert stage._is_interchange_station(codes) is True
    
    def test_non_interchange_mrt_only(self):
        """Test that MRT-only stations are not interchange"""
        stage = Stage1Ingestion({})
        codes = ["NS13", "NS14"]  # Only North South Line
        assert stage._is_interchange_station(codes) is False
    
    def test_non_interchange_lrt_only(self):
        """Test that LRT-only stations are not interchange"""
        stage = Stage1Ingestion({})
        codes = ["BP2", "BP3"]  # Only Bukit Panjang LRT
        assert stage._is_interchange_station(codes) is False


class TestFandomURLGeneration:
    """Test Fandom URL generation for different station types"""
    
    def test_mrt_station_url(self):
        """Test URL generation for MRT stations"""
        stage = Stage1Ingestion({})
        url = stage._build_fandom_url("YISHUN MRT STATION", ["NS13"])
        assert "Yishun_MRT_Station" in url
        assert "singapore-mrt-lines.fandom.com" in url
    
    def test_lrt_station_url(self):
        """Test URL generation for LRT stations"""
        stage = Stage1Ingestion({})
        url = stage._build_fandom_url("SENJA LRT STATION", ["BP13"])
        assert "Senja_LRT_Station" in url
        assert "singapore-mrt-lines.fandom.com" in url
    
    def test_bukit_panjang_interchange_url(self):
        """Test URL generation for Bukit Panjang interchange"""
        stage = Stage1Ingestion({})
        codes = ["DT1", "BP1"]
        url = stage._build_fandom_url("BUKIT PANJANG MRT/LRT STATION", codes)
        assert "Bukit_Panjang_MRT/LRT_Station" in url
        assert "singapore-mrt-lines.fandom.com" in url
    
    def test_sengkang_interchange_url(self):
        """Test URL generation for Sengkang interchange"""
        stage = Stage1Ingestion({})
        codes = ["NE16", "STC"]
        url = stage._build_fandom_url("SENGKANG MRT/LRT STATION", codes)
        assert "Sengkang_MRT/LRT_Station" in url
        assert "singapore-mrt-lines.fandom.com" in url
    
    def test_punggol_interchange_url(self):
        """Test URL generation for Punggol interchange"""
        stage = Stage1Ingestion({})
        codes = ["NE17", "PTC"]
        url = stage._build_fandom_url("PUNGGOL MRT/LRT STATION", codes)
        assert "Punggol_MRT/LRT_Station" in url
        assert "singapore-mrt-lines.fandom.com" in url
    
    def test_choa_chu_kang_interchange_url(self):
        """Test URL generation for Choa Chu Kang interchange"""
        stage = Stage1Ingestion({})
        codes = ["NS4", "BP1"]
        url = stage._build_fandom_url("CHOA CHU KANG MRT/LRT STATION", codes)
        assert "Choa_Chu_Kang_MRT/LRT_Station" in url
        assert "singapore-mrt-lines.fandom.com" in url


class TestStage1StationWithLRT:
    """Test Stage1Station model with LRT data"""
    
    def test_lrt_station_creation(self):
        """Test creating an LRT station"""
        exit = Exit(exit_code="1", lat=1.3521, lng=103.8198, source="datagov")
        station = Stage1Station(
            station_id="BP1",
            official_name="BUKIT PANJANG LRT STATION",
            display_name="Bukit Panjang",
            mrt_codes=["BP1"],
            lines=["BPL"],
            station_type=StationType.LRT,
            exits=[exit],
            fandom_url="https://singapore-mrt-lines.fandom.com/wiki/Bukit_Panjang_LRT_Station"
        )
        
        assert station.station_type == StationType.LRT
        assert station.station_id == "BP1"
        assert "BPL" in station.lines
    
    def test_interchange_station_creation(self):
        """Test creating an interchange station"""
        exit = Exit(exit_code="A", lat=1.3521, lng=103.8198, source="datagov")
        station = Stage1Station(
            station_id="DT1",
            official_name="BUKIT PANJANG MRT/LRT STATION",
            display_name="Bukit Panjang",
            mrt_codes=["DT1", "BP1"],
            lines=["DTL", "BPL"],
            station_type=StationType.MRT,  # Interchange stations default to MRT
            exits=[exit],
            fandom_url="https://singapore-mrt-lines.fandom.com/wiki/Bukit_Panjang_MRT/LRT_Station"
        )
        
        assert station.station_type == StationType.MRT
        assert "DT1" in station.mrt_codes
        assert "BP1" in station.mrt_codes
        assert "DTL" in station.lines
        assert "BPL" in station.lines


class TestApplyCorrections:
    """Test _apply_corrections() method for interchange renaming"""
    
    def test_interchange_station_renaming(self):
        """Test that interchange stations are renamed to 'MRT/LRT STATION' format"""
        stage = Stage1Ingestion({})
        
        # Create test stations before corrections
        stations = [
            Stage1Station(
                station_id="DT1",
                official_name="BUKIT PANJANG MRT STATION",
                display_name="Bukit Panjang",
                mrt_codes=["DT1", "BP1"],
                lines=["DTL", "BPL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.378, lng=103.762, source="datagov")],
                fandom_url="https://example.com"
            ),
            Stage1Station(
                station_id="NE16",
                official_name="SENGKANG MRT STATION",
                display_name="Sengkang",
                mrt_codes=["NE16", "STC"],
                lines=["NEL", "SKL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.392, lng=103.895, source="datagov")],
                fandom_url="https://example.com"
            ),
            Stage1Station(
                station_id="NE17",
                official_name="PUNGGOL MRT STATION",
                display_name="Punggol",
                mrt_codes=["NE17", "PTC"],
                lines=["NEL", "PGL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.405, lng=103.902, source="datagov")],
                fandom_url="https://example.com"
            ),
            Stage1Station(
                station_id="NS4",
                official_name="CHOA CHU KANG MRT STATION",
                display_name="Choa Chu Kang",
                mrt_codes=["NS4", "BP1"],
                lines=["NSL", "BPL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.385, lng=103.744, source="datagov")],
                fandom_url="https://example.com"
            ),
        ]
        
        # Apply corrections
        corrected = stage._apply_corrections(stations)
        
        # Verify all 4 interchange stations are renamed
        bukit_panjang = next(s for s in corrected if s.display_name == "Bukit Panjang")
        assert bukit_panjang.official_name == "BUKIT PANJANG MRT/LRT STATION"
        assert bukit_panjang.station_type == StationType.MRT
        assert "Bukit_Panjang_MRT/LRT_Station" in bukit_panjang.fandom_url
        
        sengkang = next(s for s in corrected if s.display_name == "Sengkang")
        assert sengkang.official_name == "SENGKANG MRT/LRT STATION"
        assert sengkang.station_type == StationType.MRT
        assert "Sengkang_MRT/LRT_Station" in sengkang.fandom_url
        
        punggol = next(s for s in corrected if s.display_name == "Punggol")
        assert punggol.official_name == "PUNGGOL MRT/LRT STATION"
        assert punggol.station_type == StationType.MRT
        assert "Punggol_MRT/LRT_Station" in punggol.fandom_url
        
        choa_chu_kang = next(s for s in corrected if s.display_name == "Choa Chu Kang")
        assert choa_chu_kang.official_name == "CHOA CHU KANG MRT/LRT STATION"
        assert choa_chu_kang.station_type == StationType.MRT
        assert "Choa_Chu_Kang_MRT/LRT_Station" in choa_chu_kang.fandom_url
    
    def test_non_interchange_stations_unchanged(self):
        """Test that non-interchange stations are not modified"""
        stage = Stage1Ingestion({})
        
        # Create test stations
        stations = [
            Stage1Station(
                station_id="NS13",
                official_name="YISHUN MRT STATION",
                display_name="Yishun",
                mrt_codes=["NS13"],
                lines=["NSL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.429, lng=103.835, source="datagov")],
                fandom_url="https://example.com/yishun"
            ),
            Stage1Station(
                station_id="BP2",
                official_name="SOUTH VIEW LRT STATION",
                display_name="South View",
                mrt_codes=["BP2"],
                lines=["BPL"],
                station_type=StationType.LRT,
                exits=[Exit(exit_code="1", lat=1.369, lng=103.745, source="datagov")],
                fandom_url="https://example.com/south_view"
            ),
        ]
        
        # Apply corrections
        corrected = stage._apply_corrections(stations)
        
        # Verify non-interchange stations are unchanged
        yishun = next(s for s in corrected if s.station_id == "NS13")
        assert yishun.official_name == "YISHUN MRT STATION"
        assert yishun.station_type == StationType.MRT
        
        south_view = next(s for s in corrected if s.station_id == "BP2")
        assert south_view.official_name == "SOUTH VIEW LRT STATION"
        assert south_view.station_type == StationType.LRT
    
    def test_lrt_hub_codes_added(self):
        """Test that LRT hub codes are added to interchange stations"""
        stage = Stage1Ingestion({})
        
        # Create Sengkang station without STC code
        stations = [
            Stage1Station(
                station_id="NE16",
                official_name="SENGKANG MRT STATION",
                display_name="Sengkang",
                mrt_codes=["NE16"],  # Missing STC
                lines=["NEL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.392, lng=103.895, source="datagov")],
                fandom_url="https://example.com"
            ),
        ]
        
        # Apply corrections
        corrected = stage._apply_corrections(stations)
        
        # Verify STC code is added
        sengkang = corrected[0]
        assert "STC" in sengkang.mrt_codes
        assert "SKL" in sengkang.lines  # Lines should be updated


class TestDataQualityIntegration:
    """Integration tests for data quality verification"""
    
    def test_no_exit_codes_in_station_codes(self):
        """Test that exit codes (A1, B2, etc.) are not present in station codes"""
        import re
        from src.processors.matching_engine import MatchingEngine
        from src.fetchers.onemap_fetcher import OneMapFetcher
        
        # Create matcher with default config
        onemap = OneMapFetcher()
        matcher = MatchingEngine(onemap, config={})
        
        # Test building names that might contain exit codes
        test_buildings = [
            "BUKIT PANJANG MRT STATION (A1)",
            "BUKIT PANJANG MRT STATION (A2)",
            "CHOA CHU KANG MRT STATION (B1/B2)",
            "YISHUN MRT STATION (A)",
        ]
        
        exit_code_pattern = re.compile(r'\b[A-Z]\d+\b')
        
        for building in test_buildings:
            codes = matcher._extract_codes(building)
            # Check that no single-letter codes (like A1, B2) are extracted
            for code in codes:
                # Station codes should be at least 2 chars or start with valid prefixes
                assert len(code) >= 2, f"Exit code '{code}' extracted from '{building}'"
                # Should not match single letter + number pattern
                assert not exit_code_pattern.fullmatch(code), f"Exit code '{code}' extracted from '{building}'"
    
    def test_interchange_stations_have_correct_type(self):
        """Test that interchange stations have station_type=MRT"""
        stage = Stage1Ingestion({})
        
        interchange_names = [
            "BUKIT PANJANG MRT/LRT STATION",
            "SENGKANG MRT/LRT STATION",
            "PUNGGOL MRT/LRT STATION",
            "CHOA CHU KANG MRT/LRT STATION",
        ]
        
        for name in interchange_names:
            station_type = stage._detect_station_type(name, [])
            assert station_type == StationType.MRT, f"Interchange station '{name}' should have type MRT, got {station_type}"
    
    def test_station_code_extraction_with_config(self):
        """Test that station code extraction respects configured prefixes"""
        import yaml
        from pathlib import Path
        
        # Load actual config
        config_path = Path(__file__).parent.parent / "config" / "pipeline.yaml"
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        pipeline_config = config.get('pipeline', {})
        prefixes = pipeline_config.get('station_code_prefixes', [])
        
        # Verify all expected prefixes are present
        expected_prefixes = ['NS', 'EW', 'NE', 'CC', 'DT', 'TE', 'BP', 'STC', 'PTC']
        for prefix in expected_prefixes:
            assert prefix in prefixes, f"Expected prefix '{prefix}' not found in config"
        
        # Verify exit code prefixes are NOT in the list
        exit_prefixes = ['A', 'B', 'C', 'D']
        for prefix in exit_prefixes:
            assert prefix not in prefixes, f"Exit prefix '{prefix}' should not be in station_code_prefixes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
