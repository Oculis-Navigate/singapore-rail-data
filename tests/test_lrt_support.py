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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
