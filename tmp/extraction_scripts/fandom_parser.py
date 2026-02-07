#!/usr/bin/env python3
"""
MRT Station Data Parser
Parses Fandom HTML content to extract structured enrichment data
"""

import re
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

@dataclass
class ParsedExit:
    exit_code: str
    platforms: List[Dict[str, str]]
    accessibility: List[str]
    bus_stops: List[Dict[str, Any]]
    has_barrier_free: bool

@dataclass
class ParsedStation:
    name: str
    station_code: str
    lines: List[str]
    exits: List[ParsedExit]
    accessibility_notes: List[str]
    confidence: str

class FandomParser:
    """Parse Fandom wiki HTML to extract MRT station data"""
    
    def __init__(self):
        self.debug = False
    
    def extract_station_code(self, html: str) -> Optional[str]:
        """Extract primary station code from page title or content"""
        # Look for patterns like "NS13 Yishun" or station code in infobox
        patterns = [
            r'(NS|EW|CC|DT|NE|TE|CE|CG|BP|SW|SE|PE|PW|STC|SM|CR|JS|JE)\d+[A-Z]?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(0)
        return None
    
    def extract_lines(self, html: str) -> List[str]:
        """Extract which lines serve this station"""
        lines = []
        line_patterns = {
            'North-South Line': 'NSL',
            'East-West Line': 'EWL',
            'Circle Line': 'CCL',
            'Downtown Line': 'DTL',
            'North-East Line': 'NEL',
            'Thomson-East Coast Line': 'TEL',
            'Bukit Panjang LRT': 'BPLRT',
            'Sengkang LRT': 'SKLRT',
            'Punggol LRT': 'PGLRT',
            'Changi Airport Branch': 'CAL',
            'Cross Island Line': 'CRL',
            'Jurong Region Line': 'JRL'
        }
        
        for full_name, short_code in line_patterns.items():
            if full_name in html or short_code in html:
                if short_code not in lines:
                    lines.append(short_code)
        
        return lines
    
    def extract_exits(self, html: str) -> Tuple[List[ParsedExit], List[str]]:
        """Extract exit information from HTML"""
        exits = []
        accessibility_notes = []
        
        # Pattern to find exit sections
        exit_pattern = r'Exit\s+([A-Z]|\d+)[^\n]*\n+([^\n]+)'
        exit_matches = re.findall(exit_pattern, html, re.IGNORECASE)
        
        for exit_code, location in exit_matches:
            exit_code = exit_code.strip()
            
            # Determine accessibility
            accessibility = []
            has_barrier_free = False
            
            if 'barrier-free' in html.lower() or 'wheelchair' in html.lower():
                if exit_code in html.split('barrier-free')[0].split('Exit')[-1] if 'barrier-free' in html else True:
                    accessibility.append('wheelchair_accessible')
                    accessibility.append('barrier_free')
                    has_barrier_free = True
            
            if 'lift' in location.lower():
                accessibility.append('lift')
            if 'escalator' in location.lower():
                accessibility.append('escalator')
            if 'stairs' in location.lower() and 'lift' not in location.lower():
                accessibility.append('stairs_only')
            
            exits.append(ParsedExit(
                exit_code=exit_code,
                platforms=[],  # Will be populated separately
                accessibility=accessibility,
                bus_stops=[],  # Will be populated separately
                has_barrier_free=has_barrier_free
            ))
        
        return exits, accessibility_notes
    
    def extract_platforms(self, html: str) -> List[Dict[str, str]]:
        """Extract platform to line/direction mappings"""
        platforms = []
        
        # Look for platform sections
        platform_pattern = r'(A|B|C|D)Platform.*?➔\s*(NS|EW|CC|DT|NE|TE|CE|CG|BP|SW|SE|PE|PW|STC|SM|CR|JS|JE)(\d+)'
        matches = re.findall(platform_pattern, html, re.DOTALL)
        
        for platform_code, line_prefix, station_num in matches:
            station_code = f"{line_prefix}{station_num}"
            platforms.append({
                'platform_code': platform_code,
                'towards_code': station_code,
                'line_code': line_prefix
            })
        
        return platforms
    
    def extract_bus_stops(self, html: str) -> List[Dict[str, Any]]:
        """Extract bus stop codes and services"""
        bus_stops = []
        
        # Pattern: Bus stop code followed by services
        # Look for tables or lists with bus stop information
        bus_pattern = r'(\d{5})\s*.*?Bus\s+Services[:\s]*([^\n]+)'
        matches = re.findall(bus_pattern, html)
        
        for stop_code, services_text in matches:
            # Extract service numbers
            services = re.findall(r'\d+[A-Z]?', services_text)
            bus_stops.append({
                'code': stop_code,
                'services': services
            })
        
        return bus_stops
    
    def parse_station(self, station_name: str, html_content: str) -> Optional[ParsedStation]:
        """Parse complete station data from HTML"""
        if not html_content or len(html_content) < 100:
            return None
        
        try:
            # Extract basic info
            station_code = self.extract_station_code(html_content)
            if not station_code:
                # Try to derive from station name
                code_match = re.search(r'(NS|EW|CC|DT|NE|TE|CE|CG|BP|SW|SE|PE|PW|STC|SM|CR|JS|JE)\d+', station_name)
                if code_match:
                    station_code = code_match.group(0)
                else:
                    station_code = "UNKNOWN"
            
            lines = self.extract_lines(html_content)
            
            # Extract exits
            exits, accessibility_notes = self.extract_exits(html_content)
            
            # Extract platforms and assign to exits
            platforms = self.extract_platforms(html_content)
            
            # Distribute platforms to exits based on patterns
            for i, exit in enumerate(exits):
                # Assign platforms based on exit code
                exit.platforms = [p for p in platforms if self._platform_matches_exit(p, exit.exit_code)]
            
            # Extract bus stops
            bus_stops = self.extract_bus_stops(html_content)
            # Assign bus stops to exits (simplified - in reality would match by exit)
            for exit in exits:
                exit.bus_stops = bus_stops[:2] if bus_stops else []  # Simplified assignment
            
            return ParsedStation(
                name=station_name,
                station_code=station_code,
                lines=lines,
                exits=exits,
                accessibility_notes=accessibility_notes,
                confidence='high' if exits else 'medium'
            )
            
        except Exception as e:
            print(f"Error parsing {station_name}: {e}")
            return None
    
    def _platform_matches_exit(self, platform: Dict, exit_code: str) -> bool:
        """Determine if a platform matches an exit"""
        # Simplified logic - in reality this is more complex
        platform_letter = platform.get('platform_code', '')
        return platform_letter == exit_code or exit_code in ['A', 'B', '1', '2']

# Test with sample data
def test_parser():
    """Test the parser with known data"""
    parser = FandomParser()
    
    # Test case: MacPherson
    sample_html = """
    CC10 DT26 MacPherson
    Platforms
    A: For HarbourFront
    B: For Dhoby Ghaut/Marina Bay
    Exits
    Exit A: Location...
    Exit B: Location...
    70371 MacPherson Stn Exit A
    Bus Services: 61 63 65
    """
    
    result = parser.parse_station("MacPherson MRT Station", sample_html)
    if result:
        print(f"✅ Parsed: {result.name}")
        print(f"   Code: {result.station_code}")
        print(f"   Lines: {result.lines}")
        print(f"   Exits: {len(result.exits)}")
        for exit in result.exits:
            print(f"     Exit {exit.exit_code}: {len(exit.platforms)} platforms, {len(exit.bus_stops)} bus stops")
    else:
        print("❌ Failed to parse")

if __name__ == '__main__':
    test_parser()
