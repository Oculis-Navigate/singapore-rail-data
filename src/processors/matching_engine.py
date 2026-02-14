import re
from rapidfuzz import fuzz
from .spatial_utils import calculate_centroid, haversine_distance

class MatchingEngine:
    def __init__(self, onemap_fetcher, config=None, threshold=70, epsilon_meters=800):
        self.onemap = onemap_fetcher
        self.threshold = threshold
        self.epsilon = epsilon_meters
        self.config = config or {}
        
        # Build regex from configurable station_code_prefixes
        # Single letters like A1, B2 are EXIT codes, NOT station codes
        station_prefixes = self.config.get('station_code_prefixes', [])
        if station_prefixes:
            # Build pattern that only matches valid station code prefixes
            prefix_pattern = '|'.join(station_prefixes)
            # Use non-capturing group for alternation to capture full code
            self.code_regex = rf'\b(?:{prefix_pattern})\d*\b'
        else:
            # Fallback to default prefixes if config not available
            # Note: Single letter prefixes (A, B, C) are excluded as they are exit codes
            default_prefixes = ['NS', 'EW', 'NE', 'CC', 'DT', 'TE', 'CG', 'CE', 
                               'BP', 'SW', 'SE', 'PW', 'PE', 'STC', 'PTC',
                               'CR', 'JS', 'JW', 'JE']  # Future lines
            prefix_pattern = '|'.join(default_prefixes)
            # Use non-capturing group for alternation to capture full code
            self.code_regex = rf'\b(?:{prefix_pattern})\d*\b'

    def _extract_codes(self, text):
        return set(re.findall(self.code_regex, str(text).upper()))

    def match_station(self, datagov_name, exits):
        centroid = calculate_centroid(exits)
        results = self.onemap.search_onemap(datagov_name)
        
        all_found_codes = set()
        best_name = None
        highest_score = -1

        for res in results:
            name = res['BUILDING'].upper()
            coords = {"lat": float(res['LATITUDE']), "lng": float(res['LONGITUDE'])}
            dist = haversine_distance(centroid, coords)
            
            if dist <= self.epsilon:
                all_found_codes.update(self._extract_codes(name))
                score = fuzz.WRatio(datagov_name, name)
                if score > highest_score:
                    highest_score = score
                    # Clean brackets and exit info
                    clean = re.sub(r'\(.*?\)', '', name).strip()
                    clean = re.sub(r'\s+EXIT\s+[A-Z0-9]+', '', clean).strip()
                    best_name = clean

        # Fallback to nearby API
        if not all_found_codes:
            nearby = self.onemap.get_nearby_mrt(centroid['lat'], centroid['lng'])
            if nearby:
                nb = nearby[0]
                all_found_codes.update(self._extract_codes(nb['MRT_CA_CODE']))
                best_name = nb['MRT_STATION_NAME'].upper()

        if not all_found_codes:
            return None

        return {
            "official_name": best_name if best_name else datagov_name.upper(),
            "codes": sorted(list(all_found_codes)),
            "centroid": centroid
        }
