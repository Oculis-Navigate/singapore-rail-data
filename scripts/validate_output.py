#!/usr/bin/env python3
"""
Output Validation Script

This script validates the output of the MRT data pipeline against the
expected schemas and quality criteria.

Usage:
    python validate_output.py [--output-file PATH] [--schema SCHEMA] [--verbose]
"""

import os
import sys
import json
import argparse
import yaml
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.contracts.schemas import Stage1Output, Stage2Output, FinalOutput
from pydantic import ValidationError


def load_config(config_path: str) -> Dict[str, Any]:
    """Load pipeline configuration"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def validate_json_file(file_path: str) -> bool:
    """Basic JSON file validation"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return True
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error reading JSON file {file_path}: {e}")
        return False


def validate_schema(data: Dict[str, Any], schema_type: str) -> bool:
    """Validate data against Pydantic schema"""
    try:
        if schema_type == "stage1":
            Stage1Output(**data)
        elif schema_type == "stage2":
            Stage2Output(**data)
        elif schema_type == "final":
            FinalOutput(**data)
        else:
            raise ValueError(f"Unknown schema type: {schema_type}")
        return True
    except ValidationError as e:
        print(f"Schema validation error: {e}")
        return False


def validate_station_count(data: Dict[str, Any], expected_count: int) -> bool:
    """Validate station count matches expectations"""
    if "stations" in data:
        actual_count = len(data["stations"])
        if actual_count != expected_count:
            print(f"Station count mismatch: expected {expected_count}, got {actual_count}")
            return False
        print(f"Station count correct: {actual_count}")
        return True
    print("No stations found in data")
    return False


def validate_metadata(data: Dict[str, Any], verbose: bool = False) -> bool:
    """Validate metadata completeness"""
    if "metadata" not in data:
        print("Missing metadata section")
        return False
    
    metadata = data["metadata"]
    required_fields = ["run_timestamp", "pipeline_version", "total_stations"]
    missing_fields = [field for field in required_fields if field not in metadata]
    
    if missing_fields:
        print(f"Missing metadata fields: {missing_fields}")
        return False
    
    if verbose:
        print("Metadata validation:")
        for key, value in metadata.items():
            print(f"  {key}: {value}")
    
    return True


def check_data_quality(data: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
    """Perform data quality checks"""
    quality_report = {
        "total_stations": 0,
        "stations_with_exits": 0,
        "stations_without_exits": [],
        "total_exits": 0,
        "coordinates_out_of_range": [],
        "missing_required_fields": []
    }
    
    if "stations" not in data:
        return quality_report
    
    stations = data["stations"]
    quality_report["total_stations"] = len(stations)
    
    for station in stations:
        # Check exits
        if "exits" in station and station["exits"]:
            quality_report["stations_with_exits"] += 1
            quality_report["total_exits"] += len(station["exits"])
            
            # Check exit coordinates
            for exit in station["exits"]:
                if "lat" in exit and "lng" in exit:
                    lat, lng = exit["lat"], exit["lng"]
                    if not (1.0 <= lat <= 2.0 and 103.0 <= lng <= 105.0):
                        quality_report["coordinates_out_of_range"].append(
                            f"{station.get('official_name', 'Unknown')} - Exit {exit.get('exit_code', 'Unknown')}"
                        )
        else:
            quality_report["stations_without_exits"].append(station.get("official_name", "Unknown"))
        
        # Check required fields
        required_fields = ["official_name", "mrt_codes"]
        for field in required_fields:
            if field not in station or not station[field]:
                quality_report["missing_required_fields"].append(f"{station.get('official_name', 'Unknown')}: {field}")
    
    if verbose:
        print("Data Quality Report:")
        print(f"  Total stations: {quality_report['total_stations']}")
        print(f"  Stations with exits: {quality_report['stations_with_exits']}")
        print(f"  Total exits: {quality_report['total_exits']}")
        if quality_report["stations_without_exits"]:
            print(f"  Stations without exits: {len(quality_report['stations_without_exits'])}")
        if quality_report["coordinates_out_of_range"]:
            print(f"  Coordinates out of range: {len(quality_report['coordinates_out_of_range'])}")
        if quality_report["missing_required_fields"]:
            print(f"  Missing required fields: {len(quality_report['missing_required_fields'])}")
    
    return quality_report


def main():
    """Main validation script"""
    parser = argparse.ArgumentParser(description="Validate MRT pipeline output")
    parser.add_argument(
        "--output-file",
        help="Path to output JSON file to validate"
    )
    parser.add_argument(
        "--schema",
        choices=["stage1", "stage2", "final"],
        help="Schema type to validate against"
    )
    parser.add_argument(
        "--config",
        default="config/pipeline.yaml",
        help="Path to pipeline configuration"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    expected_stations = config["pipeline"]["expected_stations"]
    
    # Find output file if not specified
    if not args.output_file:
        output_dir = project_root / "outputs"
        json_files = list(output_dir.glob("*.json"))
        if not json_files:
            print("No output files found in outputs/ directory")
            return 1
        
        # Use the most recent file
        args.output_file = str(max(json_files, key=os.path.getctime))
        print(f"Using latest output file: {args.output_file}")
    
    # Validate JSON file
    if not validate_json_file(args.output_file):
        return 1
    
    # Load data
    with open(args.output_file, 'r') as f:
        data = json.load(f)
    
    print(f"Validating {args.output_file}")
    
    # Basic validations
    success = True
    
    # Validate metadata
    if not validate_metadata(data, args.verbose):
        success = False
    
    # Validate station count
    if not validate_station_count(data, expected_stations):
        success = False
    
    # Schema validation if specified
    if args.schema:
        if not validate_schema(data, args.schema):
            success = False
        else:
            print(f"Schema validation passed for {args.schema}")
    
    # Data quality check
    quality_report = check_data_quality(data, args.verbose)
    
    if quality_report["coordinates_out_of_range"]:
        print(f"WARNING: {len(quality_report['coordinates_out_of_range'])} coordinates out of Singapore bounds")
    
    if quality_report["missing_required_fields"]:
        print(f"WARNING: {len(quality_report['missing_required_fields'])} missing required fields")
    
    # Final result
    if success:
        print("✅ Output validation passed")
        return 0
    else:
        print("❌ Output validation failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())