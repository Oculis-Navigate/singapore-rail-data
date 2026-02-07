#!/usr/bin/env python3
"""
MRT Enrichment Data Validation Script
Run this to verify batch files meet schema standards before merging.

Usage: python3 validate_batches.py [batch_file.json]
If no file specified, validates all batch*.json files in tmp/extraction_scripts/
"""

import json
import re
import sys
import glob
from pathlib import Path

# Schema definitions from SCHEMA_VERSION.md
REQUIRED_STATION_FIELDS = [
    'official_name', 'station_code', 'lines', 'exits', 
    'accessibility_notes', 'last_updated', 'source_url', 'extraction_confidence'
]

REQUIRED_EXIT_FIELDS = [
    'exit_code', 'platforms', 'accessibility', 'bus_stops', 'nearby_landmarks'
]

REQUIRED_PLATFORM_FIELDS = [
    'platform_code', 'towards_code', 'line_code'
]

VALID_ACCESSIBILITY = [
    'wheelchair_accessible', 'barrier_free', 'lift', 'escalator', 
    'stairs_only', 'tactile_guidance', 'accessible_toilet'
]

VALID_LINE_CODES = ['NS', 'EW', 'CC', 'DT', 'NE', 'TE', 'BP', 'SE', 'PE', 'SW', 'PW', 'SEL', 'SWL', 'PEL', 'PWL']
VALID_LINE_NAMES = ['NSL', 'EWL', 'CCL', 'DTL', 'NEL', 'TEL', 'BPL', 'SKL', 'PGL', 'SEL', 'SWL', 'PEL', 'PWL']

FORBIDDEN_EXIT_FIELDS = ['has_barrier_free_access']  # Removed from schema v1.0


def validate_station_code(code):
    """Must match pattern: ^[A-Z]{2,3}\d{0,2}$ (supports MRT and LRT codes)"""
    # MRT: NS1, EW12, CC1, DT35, NE17, TE29 (2 letters + 1-2 digits)
    # LRT Hub: STC, PTC (3 letters, no digits)
    # LRT Loop: SE1, SW5, PE7, PW3 (2 letters + 1 digit)
    return bool(re.match(r'^[A-Z]{2,3}\d{0,2}$', code))


def validate_bus_stop_code(code):
    """Must be exactly 5 digits"""
    return bool(re.match(r'^\d{5}$', str(code)))


def validate_timestamp(ts):
    """ISO8601 format: YYYY-MM-DDTHH:MM:SS"""
    return bool(re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', ts))


def validate_station(station_name, station_data):
    """Validate a single station entry"""
    issues = []
    
    # Check required fields
    for field in REQUIRED_STATION_FIELDS:
        if field not in station_data:
            issues.append(f"Missing required field: {field}")
    
    # Check station code format
    if 'station_code' in station_data:
        if not validate_station_code(station_data['station_code']):
            issues.append(f"Invalid station_code format: {station_data['station_code']}")
    
    # Check lines array
    if 'lines' in station_data:
        if not isinstance(station_data['lines'], list):
            issues.append("Field 'lines' must be an array")
        else:
            for line in station_data['lines']:
                if line not in VALID_LINE_NAMES:
                    issues.append(f"Invalid line name: {line}")
    
    # Check accessibility_notes is array
    if 'accessibility_notes' in station_data:
        if not isinstance(station_data['accessibility_notes'], list):
            issues.append("Field 'accessibility_notes' must be an array")
    
    # Check timestamp format
    if 'last_updated' in station_data:
        if not validate_timestamp(station_data['last_updated']):
            issues.append(f"Invalid timestamp format: {station_data['last_updated']}")
    
    # Check extraction_confidence
    if 'extraction_confidence' in station_data:
        if station_data['extraction_confidence'] not in ['high', 'medium', 'low']:
            issues.append(f"Invalid extraction_confidence: {station_data['extraction_confidence']}")
    
    # Check exits
    if 'exits' in station_data:
        if not isinstance(station_data['exits'], list):
            issues.append("Field 'exits' must be an array")
        else:
            for i, exit in enumerate(station_data['exits']):
                exit_id = exit.get('exit_code', f'#{i}')
                exit_issues = validate_exit(exit)
                for issue in exit_issues:
                    issues.append(f"Exit {exit_id}: {issue}")
    
    return issues


def validate_exit(exit_data):
    """Validate a single exit entry"""
    issues = []
    
    # Check required fields
    for field in REQUIRED_EXIT_FIELDS:
        if field not in exit_data:
            issues.append(f"Missing required field: {field}")
    
    # Check for forbidden fields
    for field in FORBIDDEN_EXIT_FIELDS:
        if field in exit_data:
            issues.append(f"Forbidden field '{field}' found - must be removed")
    
    # Check accessibility values
    if 'accessibility' in exit_data:
        if not isinstance(exit_data['accessibility'], list):
            issues.append("Field 'accessibility' must be an array")
        else:
            for acc in exit_data['accessibility']:
                if acc not in VALID_ACCESSIBILITY:
                    issues.append(f"Invalid accessibility value: '{acc}'")
    
    # Check platforms
    if 'platforms' in exit_data:
        if not isinstance(exit_data['platforms'], list):
            issues.append("Field 'platforms' must be an array")
        else:
            for platform in exit_data['platforms']:
                platform_issues = validate_platform(platform)
                for issue in platform_issues:
                    issues.append(f"Platform: {issue}")
    
    # Check bus_stops
    if 'bus_stops' in exit_data:
        if not isinstance(exit_data['bus_stops'], list):
            issues.append("Field 'bus_stops' must be an array")
        else:
            for bus_stop in exit_data['bus_stops']:
                if 'code' in bus_stop:
                    if not validate_bus_stop_code(bus_stop['code']):
                        issues.append(f"Invalid bus_stop code: '{bus_stop['code']}'")
    
    # Check nearby_landmarks
    if 'nearby_landmarks' in exit_data:
        if not isinstance(exit_data['nearby_landmarks'], list):
            issues.append("Field 'nearby_landmarks' must be an array")
    
    return issues


def validate_platform(platform_data):
    """Validate a single platform entry"""
    issues = []
    
    # Check required fields
    for field in REQUIRED_PLATFORM_FIELDS:
        if field not in platform_data:
            issues.append(f"Missing required field: {field}")
    
    # Check line_code
    if 'line_code' in platform_data:
        if platform_data['line_code'] not in VALID_LINE_CODES:
            issues.append(f"Invalid line_code: '{platform_data['line_code']}'")
    
    # Check towards_code (should be a station code or null for terminus)
    if 'towards_code' in platform_data:
        if platform_data['towards_code'] is not None and not validate_station_code(platform_data['towards_code']):
            issues.append(f"Invalid towards_code: '{platform_data['towards_code']}'")
    
    return issues


def validate_batch(file_path):
    """Validate an entire batch file"""
    print(f"\n{'='*70}")
    print(f"Validating: {file_path}")
    print('='*70)
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return False
    
    # Check metadata
    if 'metadata' not in data:
        print("❌ Missing 'metadata' section")
        return False
    
    if 'stations' not in data:
        print("❌ Missing 'stations' section")
        return False
    
    metadata = data['metadata']
    stations = data['stations']
    
    print(f"\n📊 Metadata:")
    print(f"   Description: {metadata.get('description', 'N/A')}")
    print(f"   Total stations: {metadata.get('total_stations', 'N/A')}")
    print(f"   Actual stations: {len(stations)}")
    
    if metadata.get('total_stations') != len(stations):
        print(f"   ⚠️  WARNING: Metadata count doesn't match actual count!")
    
    # Validate each station
    all_issues = []
    # Handle both dict and list formats
    if isinstance(stations, dict):
        station_iter = stations.items()
    elif isinstance(stations, list):
        station_iter = [(s.get('official_name', 'UNKNOWN'), s) for s in stations]
    else:
        print("❌ Invalid stations format (must be dict or list)")
        return False
    
    for station_name, station_data in station_iter:
        issues = validate_station(station_name, station_data)
        if issues:
            all_issues.append((station_name, issues))
            print(f"\n❌ {station_name}:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            print(f"✅ {station_name}")
    
    # Summary
    print(f"\n{'='*70}")
    if all_issues:
        total_issues = sum(len(issues) for _, issues in all_issues)
        print(f"❌ VALIDATION FAILED: {len(all_issues)} stations with {total_issues} issues")
        return False
    else:
        print(f"✅ VALIDATION PASSED: All {len(stations)} stations valid")
        return True


def main():
    if len(sys.argv) > 1:
        # Validate specific file
        files = sys.argv[1:]
    else:
        # Validate all batch files
        script_dir = Path(__file__).parent
        files = glob.glob(str(script_dir / 'batch*_enrichment_data.json'))
        files.sort()
    
    if not files:
        print("No batch files found to validate!")
        print("Usage: python3 validate_batches.py [file1.json] [file2.json] ...")
        sys.exit(1)
    
    results = []
    for file_path in files:
        results.append((file_path, validate_batch(file_path)))
    
    # Final summary
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print('='*70)
    all_passed = True
    for file_path, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {file_path}")
        if not passed:
            all_passed = False
    
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
