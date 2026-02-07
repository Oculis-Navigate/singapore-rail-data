#!/usr/bin/env python3
import os
import requests
import sys
sys.path.insert(0, '/Users/ryanyeo/Projects/mrt-data')
from dotenv import load_dotenv

load_dotenv('/Users/ryanyeo/Projects/mrt-data/.env')

def check_datagov_for_punggol_coast():
    """Check Data.gov.sg API for Punggol Coast station data"""
    dataset_id = "d_b39d3a0871985372d7e1637193335da5"
    poll_url = f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
    
    print("=== Checking Data.gov.sg for Punggol Coast ===")
    try:
        # Get download URL
        poll_res = requests.get(poll_url, timeout=30).json()
        download_url = poll_res.get('data', {}).get('url')
        
        if not download_url:
            print("Error: Could not get download URL")
            return
        
        # Download GeoJSON
        geojson = requests.get(download_url, timeout=60).json()
        features = geojson.get('features', [])
        
        # Search for Punggol Coast or NE18
        punggol_coast_found = False
        ne18_found = False
        punggol_entries = []
        
        for feature in features:
            props = feature.get('properties', {})
            station_name = props.get('STATION_NA', '')
            exit_code = props.get('EXIT_CODE', '')
            
            if 'PUNGGOL COAST' in station_name.upper():
                punggol_coast_found = True
                punggol_entries.append({
                    'station': station_name,
                    'exit': exit_code,
                    'lat': feature['geometry']['coordinates'][1],
                    'lng': feature['geometry']['coordinates'][0]
                })
            
            if 'NE18' in exit_code.upper():
                ne18_found = True
                print(f"Found NE18 code: {station_name} - Exit: {exit_code}")
        
        if punggol_coast_found:
            print(f"✓ Found {len(punggol_entries)} Punggol Coast entries:")
            for entry in punggol_entries[:5]:
                print(f"  - {entry['station']}: {entry['exit']} ({entry['lat']}, {entry['lng']})")
        else:
            print("✗ Punggol Coast NOT found in Data.gov.sg dataset")
            
        if not ne18_found:
            print("✗ NE18 code NOT found in Data.gov.sg dataset")
            
        # Count total Punggol entries for context
        punggol_all = [f for f in features if 'PUNGGOL' in f.get('properties', {}).get('STATION_NA', '').upper()]
        print(f"\nTotal Punggol entries found: {len(punggol_all)}")
        if punggol_all:
            unique_stations = set(f['properties']['STATION_NA'] for f in punggol_all)
            print(f"Unique Punggol stations: {unique_stations}")
            
    except Exception as e:
        print(f"Error checking Data.gov.sg: {e}")

def check_onemap_for_punggol_coast():
    """Check OneMap API for Punggol Coast station data"""
    api_key = os.getenv('ONEMAP_API_KEY')
    search_url = "https://www.onemap.gov.sg/api/common/elastic/search"
    nearby_url = "https://www.onemap.gov.sg/api/public/nearbysvc/getNearestMrtStops"
    
    print("\n=== Checking OneMap for Punggol Coast ===")
    
    try:
        # Search for Punggol Coast
        params = {
            'searchVal': 'Punggol Coast MRT',
            'returnGeom': 'Y',
            'getAddrDetails': 'Y'
        }
        headers = {'Authorization': api_key} if api_key else {}
        
        response = requests.get(search_url, params=params, headers=headers, timeout=30)
        data = response.json()
        results = data.get('results', [])
        
        print(f"Search results for 'Punggol Coast MRT': {len(results)} found")
        for result in results[:5]:
            print(f"  - {result.get('BUILDING')} ({result.get('LATITUDE')}, {result.get('LONGITUDE')})")
            
        # Also try searching just "NE18"
        params2 = {
            'searchVal': 'NE18',
            'returnGeom': 'Y',
            'getAddrDetails': 'Y'
        }
        response2 = requests.get(search_url, params=params2, headers=headers, timeout=30)
        data2 = response2.json()
        results2 = data2.get('results', [])
        
        print(f"\nSearch results for 'NE18': {len(results2)} found")
        for result in results2[:5]:
            print(f"  - {result.get('BUILDING')} ({result.get('LATITUDE')}, {result.get('LONGITUDE')})")
        
        # Check nearby API around Punggol Coast location (approximate coordinates)
        # Punggol Coast is at approximately 1.4167, 103.9167
        print("\n=== Checking OneMap Nearby API ===")
        nearby_params = {
            'latitude': 1.4167,
            'longitude': 103.9167,
            'pagenum': 1
        }
        nearby_response = requests.get(nearby_url, params=nearby_params, headers=headers, timeout=30)
        nearby_data = nearby_response.json()
        nearby_results = nearby_data.get('results', [])
        
        print(f"Nearby MRT from Punggol Coast location: {len(nearby_results)} found")
        for result in nearby_results[:5]:
            print(f"  - {result.get('MRT_STATION_NAME')} ({result.get('MRT_CA_CODE')}) - {result.get('DISTANCE')}m away")
            
    except Exception as e:
        print(f"Error checking OneMap: {e}")

if __name__ == "__main__":
    check_datagov_for_punggol_coast()
    check_onemap_for_punggol_coast()
    print("\n=== Summary ===")
    print("Data source check complete")
