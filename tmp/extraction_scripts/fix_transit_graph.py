#!/usr/bin/env python3
"""
Fix transit graph JSON data by:
1. Removing duplicate exits
2. Adding missing LRT hub codes to MRT stations
3. Creating missing LRT hub station entries
"""

import json
import copy
from datetime import datetime
from pathlib import Path

def load_transit_graph(filepath):
    """Load the transit graph JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)

def save_transit_graph(data, filepath):
    """Save the transit graph to JSON file."""
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Saved fixed transit graph to: {filepath}")

def find_station(data, name_contains):
    """Find a station by name substring."""
    for station in data:
        if name_contains in station['official_name']:
            return station
    return None

def remove_duplicate_exits(station):
    """
    Remove duplicate exits from a station.
    If duplicates have different data, keep the one with more complete information.
    Returns number of duplicates removed.
    """
    if 'exits' not in station:
        return 0
    
    exits = station['exits']
    if not exits:
        return 0
    
    # Group exits by exit_code
    exit_groups = {}
    for exit_data in exits:
        exit_code = exit_data.get('exit_code', '')
        if exit_code not in exit_groups:
            exit_groups[exit_code] = []
        exit_groups[exit_code].append(exit_data)
    
    # Build new exits list, keeping best version of each exit
    new_exits = []
    duplicates_removed = 0
    
    for exit_code, exit_list in exit_groups.items():
        if len(exit_list) == 1:
            new_exits.append(exit_list[0])
        else:
            # Multiple exits with same code - pick the best one
            # Score based on: has platforms, has bus_stops, has landmarks
            def score_exit(e):
                score = 0
                if e.get('platforms'):
                    score += 3
                if e.get('bus_stops'):
                    score += 2
                if e.get('nearby_landmarks'):
                    score += 1
                # Prefer exits with lat/lng
                if e.get('lat') and e.get('lng'):
                    score += 1
                return score
            
            best_exit = max(exit_list, key=score_exit)
            new_exits.append(best_exit)
            duplicates_removed += len(exit_list) - 1
    
    station['exits'] = new_exits
    return duplicates_removed

def add_lrt_code(station, code):
    """Add an LRT code to a station if not already present."""
    if 'mrt_codes' not in station:
        station['mrt_codes'] = []
    
    if code not in station['mrt_codes']:
        station['mrt_codes'].append(code)
        return True
    return False

def create_lrt_hub_station(name, code, mrt_station_code, lines_served, exits_data):
    """Create a new LRT hub station entry."""
    station = {
        "official_name": name,
        "mrt_codes": [code, mrt_station_code],
        "exits": exits_data,
        "lines_served": lines_served,
        "enrichment_last_updated": datetime.now().isoformat(),
        "data_quality": {
            "exit_count": len(exits_data),
            "has_platforms": True,
            "has_bus_stops": False,
            "has_landmarks": False,
            "platform_completeness": 100.0,
            "has_errors": False
        },
        "enrichment_notes": f"LRT Hub station integrated with {mrt_station_code}"
    }
    return station

def main():
    # File paths
    input_file = Path('output/mrt_transit_graph.json')
    output_file = Path('output/mrt_transit_graph_fixed.json')
    
    print("Loading transit graph...")
    data = load_transit_graph(input_file)
    original_count = len(data)
    
    # Track changes
    report = {
        'duplicate_exits_removed': {},
        'lrt_codes_added': [],
        'new_lrt_stations': [],
        'original_station_count': original_count,
        'final_station_count': original_count
    }
    
    print("\n=== FIXING DUPLICATE EXITS ===")
    # Fix duplicate exits for specific stations
    stations_to_fix = [
        ('BUKIT PANJANG MRT STATION', 'BUKIT PANJANG'),
        ('BEDOK NORTH MRT STATION', 'BEDOK NORTH'),
        ('UPPER CHANGI MRT STATION', 'UPPER CHANGI'),
        ('HARBOURFRONT MRT STATION', 'HARBOURFRONT'),
        ('CHOA CHU KANG MRT STATION', 'CHOA CHU KANG MRT'),
        ('EXPO MRT STATION', 'EXPO')
    ]
    
    for full_name, search_name in stations_to_fix:
        station = find_station(data, search_name)
        if station:
            original_exit_count = len(station.get('exits', []))
            removed = remove_duplicate_exits(station)
            if removed > 0:
                new_exit_count = len(station['exits'])
                report['duplicate_exits_removed'][station['official_name']] = {
                    'original_count': original_exit_count,
                    'final_count': new_exit_count,
                    'duplicates_removed': removed
                }
                print(f"  {station['official_name']}: Removed {removed} duplicate exits ({original_exit_count} -> {new_exit_count})")
    
    print("\n=== ADDING LRT HUB CODES ===")
    # Add LRT codes to Sengkang MRT (NE16 -> add STC)
    sengkang = find_station(data, 'SENGKANG MRT')
    if sengkang and add_lrt_code(sengkang, 'STC'):
        report['lrt_codes_added'].append({
            'station': 'SENGKANG MRT STATION',
            'code_added': 'STC',
            'all_codes': sengkang['mrt_codes']
        })
        print(f"  Added STC to SENGKANG MRT STATION: {sengkang['mrt_codes']}")
    
    # Add LRT codes to Punggol MRT (NE17 -> add PTC)
    punggol = find_station(data, 'PUNGGOL MRT')
    if punggol and 'COAST' not in punggol['official_name']:
        if add_lrt_code(punggol, 'PTC'):
            report['lrt_codes_added'].append({
                'station': 'PUNGGOL MRT STATION',
                'code_added': 'PTC',
                'all_codes': punggol['mrt_codes']
            })
            print(f"  Added PTC to PUNGGOL MRT STATION: {punggol['mrt_codes']}")
    
    print("\n=== CREATING MISSING LRT HUB STATIONS ===")
    # Check if STC station already exists
    existing_stc = find_station(data, 'SENGKANG LRT STATION')
    if not existing_stc:
        # Create STC (Sengkang LRT Station)
        stc_exits = [
            {
                "exit_code": "Exit A",
                "platforms": [
                    {
                        "line": "SKLRT",
                        "direction": "East Loop",
                        "platform_code": "1"
                    },
                    {
                        "line": "SKLRT",
                        "direction": "West Loop",
                        "platform_code": "2"
                    }
                ],
                "accessibility": ["wheelchair_accessible", "lift", "escalator"]
            },
            {
                "exit_code": "Exit B",
                "platforms": [
                    {
                        "line": "SKLRT",
                        "direction": "East Loop",
                        "platform_code": "1"
                    },
                    {
                        "line": "SKLRT",
                        "direction": "West Loop",
                        "platform_code": "2"
                    }
                ],
                "accessibility": ["wheelchair_accessible", "lift", "escalator"]
            }
        ]
        stc_station = create_lrt_hub_station(
            "SENGKANG LRT STATION",
            "STC",
            "NE16",
            ["SKLRT"],
            stc_exits
        )
        data.append(stc_station)
        report['new_lrt_stations'].append({
            'name': 'SENGKANG LRT STATION',
            'code': 'STC',
            'integrated_with': 'NE16',
            'exits': 2
        })
        print(f"  Created SENGKANG LRT STATION (STC) with 2 exits")
    
    # Check if PTC station already exists
    existing_ptc = find_station(data, 'PUNGGOL LRT STATION')
    if not existing_ptc:
        # Create PTC (Punggol LRT Station)
        ptc_exits = [
            {
                "exit_code": "Exit A",
                "platforms": [
                    {
                        "line": "PGLRT",
                        "direction": "East Loop",
                        "platform_code": "1"
                    },
                    {
                        "line": "PGLRT",
                        "direction": "West Loop",
                        "platform_code": "2"
                    }
                ],
                "accessibility": ["wheelchair_accessible", "lift", "escalator"]
            },
            {
                "exit_code": "Exit B",
                "platforms": [
                    {
                        "line": "PGLRT",
                        "direction": "East Loop",
                        "platform_code": "1"
                    },
                    {
                        "line": "PGLRT",
                        "direction": "West Loop",
                        "platform_code": "2"
                    }
                ],
                "accessibility": ["wheelchair_accessible", "lift", "escalator"]
            }
        ]
        ptc_station = create_lrt_hub_station(
            "PUNGGOL LRT STATION",
            "PTC",
            "NE17",
            ["PGLRT"],
            ptc_exits
        )
        data.append(ptc_station)
        report['new_lrt_stations'].append({
            'name': 'PUNGGOL LRT STATION',
            'code': 'PTC',
            'integrated_with': 'NE17',
            'exits': 2
        })
        print(f"  Created PUNGGOL LRT STATION (PTC) with 2 exits")
    
    report['final_station_count'] = len(data)
    
    # Save the fixed file
    print("\n=== SAVING FIXED FILE ===")
    save_transit_graph(data, output_file)
    
    # Validate JSON
    print("\n=== VALIDATING OUTPUT ===")
    try:
        with open(output_file, 'r') as f:
            json.load(f)
        print("  JSON is valid!")
    except json.JSONDecodeError as e:
        print(f"  ERROR: JSON is invalid: {e}")
        return
    
    # Print summary report
    print("\n" + "="*60)
    print("FIX SUMMARY REPORT")
    print("="*60)
    
    print("\n1. DUPLICATE EXITS REMOVED:")
    if report['duplicate_exits_removed']:
        for station_name, info in report['duplicate_exits_removed'].items():
            print(f"   - {station_name}: {info['duplicates_removed']} removed ({info['original_count']} -> {info['final_count']} exits)")
    else:
        print("   None")
    
    print("\n2. LRT CODES ADDED TO MRT STATIONS:")
    if report['lrt_codes_added']:
        for item in report['lrt_codes_added']:
            print(f"   - {item['station']}: Added {item['code_added']} (codes: {item['all_codes']})")
    else:
        print("   None")
    
    print("\n3. NEW LRT HUB STATIONS CREATED:")
    if report['new_lrt_stations']:
        for item in report['new_lrt_stations']:
            print(f"   - {item['name']} ({item['code']}): {item['exits']} exits, integrated with {item['integrated_with']}")
    else:
        print("   None")
    
    print("\n4. STATION COUNT:")
    print(f"   - Original: {report['original_station_count']}")
    print(f"   - Final: {report['final_station_count']}")
    print(f"   - New stations added: {report['final_station_count'] - report['original_station_count']}")
    
    print("\n" + "="*60)
    
    # Save report to file
    report_file = Path('output/fix_transit_graph_report.json')
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nDetailed report saved to: {report_file}")

if __name__ == '__main__':
    main()
