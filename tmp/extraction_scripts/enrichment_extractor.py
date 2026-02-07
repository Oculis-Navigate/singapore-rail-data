#!/usr/bin/env python3
"""
MRT Station Enrichment Data Extractor
Systematically extracts data from Singapore MRT Lines Fandom Wiki
"""

import json
import re
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# Simulated webfetch results for stations already processed
# In real execution, this would call webfetch tool

@dataclass
class ExitEnrichment:
    exit_code: str
    platforms: List[Dict[str, str]]
    accessibility: List[str]
    bus_stops: List[Dict[str, Any]]
    has_barrier_free_access: bool

@dataclass
class StationEnrichment:
    official_name: str
    station_code: str
    lines: List[str]
    exits: List[ExitEnrichment]
    accessibility_notes: List[str]
    last_updated: str
    source_url: str
    extraction_confidence: str

class FandomExtractor:
    """Extracts structured data from Fandom HTML content"""
    
    def __init__(self):
        self.failed_extractions = []
        self.successful_extractions = []
    
    def parse_platform_direction(self, direction_text: str) -> Optional[Dict[str, str]]:
        """Parse platform direction text to extract station codes"""
        # Pattern: "For [Destination]" or "➔ [Code][Name]"
        # Extract station code if present
        
        # Look for station codes like NS1, CC29, TE20, etc.
        code_match = re.search(r'(NS|EW|CC|DT|NE|TE|CE|CG|BP|SW|SE|PE|PW|STC|SM|CR|JS|JE)\d+[A-Z]?', direction_text)
        
        if code_match:
            code = code_match.group(0)
            # Determine line from code prefix
            line_map = {
                'NS': 'NS', 'EW': 'EW', 'CC': 'CC', 'DT': 'DT', 'NE': 'NE', 'TE': 'TE',
                'CE': 'CE', 'CG': 'CG', 'BP': 'BP', 'SW': 'SW', 'SE': 'SE', 'PE': 'PE',
                'PW': 'PW', 'STC': 'STC', 'SM': 'SM', 'CR': 'CR', 'JS': 'JS', 'JE': 'JE'
            }
            line_prefix = code[:2] if code[:2] in line_map else code[:3]
            line_code = line_map.get(line_prefix, 'UNKNOWN')
            
            return {
                'towards_code': code,
                'line_code': line_code
            }
        
        return None
    
    def parse_bus_stop(self, stop_code: str, services: List[str]) -> Dict[str, Any]:
        """Parse bus stop information"""
        return {
            'code': stop_code,
            'services': services
        }
    
    def extract_from_html(self, station_name: str, html_content: str) -> Optional[StationEnrichment]:
        """Extract enrichment data from Fandom HTML content"""
        # This is a simplified version - real implementation would parse actual HTML
        # For now, we'll use the data I already fetched manually
        
        # Check if extraction failed (404 or no data)
        if not html_content or '404' in html_content:
            self.failed_extractions.append(station_name)
            return None
        
        # Real extraction logic would go here
        # For this batch, we'll return the data I manually collected earlier
        
        return None  # Placeholder

# Data structures for batch processing
BATCH_STATUS_FILE = '/Users/ryanyeo/Projects/mrt-data/tmp/extraction_scripts/batch_status.json'
FAILED_STATIONS_FILE = '/Users/ryanyeo/Projects/mrt-data/tmp/extraction_scripts/failed_stations.json'
EXTRACTED_DATA_FILE = '/Users/ryanyeo/Projects/mrt-data/tmp/extraction_scripts/extracted_data.json'

def save_batch_status(batch_id: int, status: str, count: int):
    """Save batch processing status"""
    try:
        with open(BATCH_STATUS_FILE, 'r') as f:
            statuses = json.load(f)
    except:
        statuses = {}
    
    statuses[f'batch_{batch_id}'] = {
        'status': status,
        'count': count,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
    }
    
    with open(BATCH_STATUS_FILE, 'w') as f:
        json.dump(statuses, f, indent=2)

def load_batch_plan() -> List[Dict]:
    """Load the batch processing plan"""
    with open('/Users/ryanyeo/Projects/mrt-data/tmp/extraction_scripts/batch_plan.json', 'r') as f:
        return json.load(f)

def process_batch(batch_id: int, stations: List[Dict]) -> Dict[str, Any]:
    """Process a batch of stations"""
    print(f"\n{'='*60}")
    print(f"PROCESSING BATCH {batch_id}: {len(stations)} stations")
    print(f"{'='*60}\n")
    
    extractor = FandomExtractor()
    extracted_data = {}
    failed = []
    
    for i, station in enumerate(stations, 1):
        station_name = station['name']
        print(f"[{i}/{len(stations)}] Processing: {station_name}")
        
        # In real execution, this would:
        # 1. Fetch Fandom page using webfetch
        # 2. Parse HTML to extract data
        # 3. Structure into enrichment format
        
        # For now, we'll track what needs to be done
        print(f"  - Codes: {', '.join(station['codes'])}")
        print(f"  - Exits: {station['exits']}")
        print(f"  ⏳ Needs extraction\n")
        
        # Placeholder - real data would be extracted here
        time.sleep(0.1)  # Simulate processing time
    
    return {
        'batch_id': batch_id,
        'total': len(stations),
        'extracted': len(extracted_data),
        'failed': len(failed),
        'data': extracted_data,
        'failed_stations': failed
    }

def main():
    """Main execution function"""
    print("🚀 MRT Station Enrichment Data Extractor")
    print("=" * 60)
    
    # Load batch plan
    batches = load_batch_plan()
    print(f"📋 Loaded {len(batches)} batches ({sum(b['count'] for b in batches)} stations)\n")
    
    # Process each batch
    all_results = []
    all_failed = []
    
    for batch in batches:
        batch_id = batch['batch_id']
        stations = batch['stations']
        
        result = process_batch(batch_id, stations)
        all_results.append(result)
        all_failed.extend(result['failed_stations'])
        
        save_batch_status(batch_id, 'completed', result['extracted'])
    
    # Save final results
    print(f"\n{'='*60}")
    print("EXTRACTION COMPLETE")
    print(f"{'='*60}")
    print(f"Total processed: {sum(r['total'] for r in all_results)}")
    print(f"Successfully extracted: {sum(r['extracted'] for r in all_results)}")
    print(f"Failed: {len(all_failed)}")
    
    if all_failed:
        print(f"\nFailed stations ({len(all_failed)}):")
        for station in all_failed:
            print(f"  - {station}")
    
    # Save failed stations list
    with open(FAILED_STATIONS_FILE, 'w') as f:
        json.dump({
            'count': len(all_failed),
            'stations': all_failed,
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
        }, f, indent=2)
    
    print(f"\n📁 Failed stations saved to: {FAILED_STATIONS_FILE}")

if __name__ == '__main__':
    main()
