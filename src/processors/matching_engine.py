import re
from rapidfuzz import fuzz
from .spatial_utils import calculate_centroid, haversine_distance

class MatchingEngine:
    def __init__(self, onemap_fetcher, threshold=70, epsilon_meters=800):
        self.onemap = onemap_fetcher
        self.threshold = threshold
        self.epsilon = epsilon_meters
        self.code_regex = r'([A-Z]{1,3}\d+|\b(?:NS|EW|NE|CC|DT|TE|BP|SW|SE|PW|STC|PTC)\b)'

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
