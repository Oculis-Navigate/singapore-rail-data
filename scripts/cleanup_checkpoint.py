#!/usr/bin/env python3
"""
Clean up checkpoint: remove stations from successful list that are also in skipped,
keeping them only in skipped so they'll be reprocessed.
"""
import json
import sys
from pathlib import Path

def cleanup_checkpoint(checkpoint_path: str):
    """Remove overlapping stations from successful list, keep only in skipped"""
    
    with open(checkpoint_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Find stations in both lists
    skipped_ids = {s['station_id'] for s in data['skipped_stations']}
    success_ids = set(data['stations'].keys())
    overlap = skipped_ids & success_ids
    
    print(f"Stations in both lists: {overlap}")
    
    if not overlap:
        print("No overlap found, nothing to clean up")
        return
    
    # Remove from successful stations
    for station_id in overlap:
        if station_id in data['stations']:
            station_name = data['stations'][station_id].get('official_name', station_id)
            del data['stations'][station_id]
            print(f"Removed from successful: {station_name} ({station_id})")
    
    # Remove from processed_station_ids so they'll be reprocessed (if field exists)
    if 'processed_station_ids' in data:
        original_processed_count = len(data['processed_station_ids'])
        data['processed_station_ids'] = [sid for sid in data['processed_station_ids'] if sid not in overlap]
        new_processed_count = len(data['processed_station_ids'])
        print(f"\nUpdated processed_station_ids: {original_processed_count} -> {new_processed_count}")
    else:
        print("\nNote: No processed_station_ids field in this checkpoint (enrichment format)")
    
    # Save backup
    backup_path = checkpoint_path + '.backup2'
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nBackup saved to: {backup_path}")
    
    # Save cleaned version
    with open(checkpoint_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"Cleaned checkpoint saved to: {checkpoint_path}")
    
    # Summary
    print(f"\nSummary:")
    print(f"  Successful: {len(data['stations'])}")
    print(f"  Skipped: {len(data['skipped_stations'])}")
    print(f"  Processed IDs: {len(data['processed_station_ids'])}")

if __name__ == "__main__":
    checkpoint_path = sys.argv[1] if len(sys.argv) > 1 else 'outputs/latest/stage2_enrichment.json'
    
    if not Path(checkpoint_path).exists():
        print(f"Checkpoint not found: {checkpoint_path}")
        sys.exit(1)
    
    cleanup_checkpoint(checkpoint_path)
