#!/usr/bin/env python3
"""
Cleanup script to remove duplicate failure entries from Stage 2 checkpoint files.

Usage:
    python scripts/cleanup_stage2_duplicates.py
    python scripts/cleanup_stage2_duplicates.py --checkpoint outputs/latest/stage2_enrichment.json
"""

import json
import argparse
from pathlib import Path
from collections import OrderedDict


def remove_duplicate_failures(checkpoint_path: str):
    """Remove duplicate failure entries and successful stations from failed list."""
    
    print(f"Processing: {checkpoint_path}")
    
    with open(checkpoint_path, 'r') as f:
        data = json.load(f)
    
    original_count = len(data.get('failed_stations', []))
    successful_ids = set(data.get('stations', {}).keys())
    
    # Use OrderedDict to keep only the last occurrence of each station_id
    seen = OrderedDict()
    for failure in data.get('failed_stations', []):
        station_id = failure['station_id']
        seen[station_id] = failure  # This overwrites, keeping the last one
    
    # Remove stations that are now successful (they were retried and passed)
    for station_id in list(seen.keys()):
        if station_id in successful_ids:
            del seen[station_id]
    
    # Convert back to list
    data['failed_stations'] = list(seen.values())
    
    new_count = len(data['failed_stations'])
    removed = original_count - new_count
    
    if removed > 0:
        # Backup original
        backup_path = checkpoint_path + '.duplicate_backup'
        with open(backup_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"  Backup created: {backup_path}")
        
        # Write cleaned file
        with open(checkpoint_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"  Removed {removed} entries (duplicates + now-successful stations)")
        print(f"  Failed stations: {original_count} -> {new_count}")
        
        # Update metadata if it exists
        if 'metadata' in data:
            successful = len(data.get('stations', {}))
            failed = new_count
            total = successful + failed
            data['metadata']['successful'] = successful
            data['metadata']['failed'] = failed
            data['metadata']['total_stations'] = total
            
            with open(checkpoint_path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"  Updated metadata: {successful} successful, {failed} failed, {total} total")
    else:
        print(f"  No duplicates found")
    
    return removed


def main():
    parser = argparse.ArgumentParser(description='Remove duplicate failure entries from Stage 2 checkpoints')
    parser.add_argument('--checkpoint', help='Path to specific checkpoint file to clean')
    args = parser.parse_args()
    
    total_removed = 0
    
    if args.checkpoint:
        # Clean specific file
        if Path(args.checkpoint).exists():
            total_removed += remove_duplicate_failures(args.checkpoint)
        else:
            print(f"File not found: {args.checkpoint}")
    else:
        # Clean all checkpoint files in outputs/latest
        checkpoint_dir = Path('outputs/latest')
        
        files_to_clean = [
            checkpoint_dir / 'stage2_enrichment.json',
            checkpoint_dir / 'stage2_incremental.json.bak',
        ]
        
        for checkpoint_file in files_to_clean:
            if checkpoint_file.exists():
                total_removed += remove_duplicate_failures(str(checkpoint_file))
                print()
    
    print(f"\nTotal duplicates removed: {total_removed}")


if __name__ == '__main__':
    main()
