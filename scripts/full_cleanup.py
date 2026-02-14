#!/usr/bin/env python3
"""
Full cleanup: deduplicate skipped_stations AND remove overlap with successful stations
"""
import json
import sys
from pathlib import Path

def full_cleanup(checkpoint_path: str):
    with open(checkpoint_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("=== Step 1: Deduplicate skipped_stations ===")
    seen_ids = set()
    unique_skipped = []
    duplicates_removed = 0
    
    for station in data.get('skipped_stations', []):
        station_id = station.get('station_id')
        if station_id and station_id not in seen_ids:
            seen_ids.add(station_id)
            unique_skipped.append(station)
        else:
            duplicates_removed += 1
    
    data['skipped_stations'] = unique_skipped
    print(f"Removed {duplicates_removed} duplicate skipped entries")
    print(f"Skipped count: {len(data['skipped_stations'])}")
    
    print("\n=== Step 2: Remove overlap with successful stations ===")
    skipped_ids = {s['station_id'] for s in data['skipped_stations']}
    success_ids = set(data['stations'].keys())
    overlap = skipped_ids & success_ids
    
    print(f"Stations in both lists: {overlap}")
    for station_id in overlap:
        if station_id in data['stations']:
            station_name = data['stations'][station_id].get('official_name', station_id)
            del data['stations'][station_id]
            print(f"Removed from successful: {station_name} ({station_id})")
    
    # Save backup
    backup_path = checkpoint_path + '.full_backup'
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nBackup saved to: {backup_path}")
    
    # Save cleaned
    with open(checkpoint_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"Cleaned checkpoint saved to: {checkpoint_path}")
    
    # Final summary
    print(f"\n=== FINAL STATE ===")
    print(f"Successful: {len(data['stations'])}")
    print(f"Skipped: {len(data['skipped_stations'])}")
    print("\nSkipped stations (all will be reprocessed):")
    for s in data['skipped_stations']:
        print(f"  - {s['official_name']} ({s['station_id']})")
    
    # Verify no overlap
    final_overlap = {s['station_id'] for s in data['skipped_stations']} & set(data['stations'].keys())
    if final_overlap:
        print(f"\nERROR: Still have overlap: {final_overlap}")
    else:
        print("\n✓ No overlap - all clean!")

if __name__ == "__main__":
    checkpoint_path = sys.argv[1] if len(sys.argv) > 1 else 'outputs/latest/stage2_enrichment.json'
    
    if not Path(checkpoint_path).exists():
        print(f"Checkpoint not found: {checkpoint_path}")
        sys.exit(1)
    
    full_cleanup(checkpoint_path)
