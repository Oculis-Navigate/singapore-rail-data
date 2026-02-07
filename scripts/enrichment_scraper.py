#!/usr/bin/env python3
"""
MRT Station Enrichment Data Scraper

This script extracts additional station information from Singapore MRT Fandom pages
using OpenRouter LLM API. It's designed to be run once (or when new stations are added)
to generate enrichment data that can then be manually maintained.

Usage:
    python enrichment_scraper.py --station "MacPherson MRT Station"
    python enrichment_scraper.py --batch stations_to_scrape.txt
    python enrichment_scraper.py --manual-review

The script will:
1. Fetch the Fandom page HTML
2. Send it to OpenRouter with a structured prompt
3. Parse the LLM response into structured JSON
4. Save to enrichment_data.json
5. (Optional) Pause for manual review if --manual-review flag is set
"""

import os
import sys
import json
import time
import re
import argparse
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from urllib.parse import quote

import requests
from dotenv import load_dotenv


# Configuration
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
FANDOM_BASE_URL = "https://singapore-mrt-lines.fandom.com/wiki/"
ENRICHMENT_DATA_FILE = "output/mrt_enrichment_data.json"

# Default model - you can change this to any OpenRouter model
DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"


@dataclass
class ExitEnrichment:
    """Structured data for a single exit"""
    exit_code: str
    platforms: List[Dict[str, str]]  # [{"line": "CCL", "direction": "Harbourfront"}]
    accessibility: List[str]  # ["wheelchair_accessible", "lift", "escalator", "stairs_only"]
    bus_stops: List[Dict[str, Any]]  # [{"code": "70371", "description": "", "services": []}]
    nearby_landmarks: List[str]  # e.g., ["MacPherson Community Club", "Circuit Road Market"]


@dataclass
class StationEnrichment:
    """Complete enrichment data for a station"""
    official_name: str
    station_code: str  # e.g., "CC10"
    lines: List[str]  # e.g., ["CCL"]
    exits: List[ExitEnrichment]
    accessibility_notes: List[str]  # Station-level accessibility info
    last_updated: str  # ISO format date
    source_url: str
    extraction_confidence: str  # "high", "medium", "low"


class OpenRouterClient:
    """Client for OpenRouter API"""
    
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/yourusername/mrt-data",  # Required by OpenRouter
            "X-Title": "MRT Data Enrichment Scraper"
        }
    
    def extract_station_data(self, station_name: str, html_content: str) -> Optional[StationEnrichment]:
        """Send HTML to OpenRouter and get structured station data"""
        
        system_prompt = """You are a data extraction specialist. Your task is to extract structured information about Singapore MRT stations from Fandom wiki pages.

Extract the following information in JSON format:
1. Station code (e.g., "CC10")
2. Lines served (e.g., ["CCL", "DTL"])
3. For each exit:
   - Exit code (e.g., "A", "B", "1", "2")
   - Which platforms/directions it leads to (e.g., Platform A → Harbourfront direction)
   - Accessibility features (wheelchair accessible, lift, escalator, stairs only, barrier-free, etc.)
   - Nearby bus stops with their codes (e.g., Bus Stop 70371)
   - Nearby landmarks/destinations

IMPORTANT RULES:
- If information is not found, use empty arrays or "unknown"
- Be precise with bus stop codes (they are 5-digit numbers)
- Only include exits that actually exist at this station
- Accessibility should note ANY limitations (e.g., "Exit C does not provide barrier-free accessibility")
- Platform directions should specify both line and destination

Return ONLY valid JSON. No markdown, no explanation."""

        user_prompt = f"""Extract data for station: {station_name}

HTML Content:
{html_content[:15000]}  # Truncate to avoid token limits

Return this exact JSON structure:
{{
    "station_code": "CC10",
    "lines": ["CCL"],
    "exits": [
        {{
            "exit_code": "A",
            "platforms": [
                {{"line": "CCL", "direction": "Harbourfront", "platform_code": "A"}}
            ],
            "accessibility": ["wheelchair_accessible", "lift", "escalator"],
            "bus_stops": [
                {{"code": "70371", "description": "MacPherson Station Exit A", "services": []}}
            ],
            "nearby_landmarks": ["MacPherson Community Club"]
        }}
    ],
    "accessibility_notes": ["All exits are wheelchair accessible except Exit C"],
    "extraction_confidence": "high"
}}"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.1,  # Low temperature for consistent extraction
            "max_tokens": 4000
        }
        
        content = None
        try:
            response = requests.post(
                OPENROUTER_API_URL,
                headers=self.headers,
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # Clean up the response (remove markdown code blocks if present)
            content = re.sub(r'```json\s*', '', content)
            content = re.sub(r'```\s*', '', content)
            content = content.strip()
            
            # Parse the JSON
            data = json.loads(content)
            
            # Build the enrichment object
            exits = []
            for exit_data in data.get("exits", []):
                exits.append(ExitEnrichment(
                    exit_code=exit_data.get("exit_code", ""),
                    platforms=exit_data.get("platforms", []),
                    accessibility=exit_data.get("accessibility", []),
                    bus_stops=exit_data.get("bus_stops", []),
                    nearby_landmarks=exit_data.get("nearby_landmarks", [])
                ))
            
            return StationEnrichment(
                official_name=station_name,
                station_code=data.get("station_code", ""),
                lines=data.get("lines", []),
                exits=exits,
                accessibility_notes=data.get("accessibility_notes", []),
                last_updated=time.strftime("%Y-%m-%dT%H:%M:%S"),
                source_url=f"{FANDOM_BASE_URL}{quote(station_name.replace(' ', '_'))}",
                extraction_confidence=data.get("extraction_confidence", "medium")
            )
            
        except requests.exceptions.RequestException as e:
            print(f"❌ API request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse LLM response as JSON: {e}")
            if content:
                print(f"Response was: {content[:500]}")
            return None
        except KeyError as e:
            print(f"❌ Unexpected API response structure: {e}")
            return None


class FandomScraper:
    """Scraper for Singapore MRT Fandom pages"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        })
    
    def fetch_page(self, station_name: str) -> Optional[str]:
        """Fetch the HTML content of a station's Fandom page"""
        # Convert station name to URL format
        url_name = station_name.replace(' ', '_')
        url = f"{FANDOM_BASE_URL}{quote(url_name)}"
        
        try:
            print(f"📥 Fetching: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch {url}: {e}")
            return None


class EnrichmentDataManager:
    """Manages the enrichment data JSON file"""
    
    def __init__(self, filepath: str = ENRICHMENT_DATA_FILE):
        self.filepath = filepath
        self.data = self._load_existing()
    
    def _load_existing(self) -> Dict[str, Any]:
        """Load existing enrichment data if it exists"""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️  Warning: Could not parse existing {self.filepath}, starting fresh")
                return {"metadata": {}, "stations": {}}
        return {"metadata": {}, "stations": {}}
    
    def add_station(self, station: StationEnrichment):
        """Add or update a station in the enrichment data"""
        self.data["stations"][station.official_name] = asdict(station)
    
    def get_station(self, station_name: str) -> Optional[Dict]:
        """Get enrichment data for a specific station"""
        return self.data["stations"].get(station_name)
    
    def save(self):
        """Save the enrichment data to file"""
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        print(f"💾 Saved enrichment data to {self.filepath}")
    
    def manual_review(self, station_name: str, station_data: Dict) -> Optional[Dict]:
        """Interactive manual review of extracted data"""
        print(f"\n{'='*60}")
        print(f"MANUAL REVIEW: {station_name}")
        print(f"{'='*60}")
        print(f"Station Code: {station_data.get('station_code', 'N/A')}")
        print(f"Lines: {', '.join(station_data.get('lines', []))}")
        print(f"Confidence: {station_data.get('extraction_confidence', 'N/A')}")
        print(f"\nExits ({len(station_data.get('exits', []))}):")
        
        for i, exit_data in enumerate(station_data.get('exits', []), 1):
            print(f"\n  Exit {i}: {exit_data.get('exit_code', 'Unknown')}")
            print(f"    Platforms: {exit_data.get('platforms', [])}")
            print(f"    Accessibility: {exit_data.get('accessibility', [])}")
            print(f"    Bus Stops: {[bs.get('code') for bs in exit_data.get('bus_stops', [])]}")
            print(f"    Landmarks: {exit_data.get('nearby_landmarks', [])}")
        
        print(f"\nAccessibility Notes: {station_data.get('accessibility_notes', [])}")
        print(f"\n{'='*60}")
        
        while True:
            action = input("\n[Keep(k)/Edit(e)/Skip(s)/Quit(q)]: ").lower().strip()
            if action in ['k', 'keep', '']:
                return station_data
            elif action in ['e', 'edit']:
                print("\nTo edit, please modify the JSON file after extraction.")
                return station_data
            elif action in ['s', 'skip']:
                return None
            elif action in ['q', 'quit']:
                raise KeyboardInterrupt("User quit during review")
            else:
                print("Invalid choice. Please enter k, e, s, or q")


def main():
    parser = argparse.ArgumentParser(
        description="Extract MRT station enrichment data using OpenRouter LLM"
    )
    parser.add_argument(
        "--station",
        help="Single station name to extract (e.g., 'MacPherson MRT Station')"
    )
    parser.add_argument(
        "--batch",
        help="File containing list of station names (one per line)"
    )
    parser.add_argument(
        "--manual-review",
        action="store_true",
        help="Enable interactive manual review after each extraction"
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"OpenRouter model to use (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between API calls in seconds (default: 2)"
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    
    if not api_key or api_key == "your_openrouter_api_key_here":
        print("❌ Error: OPENROUTER_API_KEY not set in .env file")
        print("Please get an API key from https://openrouter.ai/ and add it to .env")
        sys.exit(1)
    
    # Initialize components
    llm_client = OpenRouterClient(api_key, model=args.model)
    scraper = FandomScraper()
    data_manager = EnrichmentDataManager()
    
    # Determine stations to process
    stations_to_process = []
    if args.station:
        stations_to_process = [args.station]
    elif args.batch:
        try:
            with open(args.batch, 'r') as f:
                stations_to_process = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"❌ Batch file not found: {args.batch}")
            sys.exit(1)
    else:
        print("❌ Error: Must specify either --station or --batch")
        parser.print_help()
        sys.exit(1)
    
    print(f"🚀 Processing {len(stations_to_process)} stations...")
    print(f"🤖 Using model: {args.model}")
    print(f"💾 Output file: {ENRICHMENT_DATA_FILE}")
    
    successful = 0
    failed = 0
    skipped = 0
    
    try:
        for i, station_name in enumerate(stations_to_process, 1):
            print(f"\n[{i}/{len(stations_to_process)}] Processing: {station_name}")
            
            # Check if already exists
            existing = data_manager.get_station(station_name)
            if existing:
                print(f"⚠️  Station already exists in enrichment data (last updated: {existing.get('last_updated', 'unknown')})")
                overwrite = input("   Overwrite? [y/N]: ").lower().strip() == 'y'
                if not overwrite:
                    print("   Skipping...")
                    skipped += 1
                    continue
            
            # Fetch the Fandom page
            html = scraper.fetch_page(station_name)
            if not html:
                failed += 1
                continue
            
            # Extract data using LLM
            print("🤖 Sending to OpenRouter for extraction...")
            station_data = llm_client.extract_station_data(station_name, html)
            
            if not station_data:
                failed += 1
                continue
            
            # Manual review if enabled
            if args.manual_review:
                station_dict = asdict(station_data)
                reviewed = data_manager.manual_review(station_name, station_dict)
                if reviewed is None:
                    print("   Skipping...")
                    skipped += 1
                    continue
                station_data = StationEnrichment(**reviewed)
            
            # Add to data manager
            data_manager.add_station(station_data)
            print(f"✅ Successfully extracted: {station_name} (confidence: {station_data.extraction_confidence})")
            successful += 1
            
            # Delay between requests
            if i < len(stations_to_process):
                time.sleep(args.delay)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    finally:
        # Save progress
        data_manager.save()
        
        # Print summary
        print(f"\n{'='*60}")
        print("EXTRACTION SUMMARY")
        print(f"{'='*60}")
        print(f"Total stations: {len(stations_to_process)}")
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"⏭️  Skipped: {skipped}")
        print(f"\n💾 Data saved to: {ENRICHMENT_DATA_FILE}")
        print(f"\nNext steps:")
        print(f"  1. Review the enrichment data file")
        print(f"  2. Manually correct any errors")
        print(f"  3. Run main.py to merge enrichment data into the main output")


if __name__ == "__main__":
    main()
