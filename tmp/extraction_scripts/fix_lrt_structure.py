#!/usr/bin/env python3

import json
import sys

def add_missing_lrt_stations(input_file, output_file):
    """
    Add missing LRT stations to the transit graph.
    The existing graph has the right structure for some stations but is missing
    - LRT hub stations: PTC, STC
    - All SE and SW line stations
    - Some PE and PW stations with wrong codes
    """
    
    with open(input_file, 'r') as f:
        transit_data = json.load(f)
    
    # Missing LRT stations to add
    missing_lrt = [
        # Punggol LRT Hub (should be PTC)
        {
            "official_name": "PUNGGOL LRT STATION",
            "mrt_codes": ["PTC"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.4053,
                    "lng": 103.9023
                },
                {
                    "exit_code": "Exit 2", 
                    "lat": 1.4051,
                    "lng": 103.9026
                }
            ]
        },
        # Sengkang LRT Hub (should be STC)
        {
            "official_name": "SENGKANG LRT STATION",
            "mrt_codes": ["STC"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.3918,
                    "lng": 103.8954
                },
                {
                    "exit_code": "Exit 2",
                    "lat": 1.3918,
                    "lng": 103.8956
                }
            ]
        },
        # SE1-SE5 (Sengkang East Loop)
        {
            "official_name": "COMPASSVALE LRT STATION",
            "mrt_codes": ["SE1"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.3921,
                    "lng": 103.8893
                }
            ]
        },
        {
            "official_name": "RUMBIA LRT STATION", 
            "mrt_codes": ["SE2"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.3955,
                    "lng": 103.8932
                }
            ]
        },
        {
            "official_name": "BAKAU LRT STATION",
            "mrt_codes": ["SE3"],
            "exits": [
                {
                    "exit_code": "Exit 1", 
                    "lat": 1.3989,
                    "lng": 103.8921
                }
            ]
        },
        {
            "official_name": "KANGKAR LRT STATION",
            "mrt_codes": ["SE4"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.4023,
                    "lng": 103.8945
                }
            ]
        },
        {
            "official_name": "RANGGUNG LRT STATION",
            "mrt_codes": ["SE5"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.4067,
                    "lng": 103.8928
                }
            ]
        },
        # SW1-SW8 (Sengkang West Loop)
        {
            "official_name": "CHENG LIM LRT STATION",
            "mrt_codes": ["SW1"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.3901,
                    "lng": 103.8951
                }
            ]
        },
        {
            "official_name": "FARMWAY LRT STATION",
            "mrt_codes": ["SW2"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.3867,
                    "lng": 103.8938
                }
            ]
        },
        {
            "official_name": "KUPANG LRT STATION",
            "mrt_codes": ["SW3"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.3832,
                    "lng": 103.8941
                }
            ]
        },
        {
            "official_name": "THANGGAM LRT STATION",
            "mrt_codes": ["SW4"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.3798,
                    "lng": 103.8944
                }
            ]
        },
        {
            "official_name": "FERNVALE LRT STATION",
            "mrt_codes": ["SW5"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.3768,
                    "lng": 103.8947
                }
            ]
        },
        {
            "official_name": "LAYAR LRT STATION",
            "mrt_codes": ["SW6"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.3738,
                    "lng": 103.8950
                }
            ]
        },
        {
            "official_name": "TONGKANG LRT STATION",
            "mrt_codes": ["SW7"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.3709,
                    "lng": 103.8953
                }
            ]
        },
        {
            "official_name": "RENJONG LRT STATION",
            "mrt_codes": ["SW8"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.3679,
                    "lng": 103.8956
                }
            ]
        },
        # PE1-PE7 (Punggol East Loop - fix existing entries)
        {
            "official_name": "COVE LRT STATION",
            "mrt_codes": ["PE1"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.4097,
                    "lng": 103.9238
                }
            ]
        },
        {
            "official_name": "MERIDIAN LRT STATION", 
            "mrt_codes": ["PE2"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.4123,
                    "lng": 103.9241
                }
            ]
        },
        {
            "official_name": "CORAL EDGE LRT STATION",
            "mrt_codes": ["PE3"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.4149,
                    "lng": 103.9251
                }
            ]
        },
        {
            "official_name": "RIVIERA LRT STATION",
            "mrt_codes": ["PE4"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.4175,
                    "lng": 103.9259
                }
            ]
        },
        {
            "official_name": "KADALOOR LRT STATION",
            "mrt_codes": ["PE5"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.4201,
                    "lng": 103.9267
                }
            ]
        },
        {
            "official_name": "OASIS LRT STATION",
            "mrt_codes": ["PE6"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.4227,
                    "lng": 103.9275
                }
            ]
        },
        {
            "official_name": "DAMAI LRT STATION",
            "mrt_codes": ["PE7"],
            "exits": [
                {
                    "exit_code": "Exit 1",
                    "lat": 1.4253,
                    "lng": 103.9283
                }
            ]
        }
    ]
    
    # Add missing stations to transit data
    added_count = 0
    for lrt_station in missing_lrt:
        transit_data.append(lrt_station)
        added_count += 1
    
    # Fix existing MRT stations that need LRT codes
    for station in transit_data:
        if station['official_name'] == "PUNGGOL MRT STATION":
            if "PTC" not in station['mrt_codes']:
                station['mrt_codes'].append("PTC")
                # Add LRT exits (C, D) with approximate coordinates
                existing_lats = [ex['lat'] for ex in station['exits']]
                existing_lngs = [ex['lng'] for ex in station['exits']]
                
                # Add Exit C (approximate south)
                station['exits'].append({
                    "exit_code": "Exit C",
                    "lat": sum(existing_lats) / len(existing_lats) - 0.002,
                    "lng": sum(existing_lngs) / len(existing_lngs) + 0.001
                })
                
                # Add Exit D (approximate north)  
                station['exits'].append({
                    "exit_code": "Exit D",
                    "lat": sum(existing_lats) / len(existing_lats) + 0.002,
                    "lng": sum(existing_lngs) / len(existing_lngs) - 0.001
                })
                added_count += 2
                
        elif station['official_name'] == "SENGKANG MRT STATION":
            if "STC" not in station['mrt_codes']:
                station['mrt_codes'].append("STC")
                # Add LRT exits (C, D) with approximate coordinates
                existing_lats = [ex['lat'] for ex in station['exits']]
                existing_lngs = [ex['lng'] for ex in station['exits']]
                
                # Add Exit C and D for LRT
                station['exits'].append({
                    "exit_code": "Exit C",
                    "lat": sum(existing_lats) / len(existing_lats) - 0.003,
                    "lng": sum(existing_lngs) / len(existing_lngs) + 0.002
                })
                station['exits'].append({
                    "exit_code": "Exit D",
                    "lat": sum(existing_lats) / len(existing_lats) + 0.003,
                    "lng": sum(existing_lngs) / len(existing_lngs) - 0.002
                })
                added_count += 2
    
    print(f"Added {added_count} exits and 2 hub codes to existing stations")
    
    # Sort exits for all stations
    for station in transit_data:
        station['exits'] = sorted(station['exits'], key=lambda x: x['exit_code'])
    
    # Save updated transit graph
    with open(output_file, 'w') as f:
        json.dump(transit_data, f, indent=2)
    
    print(f"Transit graph updated: {len(transit_data)} total stations")
    print(f"Added {len(missing_lrt)} new LRT stations + 2 hub codes")
    
    # Create summary
    summary = {
        "original_count": len(transit_data) - len(missing_lrt),
        "added_count": len(missing_lrt),
        "final_count": len(transit_data),
        "lrt_codes_fixed": 2
    }
    
    with open('lrt_fix_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    return transit_data

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 fix_lrt_structure.py <input.json> <output.json>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    add_missing_lrt_stations(input_file, output_file)