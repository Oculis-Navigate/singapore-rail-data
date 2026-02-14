#!/usr/bin/env python3
"""
Validate output meets iOS app requirements.

Checks:
- File size < 5MB
- Valid JSON structure
- Required metadata fields
- Checksum integrity
- Station count = 187 (or configured count)
"""

import json
import hashlib
import sys
from pathlib import Path


def validate_output(file_path_input: str, expected_count: int = 181):
    """Validate output file"""
    errors = []
    file_path = Path(file_path_input)
    
    # Check file exists
    if not file_path.exists():
        return False, [f"File not found: {file_path}"]
    
    # Check size
    size_bytes = file_path.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    if size_mb > 5:
        errors.append(f"File size {size_mb:.1f}MB exceeds 5MB")
    
    # Parse JSON
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    
    # Check metadata
    if 'metadata' not in data:
        return False, ["Missing metadata section"]
    
    metadata = data['metadata']
    required_fields = [
        'data_version',
        'data_version_iso', 
        'checksum_sha256',
        'station_count'
    ]
    
    for field in required_fields:
        if field not in metadata:
            errors.append(f"Missing metadata field: {field}")
    
    # Check stations
    if 'stations' not in data:
        return False, ["Missing stations section"]
    
    stations = data['stations']
    if len(stations) != expected_count:
        errors.append(f"Station count: got {len(stations)}, expected {expected_count}")
    
    # Verify checksum
    if 'checksum_sha256' in metadata:
        # Recalculate checksum (exclude checksum field itself)
        metadata_copy = metadata.copy()
        del metadata_copy['checksum_sha256']
        data_copy = {**data, 'metadata': metadata_copy}
        json_str = json.dumps(data_copy, separators=(',', ':'), sort_keys=True)
        calculated = hashlib.sha256(json_str.encode('utf-8')).hexdigest()
        
        if calculated != metadata['checksum_sha256']:
            errors.append(f"Checksum mismatch: calculated {calculated[:16]}... vs stored {metadata['checksum_sha256'][:16]}...")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def main():
    if len(sys.argv) < 2:
        print("Usage: validate_mobile_output.py <stage3_final.json> [expected_count]")
        print("  expected_count: Number of stations expected (default: 181)")
        sys.exit(1)
    
    file_path = sys.argv[1]
    expected_count = int(sys.argv[2]) if len(sys.argv) > 2 else 181
    is_valid, errors = validate_output(file_path, expected_count)
    
    if is_valid:
        print(f"✓ Validation passed: {file_path}")
        sys.exit(0)
    else:
        print(f"✗ Validation failed: {file_path}")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)


if __name__ == '__main__':
    main()
