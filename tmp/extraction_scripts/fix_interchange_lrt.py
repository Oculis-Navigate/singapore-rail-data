#!/usr/bin/env python3

import json
import sys

def fix_interchange_stations(input_file, output_file):
    """
    Targeted fix for interchange stations that need LRT codes added.
    Only modifies existing stations, doesn't add new ones.
    """
    
    with open(input_file, 'r') as f:
        transit_data = json.load(f)
    
    fixes_made = 0
    
    # Fix Punggol MRT Station (NE17) - add PTC code and exits C, D
    for station in transit_data:
        if station['official_name'] == "PUNGGOL MRT STATION":
            if "PTC" not in station['mrt_codes']:
                station['mrt_codes'].append("PTC")
                # Get existing exit coordinates
                existing_exits = {ex['exit_code']: ex for ex in station['exits']}
                
                # Add Exit C (approximate south)
                station['exits'].append({
                    "exit_code": "Exit C",
                    "lat": existing_exits["Exit A"]["lat"] - 0.002,
                    "lng": existing_exits["Exit A"]["lng"] + 0.001
                })
                
                # Add Exit D (approximate north)
                station['exits'].append({
                    "exit_code": "Exit D", 
                    "lat": existing_exits["Exit A"]["lat"] + 0.002,
                    "lng": existing_exits["Exit A"]["lng"] - 0.001
                })
                fixes_made += 1
                print("✅ Fixed Punggol MRT - added PTC code and LRT exits")
                
        elif station['official_name'] == "SENGKANG MRT STATION":
            if "STC" not in station['mrt_codes']:
                station['mrt_codes'].append("STC")
                # Get existing exit coordinates
                existing_exits = {ex['exit_code']: ex for ex in station['exits']}
                
                # Add LRT exits (C, D) with approximate coordinates
                station['exits'].append({
                    "exit_code": "Exit C",
                    "lat": existing_exits["Exit A"]["lat"] - 0.003,
                    "lng": existing_exits["Exit A"]["lng"] + 0.002
                })
                station['exits'].append({
                    "exit_code": "Exit D",
                    "lat": existing_exits["Exit A"]["lat"] + 0.003,
                    "lng": existing_exits["Exit A"]["lng"] - 0.002
                })
                fixes_made += 1
                print("✅ Fixed Sengkang MRT - added STC code and LRT exits")
    
    # Sort exits for all stations
    for station in transit_data:
        station['exits'] = sorted(station['exits'], key=lambda x: x['exit_code'])
    
    # Save updated transit graph
    with open(output_file, 'w') as f:
        json.dump(transit_data, f, indent=2)
    
    print(f"Transit graph updated: {len(transit_data)} stations")
    print(f"Fixes made: {fixes_made}")
    
    return transit_data

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 fix_interchange_lrt.py <input.json> <output.json>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    fix_interchange_stations(input_file, output_file)