"""
Test suite for Pydantic schemas and data contracts

This module tests all the Pydantic models defined in src/contracts/schemas.py
to ensure they validate data correctly and catch invalid inputs.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.contracts.schemas import (
    StationType, Exit, Stage1Station, Stage1Output,
    Platform, BusStop, EnrichedExit, Stage2Station, Stage2Output,
    FinalExit, FinalStation, FinalOutput
)
from pydantic import ValidationError


class TestStationType:
    """Test StationType enum"""
    
    def test_valid_station_types(self):
        """Test that valid station types work"""
        assert StationType.MRT == "mrt"
        assert StationType.LRT == "lrt"
    
    def test_invalid_station_type(self):
        """Test that invalid station types fail"""
        with pytest.raises(ValueError):
            StationType("invalid")


class TestExit:
    """Test Exit model"""
    
    def test_valid_exit(self):
        """Test creating a valid exit"""
        exit_data = {
            "exit_code": "A",
            "lat": 1.3521,
            "lng": 103.8198,
            "source": "onemap"
        }
        exit_obj = Exit(**exit_data)
        assert exit_obj.exit_code == "A"
        assert exit_obj.source == "onemap"
    
    def test_invalid_coordinates(self):
        """Test that invalid coordinates fail validation"""
        # Latitude out of range
        with pytest.raises(ValidationError):
            Exit(exit_code="A", lat=0.0, lng=103.8198, source="onemap")
        
        # Longitude out of range  
        with pytest.raises(ValidationError):
            Exit(exit_code="A", lat=1.3521, lng=100.0, source="onemap")
    
    def test_invalid_source(self):
        """Test that invalid source fails validation"""
        with pytest.raises(ValidationError):
            Exit(exit_code="A", lat=1.3521, lng=103.8198, source="onemap")  # Using valid source for syntax


class TestStage1Station:
    """Test Stage1Station model"""
    
    def test_valid_station(self):
        """Test creating a valid station"""
        exit = Exit(exit_code="A", lat=1.3521, lng=103.8198, source="onemap")
        station_data = {
            "station_id": "NS13",
            "official_name": "YISHUN MRT STATION",
            "display_name": "Yishun",
            "mrt_codes": ["NS13"],
            "lines": ["NSL"],
            "station_type": StationType.MRT,
            "exits": [exit],
            "fandom_url": "https://example.com",
            "extraction_status": "completed"
        }
        station = Stage1Station(**station_data)
        assert station.station_id == "NS13"
        assert station.station_type == StationType.MRT
        assert len(station.exits) == 1
    
    def test_invalid_station_id(self):
        """Test that invalid station ID fails"""
        exit = Exit(exit_code="A", lat=1.3521, lng=103.8198, source="onemap")
        with pytest.raises(ValidationError):
            Stage1Station(
                station_id="invalid",
                official_name="TEST MRT STATION",
                display_name="Test",
                mrt_codes=["TEST"],
                lines=["TSL"],
                station_type=StationType.MRT,
                exits=[exit],
                fandom_url="https://example.com"
            )
    
    def test_no_exits(self):
        """Test that station with no exits fails validation"""
        with pytest.raises(ValidationError):
            Stage1Station(
                station_id="NS13",
                official_name="YISHUN MRT STATION",
                display_name="Yishun",
                mrt_codes=["NS13"],
                lines=["NSL"],
                station_type=StationType.MRT,
                exits=[],
                fandom_url="https://example.com"
            )


class TestStage1Output:
    """Test Stage1Output model"""
    
    def test_valid_output(self):
        """Test creating valid stage 1 output"""
        exit = Exit(exit_code="A", lat=1.3521, lng=103.8198, source="onemap")
        station = Stage1Station(
            station_id="NS13",
            official_name="YISHUN MRT STATION",
            display_name="Yishun",
            mrt_codes=["NS13"],
            lines=["NSL"],
            station_type=StationType.MRT,
            exits=[exit],
            fandom_url="https://example.com"
        )
        
        output = Stage1Output(
            metadata={"run_timestamp": datetime.now().isoformat()},
            stations=[station]
        )
        assert len(output.stations) == 1
    
    def test_no_stations(self):
        """Test that output with no stations fails validation"""
        with pytest.raises(ValidationError):
            Stage1Output(metadata={}, stations=[])


class TestPlatform:
    """Test Platform model"""
    
    def test_valid_platform(self):
        """Test creating a valid platform"""
        platform = Platform(
            platform_code="1",
            towards_code="NS14",
            line_code="NSL"
        )
        assert platform.platform_code == "1"
        assert platform.towards_code == "NS14"


class TestBusStop:
    """Test BusStop model"""
    
    def test_valid_bus_stop(self):
        """Test creating a valid bus stop"""
        bus_stop = BusStop(code="59019", services=["14", "62"])
        assert bus_stop.code == "59019"
        assert len(bus_stop.services) == 2
    
    def test_invalid_bus_stop_code(self):
        """Test that invalid bus stop code fails"""
        with pytest.raises(ValidationError):
            BusStop(code="invalid", services=[])


class TestEnrichedExit:
    """Test EnrichedExit model"""
    
    def test_minimal_exit(self):
        """Test creating minimal enriched exit"""
        exit = EnrichedExit(exit_code="A")
        assert exit.exit_code == "A"
        assert exit.platforms is None
        assert exit.accessibility is None
    
    def test_full_exit(self):
        """Test creating fully populated enriched exit"""
        platform = Platform(platform_code="1", towards_code="NS14", line_code="NSL")
        bus_stop = BusStop(code="59019", services=["14"])
        
        exit = EnrichedExit(
            exit_code="A",
            platforms=[platform],
            accessibility=["wheelchair_accessible"],
            bus_stops=[bus_stop],
            nearby_landmarks=["Shopping Mall"]
        )
        assert exit.platforms is not None and len(exit.platforms) == 1
        assert exit.bus_stops is not None and len(exit.bus_stops) == 1
        assert exit.nearby_landmarks is not None and len(exit.nearby_landmarks) == 1


class TestStage2Station:
    """Test Stage2Station model"""
    
    def test_successful_extraction(self):
        """Test station with successful extraction"""
        exit = EnrichedExit(exit_code="A")
        station = Stage2Station(
            station_id="NS13",
            official_name="YISHUN MRT STATION",
            extraction_result="success",
            extraction_confidence="high",
            exits=[exit],
            extraction_timestamp=datetime.now(),
            source_url="https://example.com"
        )
        assert station.extraction_result == "success"
        assert station.extraction_confidence == "high"
    
    def test_failed_extraction(self):
        """Test station with failed extraction"""
        station = Stage2Station(
            station_id="NS13",
            official_name="YISHUN MRT STATION",
            extraction_result="failed",
            exits=[],
            extraction_timestamp=datetime.now(),
            source_url="https://example.com",
            error_message="Page not found"
        )
        assert station.extraction_result == "failed"
        assert station.error_message == "Page not found"


class TestStage2Output:
    """Test Stage2Output model"""
    
    def test_valid_output(self):
        """Test creating valid stage 2 output"""
        exit = EnrichedExit(exit_code="A")
        station = Stage2Station(
            station_id="NS13",
            official_name="YISHUN MRT STATION",
            extraction_result="success",
            exits=[exit],
            extraction_timestamp=datetime.now(),
            source_url="https://example.com"
        )
        
        output = Stage2Output(
            metadata={"run_timestamp": datetime.now().isoformat()},
            stations={"NS13": station},
            failed_stations=[],
            retry_queue=[]
        )
        assert len(output.stations) == 1
        assert output.stations["NS13"].station_id == "NS13"


class TestFinalStation:
    """Test FinalStation model"""
    
    def test_minimal_station(self):
        """Test creating minimal final station"""
        exit = FinalExit(exit_code="A", lat=1.3521, lng=103.8198)
        station = FinalStation(
            official_name="YISHUN MRT STATION",
            mrt_codes=["NS13"],
            exits=[exit]
        )
        assert station.official_name == "YISHUN MRT STATION"
        assert len(station.exits) == 1
        assert station.lines_served is None
        assert station.accessibility_notes is None
    
    def test_full_station(self):
        """Test creating fully populated final station"""
        platform = Platform(platform_code="1", towards_code="NS14", line_code="NSL")
        bus_stop = BusStop(code="59019", services=["14"])
        
        exit = FinalExit(
            exit_code="A",
            lat=1.3521,
            lng=103.8198,
            platforms=[platform],
            bus_stops=[bus_stop]
        )
        
        station = FinalStation(
            official_name="YISHUN MRT STATION",
            mrt_codes=["NS13"],
            exits=[exit],
            lines_served=["NSL"],
            accessibility_notes=["wheelchair_accessible"],
            enrichment_last_updated=datetime.now(),
            data_quality={"completeness": 0.95}
        )
        assert station.lines_served == ["NSL"]
        assert station.accessibility_notes == ["wheelchair_accessible"]


class TestFinalOutput:
    """Test FinalOutput model"""
    
    def test_valid_output(self):
        """Test creating valid final output"""
        exit = FinalExit(exit_code="A", lat=1.3521, lng=103.8198)
        station = FinalStation(
            official_name="YISHUN MRT STATION",
            mrt_codes=["NS13"],
            exits=[exit]
        )
        
        output = FinalOutput(
            metadata={
                "run_timestamp": datetime.now().isoformat(),
                "pipeline_version": "2.0.0",
                "total_stations": 1
            },
            stations=[station]
        )
        assert len(output.stations) == 1
        assert output.metadata["total_stations"] == 1


if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__, "-v"])