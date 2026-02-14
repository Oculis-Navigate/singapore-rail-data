#!/usr/bin/env python3
"""
Temporary cleanup script for Stage 2 checkpoint after BUGFIX-003 consolidation.

This script safely updates the Stage 2 checkpoint to reflect changes from Stage 1:
- Removes A1 station (consolidated into BP6 after Bukit Panjang fix)
- Updates station count from 187 to 186
- Preserves all other station data and failed stations list
- Ensures BP6 remains in failed list for retry

Usage:
    python scripts/cleanup_stage2_checkpoint.py

Safety: Creates a backup before making changes.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime


def cleanup_checkpoint():
    """Clean up Stage 2 checkpoint after Stage 1 consolidation."""
    
    checkpoint_path = Path("outputs/latest/stage2_incremental.json.bak")
    backup_dir = Path("outputs/latest/backups")
    
    # Validate checkpoint exists
    if not checkpoint_path.exists():
        print("❌ Checkpoint file not found: outputs/latest/stage2_incremental.json.bak")
        return 1
    
    # Create backup directory
    backup_dir.mkdir(exist_ok=True)
    
    # Create timestamped backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"stage2_incremental_pre_cleanup_{timestamp}.json"
    shutil.copy(checkpoint_path, backup_path)
    print(f"✅ Created backup: {backup_path}")
    
    # Load checkpoint
    with open(checkpoint_path, 'r') as f:
        checkpoint = json.load(f)
    
    print(f"\n📊 BEFORE CLEANUP:")
    print(f"   Total processed IDs: {len(checkpoint['processed_station_ids'])}")
    print(f"   Successful stations: {len(checkpoint['stations'])}")
    print(f"   Failed stations: {len(checkpoint['failed_stations'])}")
    
    # Check current state
    has_a1_processed = 'A1' in checkpoint['processed_station_ids']
    has_a1_failed = any(f['station_id'] == 'A1' for f in checkpoint['failed_stations'])
    has_a1_success = 'A1' in checkpoint['stations']
    
    print(f"\n🔍 A1 STATION STATUS:")
    print(f"   In processed_station_ids: {has_a1_processed}")
    print(f"   In failed_stations: {has_a1_failed}")
    print(f"   In stations (success): {has_a1_success}")
    
    # Only proceed if A1 exists
    if not has_a1_processed and not has_a1_failed and not has_a1_success:
        print("\n✅ Checkpoint already clean (no A1 found)")
        return 0
    
    # Make modifications
    modified = False
    
    # 1. Remove A1 from processed_station_ids
    if has_a1_processed:
        checkpoint['processed_station_ids'] = [
            sid for sid in checkpoint['processed_station_ids'] if sid != 'A1'
        ]
        print("\n📝 Removed A1 from processed_station_ids")
        modified = True
    
    # 2. Remove A1 from failed_stations
    if has_a1_failed:
        checkpoint['failed_stations'] = [
            f for f in checkpoint['failed_stations'] if f['station_id'] != 'A1'
        ]
        print("📝 Removed A1 from failed_stations")
        modified = True
    
    # 3. Remove A1 from stations (if it somehow got there)
    if has_a1_success:
        del checkpoint['stations']['A1']
        print("📝 Removed A1 from stations dict")
        modified = True
    
    # 4. Verify BP6 is still in failed_stations (it should be re-processed)
    bp6_in_failed = any(f['station_id'] == 'BP6' for f in checkpoint['failed_stations'])
    if bp6_in_failed:
        print("✅ BP6 remains in failed_stations (will be re-processed)")
    else:
        print("⚠️  BP6 not in failed_stations - it may have been processed successfully")
    
    # Save modified checkpoint
    if modified:
        with open(checkpoint_path, 'w') as f:
            json.dump(checkpoint, f, indent=2)
        
        print(f"\n📊 AFTER CLEANUP:")
        print(f"   Total processed IDs: {len(checkpoint['processed_station_ids'])}")
        print(f"   Successful stations: {len(checkpoint['stations'])}")
        print(f"   Failed stations: {len(checkpoint['failed_stations'])}")
        
        print("\n✅ Checkpoint cleanup complete!")
        print(f"\n💡 Next steps:")
        print(f"   1. Run Stage 2 with retry flag: python scripts/run_stage2.py --retry-failed")
        print(f"   2. Only {len(checkpoint['failed_stations'])} stations will be re-processed")
        print(f"   3. BP6 (consolidated Bukit Panjang) will be processed with new data")
    else:
        print("\n✅ No changes needed - checkpoint already clean")
    
    return 0


if __name__ == "__main__":
    exit(cleanup_checkpoint())
