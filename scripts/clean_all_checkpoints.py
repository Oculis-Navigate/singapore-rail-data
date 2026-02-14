#!/usr/bin/env python3
"""
Clean up both checkpoint files: enrichment and incremental backup
"""
import json
import os

def clean_checkpoint(data):
    """Clean a checkpoint dict: deduplicate skipped and remove overlap"""
    # Step 1: Deduplicate skipped
    seen_ids = set()
    unique_skipped = []
    for station in data.get('skipped_stations', []):
        station_id = station.get('station_id')
        if station_id and station_id not in seen_ids:
            seen_ids.add(station_id)
            unique_skipped.append(station)
    data['skipped_stations'] = unique_skipped
    
    # Step 2: Remove overlap with successful
    skipped_ids = {s['station_id'] for s in data['skipped_stations']}
    for station_id in skipped_ids:
        if station_id in data.get('stations', {}):
            del data['stations'][station_id]
    
    return data

# Clean enrichment file
enrichment_path = 'outputs/latest/stage2_enrichment.json'
with open(enrichment_path, 'r') as f:
    data = json.load(f)

data = clean_checkpoint(data)

with open(enrichment_path, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False, default=str)

print(f"Cleaned: {enrichment_path}")
print(f"  Successful: {len(data['stations'])}")
print(f"  Skipped: {len(data['skipped_stations'])}")

# Clean and save as incremental backup
bak_path = 'outputs/latest/stage2_incremental.json.bak'
with open(bak_path, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False, default=str)

print(f"Cleaned: {bak_path}")

# Also remove old stage2_incremental.json if it exists
inc_path = 'outputs/latest/stage2_incremental.json'
if os.path.exists(inc_path):
    os.remove(inc_path)
    print(f"Removed: {inc_path}")

print("\n✓ All checkpoint files cleaned - no more duplicates!")
