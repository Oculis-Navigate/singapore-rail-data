#!/usr/bin/env python3
"""
Temporary script to deduplicate skipped_stations in stage2 checkpoint
"""
import json
import sys
from pathlib import Path

def deduplicate_skipped_stations(checkpoint_path: str):
    """Remove duplicate entries from skipped_stations list"""
    
    with open(checkpoint_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    original_count = len(data.get('skipped_stations', []))
    
    # Deduplicate by station_id
    seen_ids = set()
    unique_skipped = []
    
    for station in data.get('skipped_stations', []):
        station_id = station.get('station_id')
        if station_id and station_id not in seen_ids:
            seen_ids.add(station_id)
            unique_skipped.append(station)
    
    new_count = len(unique_skipped)
    removed = original_count - new_count
    
    if removed > 0:
        print(f"Removed {removed} duplicate entries")
        print(f"Original: {original_count}, Now: {new_count}")
        print("\nUnique skipped stations:")
        for s in unique_skipped:
            print(f"  - {s.get('official_name', s.get('station_id', 'unknown'))}")
        
        # Update data
        data['skipped_stations'] = unique_skipped
        
        # Backup original
        backup_path = checkpoint_path + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        print(f"\nBackup saved to: {backup_path}")
        
        # Save cleaned version
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        print(f"Cleaned checkpoint saved to: {checkpoint_path}")
    else:
        print(f"No duplicates found. Total skipped: {original_count}")
    
    return removed

if __name__ == "__main__":
    checkpoint_path = sys.argv[1] if len(sys.argv) > 1 else 'outputs/latest/stage2_enrichment.json'
    
    if not Path(checkpoint_path).exists():
        print(f"Checkpoint not found: {checkpoint_path}")
        sys.exit(1)
    
    deduplicate_skipped_stations(checkpoint_path)
