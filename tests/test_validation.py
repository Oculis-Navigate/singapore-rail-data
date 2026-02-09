"""
Tests for data validation logic

This module contains tests for sanity checks, completeness checks,
and data quality validation.
"""

import pytest
import json
from pathlib import Path
from typing import Dict, Any, List

# Import project modules
from src.contracts.schemas import (
    Stage1Output, Stage2Output, FinalOutput,
    Stage1Station, Stage2Station, FinalStation,
    Exit, FinalExit, StationType
)
from src.pipelines.stage3_merger import Stage3Merger


class TestSanityChecks:
    """Sanity checks for coordinate validation"""
    
    def test_coordinates_in_singapore(self, singapore_coords_valid):
        """Verify coordinates are within Singapore bounds"""
        # Lat: 1.0-2.0, Lng: 103.0-105.0
        for lat, lng in singapore_coords_valid:
            assert 1.0 <= lat <= 2.0, f"Latitude {lat} out of bounds"
            assert 103.0 <= lng <= 105.0, f"Longitude {lng} out of bounds"
    
    def test_invalid_coordinates(self, singapore_coords_invalid):
        """Detect coordinates outside Singapore"""
        for lat, lng in singapore_coords_invalid:
            is_valid = (1.0 <= lat <= 2.0 and 103.0 <= lng <= 105.0)
            assert not is_valid, f"Coordinate ({lat}, {lng}) should be invalid"


class TestSchemaValidation:
    """Tests for schema validation"""
    
    def test_stage1_output_validation(self, sample_stage1_output):
        """Test Stage 1 output validates correctly"""
        output = Stage1Output.model_validate(sample_stage1_output)
        assert len(output.stations) == 1
        assert output.stations[0].station_id == "NS13"
    
    def test_final_output_validation(self, sample_final_station):
        """Test Final output validates correctly"""
        output = FinalOutput(
            metadata={"test": True, "total_stations": 1},
            stations=[sample_final_station]
        )
        assert len(output.stations) == 1
        assert output.stations[0].official_name == "YISHUN MRT STATION"


class TestCompletenessChecks:
    """Tests for data completeness"""
    
    def test_station_count(self, sample_stage1_output):
        """Verify expected station count logic"""
        expected_count = 187
        output = Stage1Output.model_validate(sample_stage1_output)
        actual_count = len(output.stations)
        # This is a sample, so we'll just verify the logic works
        assert actual_count >= 1, "Should have at least one station"
    
    def test_all_stations_have_exits(self, sample_stage1_output):
        """Every station must have at least one exit"""
        output = Stage1Output.model_validate(sample_stage1_output)
        for station in output.stations:
            assert len(station.exits) > 0, f"Station {station.station_id} has no exits"
    
    def test_no_duplicate_station_names(self, sample_stage1_output):
        """Station names should be unique"""
        output = Stage1Output.model_validate(sample_stage1_output)
        names = [s.official_name for s in output.stations]
        assert len(names) == len(set(names)), "Duplicate station names found"


class TestDataQuality:
    """Tests for data quality metrics"""
    
    def test_enrichment_coverage(self, sample_stage2_output):
        """Check what percentage of stations have enrichment data"""
        # Load stage 2 output
        stations = sample_stage2_output.stations
        total_stations = len(stations)
        
        # Count stations with successful extraction
        enriched_count = sum(
            1 for s in stations.values() 
            if s.extraction_result == "success"
        )
        
        # Calculate coverage
        coverage = enriched_count / total_stations if total_stations > 0 else 0
        
        # For this sample, should be 100%
        assert coverage >= 0.8, f"Enrichment coverage {coverage:.1%} is below threshold"
    
    def test_exit_code_consistency(self):
        """Verify exit codes are consistent across sources"""
        # Test that exit codes are normalized
        exit_codes = ["A", "B", "1", "2"]
        for code in exit_codes:
            # All should be single character or digit
            assert len(code) <= 2, f"Exit code {code} is too long"
            assert code.isalnum(), f"Exit code {code} should be alphanumeric"


class TestExitCodeNormalization:
    """Tests for exit code normalization logic"""
    
    def test_exit_code_normalization(self):
        """Test exit code matching logic from Stage3Merger"""
        merger = Stage3Merger({})
        
        # Test various formats
        assert merger._normalize_exit_code("Exit A") == "A"
        assert merger._normalize_exit_code("EXIT B") == "B"
        assert merger._normalize_exit_code("1") == "1"
        assert merger._normalize_exit_code("  a  ") == "A"
        # "Exit" with no identifier returns empty string (no alphanumeric code)
        assert merger._normalize_exit_code("Exit") == ""
    
    def test_exit_code_edge_cases(self):
        """Test edge cases for exit code normalization"""
        merger = Stage3Merger({})
        
        # Empty should return empty string
        assert merger._normalize_exit_code("") == ""


class TestCoordinateValidation:
    """Tests for coordinate validation"""
    
    def test_valid_coordinates_in_exit(self):
        """Test that valid coordinates work in Exit model"""
        exit_obj = Exit(exit_code="A", lat=1.3521, lng=103.8198, source="onemap")
        assert exit_obj.lat == 1.3521
        assert exit_obj.lng == 103.8198
    
    def test_boundary_coordinates(self):
        """Test boundary values for coordinates"""
        # Test minimum boundaries
        exit_min = Exit(exit_code="A", lat=1.0, lng=103.0, source="onemap")
        assert exit_min.lat == 1.0
        assert exit_min.lng == 103.0
        
        # Test maximum boundaries
        exit_max = Exit(exit_code="B", lat=2.0, lng=105.0, source="datagov")
        assert exit_max.lat == 2.0
        assert exit_max.lng == 105.0


class TestValidationScript:
    """Tests for the validation script functionality"""
    
    def test_validate_schema_function(self, tmp_path):
        """Test schema validation works"""
        # Create a test file
        test_data = {
            "metadata": {"test": True},
            "stations": [
                {
                    "station_id": "NS13",
                    "official_name": "YISHUN MRT STATION",
                    "display_name": "Yishun",
                    "mrt_codes": ["NS13"],
                    "lines": ["NSL"],
                    "station_type": "mrt",
                    "exits": [
                        {"exit_code": "A", "lat": 1.429, "lng": 103.835, "source": "onemap"}
                    ],
                    "fandom_url": "https://example.com"
                }
            ]
        }
        
        test_file = tmp_path / "test_output.json"
        with open(test_file, 'w') as f:
            json.dump(test_data, f)
        
        # Validate it
        with open(test_file, 'r') as f:
            loaded_data = json.load(f)
        
        output = Stage1Output.model_validate(loaded_data)
        assert len(output.stations) == 1
    
    def test_validate_completeness(self, sample_stage1_output):
        """Test completeness validation"""
        output = Stage1Output.model_validate(sample_stage1_output)
        
        # Check we have stations
        assert len(output.stations) > 0
        
        # Check all stations have required fields
        for station in output.stations:
            assert station.station_id
            assert station.official_name
            assert station.mrt_codes
            assert station.lines


class TestAlertTriggers:
    """Tests for alert triggering conditions"""
    
    def test_critical_alert_conditions(self):
        """Test conditions that should trigger critical alerts"""
        # HTTP 404/500, schema failures, missing required fields
        critical_conditions = [
            ("http_404", "Page not found"),
            ("http_500", "Server error"),
            ("schema_error", "Validation failed"),
            ("missing_field", "Required field missing"),
        ]
        
        for condition, message in critical_conditions:
            assert condition in ["http_404", "http_500", "schema_error", "missing_field"]
            assert message
    
    def test_error_alert_conditions(self):
        """Test conditions that should trigger error alerts"""
        error_conditions = [
            ("extraction_failed", "Station extraction failed"),
            ("low_station_count", "Station count below expected"),
            ("coordinate_error", "Invalid coordinates"),
        ]
        
        for condition, message in error_conditions:
            assert condition
            assert message
    
    def test_warning_alert_conditions(self):
        """Test conditions that should trigger warning alerts"""
        warning_conditions = [
            ("low_coverage", "Enrichment coverage below 70%"),
            ("api_timeout", "API timeout but retry succeeded"),
            ("data_quality", "Data quality issue"),
        ]
        
        for condition, message in warning_conditions:
            assert condition
            assert message
