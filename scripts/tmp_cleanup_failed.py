#!/usr/bin/env python3
"""
Cleanup script for Stage 2 checkpoint files.

Removes duplicate entries from failed_stations list where a station
has both a failure record and a successful extraction in the stations dict.

Also updates metadata counts to reflect the cleaned data.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List


def load_checkpoint(path: str) -> Dict[str, Any]:
    """Load checkpoint file."""
    with open(path, 'r') as f:
        return json.load(f)


def save_checkpoint(path: str, data: Dict[str, Any]) -> None:
    """Save checkpoint file."""
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✓ Saved cleaned checkpoint to: {path}")


def cleanup_failed_stations(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove duplicate failed station entries.
    
    A station is considered duplicate if:
    1. It exists in failed_stations list
    2. It also exists in stations dict with extraction_result == "success"
    """
    stations = data.get('stations', {})
    failed_stations = data.get('failed_stations', [])
    
    if not failed_stations:
        print("No failed_stations list found, nothing to clean")
        return data
    
    # Find duplicates (failed entries for stations that actually succeeded)
    duplicates = []
    kept_failures = []
    
    for failure in failed_stations:
        station_id = failure.get('station_id')
        
        if station_id in stations:
            station_data = stations[station_id]
            if station_data.get('extraction_result') == 'success':
                duplicates.append({
                    'station_id': station_id,
                    'official_name': station_data.get('official_name', 'Unknown'),
                    'reason': failure.get('error', 'Unknown error')
                })
                continue  # Skip adding to kept_failures
        
        kept_failures.append(failure)
    
    # Report findings
    print(f"\n📊 Cleanup Report:")
    print(f"   Original failed_stations count: {len(failed_stations)}")
    print(f"   Duplicate entries removed: {len(duplicates)}")
    print(f"   Remaining failures: {len(kept_failures)}")
    
    if duplicates:
        print(f"\n🗑️  Removed duplicate entries:")
        for dup in duplicates:
            print(f"   - {dup['station_id']}: {dup['official_name']}")
    
    # Update data
    data['failed_stations'] = kept_failures
    
    # Update metadata if it exists
    if 'metadata' in data:
        metadata = data['metadata']
        if 'failed_stations' in metadata:
            metadata['failed_stations'] = len(kept_failures)
        if 'completed_stations' in metadata:
            successful_count = sum(
                1 for s in stations.values() 
                if s.get('extraction_result') == 'success'
            )
            metadata['completed_stations'] = successful_count
    
    return data


def main():
    if len(sys.argv) < 2:
        checkpoint_path = "outputs/latest/stage2_incremental.json.bak"
    else:
        checkpoint_path = sys.argv[1]
    
    path = Path(checkpoint_path)
    if not path.exists():
        print(f"❌ Error: File not found: {checkpoint_path}")
        print(f"\nUsage: python cleanup_stage2_failed.py [checkpoint_path]")
        print(f"   Default: outputs/latest/stage2_incremental.json.bak")
        sys.exit(1)
    
    print(f"Loading checkpoint: {checkpoint_path}")
    data = load_checkpoint(checkpoint_path)
    
    # Clean up failed stations
    data = cleanup_failed_stations(data)
    
    # Save back to same file
    save_checkpoint(checkpoint_path, data)
    
    print(f"\n✅ Cleanup complete!")
    print(f"   Checkpoint now has {len(data.get('failed_stations', []))} failed stations")


if __name__ == "__main__":
    main()
