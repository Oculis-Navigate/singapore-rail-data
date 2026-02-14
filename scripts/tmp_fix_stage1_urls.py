#!/usr/bin/env python3
"""
Fix Stage 1 URLs that have incorrect casing.

Updates stage1_deterministic.json with correct Fandom URLs for stations
that have manual mappings in config but got incorrect auto-generated URLs.
"""

import json
import sys
from pathlib import Path


def fix_stage1_urls(stage1_path: str) -> None:
    """Fix URLs in stage1 output based on manual mappings."""
    
    # Load config to get manual mappings
    config_path = Path("config/pipeline.yaml")
    if not config_path.exists():
        print(f"❌ Config not found: {config_path}")
        sys.exit(1)
    
    import yaml
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    manual_mappings = config.get('pipeline', {}).get('url_mappings', {})
    
    # Load stage1 output
    with open(stage1_path) as f:
        data = json.load(f)
    
    stations = data.get('stations', [])
    fixes_applied = []
    
    for station in stations:
        display_name = station.get('display_name', '')
        current_url = station.get('fandom_url', '')
        
        # Check if this station has a manual mapping (case-insensitive)
        for mapped_name, correct_url in manual_mappings.items():
            if display_name.lower() == mapped_name.lower():
                if current_url != correct_url:
                    fixes_applied.append({
                        'station_id': station['station_id'],
                        'display_name': display_name,
                        'old_url': current_url,
                        'new_url': correct_url
                    })
                    station['fandom_url'] = correct_url
                break
    
    # Save updated stage1 output
    with open(stage1_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Report
    print(f"\n📊 URL Fix Report:")
    print(f"   Stations checked: {len(stations)}")
    print(f"   URLs fixed: {len(fixes_applied)}")
    
    if fixes_applied:
        print(f"\n🔧 Fixed URLs:")
        for fix in fixes_applied:
            print(f"   {fix['station_id']}: {fix['display_name']}")
            print(f"      From: {fix['old_url']}")
            print(f"      To:   {fix['new_url']}")
    
    print(f"\n✅ Updated {stage1_path}")


if __name__ == "__main__":
    stage1_path = sys.argv[1] if len(sys.argv) > 1 else "outputs/latest/stage1_deterministic.json"
    fix_stage1_urls(stage1_path)
