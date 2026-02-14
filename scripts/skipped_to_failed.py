#!/usr/bin/env python3
"""
Convert the 8 skipped stations to failed stations (for retry)
"""
import json
from datetime import datetime

# Load checkpoint
with open('outputs/latest/stage2_enrichment.json', 'r') as f:
    data = json.load(f)

print(f"Before: {len(data['stations'])} successful, {len(data['failed_stations'])} failed, {len(data['skipped_stations'])} skipped")

# Move skipped to failed
for station in data['skipped_stations']:
    # Add to failed_stations as non-permanent (so it can be retried)
    data['failed_stations'].append({
        "station_id": station['station_id'],
        "error": "Station not found on Fandom - needs verification",
        "permanent": False,  # Can be retried
        "timestamp": datetime.utcnow().isoformat()
    })
    print(f"Moved to failed: {station['official_name']} ({station['station_id']})")

# Clear skipped list
data['skipped_stations'] = []

# Save
with open('outputs/latest/stage2_enrichment.json', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False, default=str)

print(f"\nAfter: {len(data['stations'])} successful, {len(data['failed_stations'])} failed, {len(data['skipped_stations'])} skipped")

# Also update backup
with open('outputs/latest/stage2_incremental.json.bak', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False, default=str)

print("Updated backup file as well")
