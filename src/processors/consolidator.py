import re
from .spatial_utils import calculate_centroid, haversine_distance

class Consolidator:
    def __init__(self, spatial_threshold=800):
        self.spatial_threshold = spatial_threshold

    def _get_base_name(self, official_name):
        """Extract base station name without MRT/LRT suffix."""
        base = official_name.upper()
        base = base.replace(' MRT/LRT STATION', '')
        base = base.replace(' MRT STATION', '')
        base = base.replace(' LRT STATION', '')
        base = base.replace(' STATION', '')
        return base.strip()

    def consolidate(self, raw_matches):
        consolidated = []

        for match in raw_matches:
            found_existing = False
            match_centroid = calculate_centroid(match['exits'])
            match_base_name = self._get_base_name(match['official_name'])
            
            for station in consolidated:
                # Criterion A: Do they share at least one common MRT code?
                code_intersection = set(match['codes']) & set(station['mrt_codes'])
                
                # Criterion B: Are they physically close?
                existing_centroid = calculate_centroid(station['exits'])
                dist = haversine_distance(match_centroid, existing_centroid)

                # Criterion C: Same base name (for interchange stations like Bukit Panjang)
                station_base_name = self._get_base_name(station['official_name'])
                same_base_name = (match_base_name == station_base_name)

                if (code_intersection and dist < self.spatial_threshold) or \
                   (match['official_name'] == station['official_name'] and dist < 300) or \
                   (same_base_name and dist < self.spatial_threshold):
                    
                    # MERGE LOGIC
                    # 1. Update codes to the union of both
                    station['mrt_codes'] = sorted(list(set(station['mrt_codes']) | set(match['codes'])))
                    
                    # 2. Add and normalize exits
                    existing_exit_codes = {self._normalize_exit_code(ex['exit_code']) for ex in station['exits']}
                    for new_ex in match['exits']:
                        norm_code = self._normalize_exit_code(new_ex['exit_code'])
                        if norm_code not in existing_exit_codes:
                            new_ex_copy = new_ex.copy()
                            new_ex_copy['exit_code'] = norm_code
                            station['exits'].append(new_ex_copy)
                            existing_exit_codes.add(norm_code)
                    
                    found_existing = True
                    break
            
            if not found_existing:
                # Create a new entry with deduplication
                new_entry = {
                    "official_name": match['official_name'],
                    "mrt_codes": match['codes'],
                    "exits": []
                }
                seen_exit_codes = set()
                for ex in match['exits']:
                    norm_code = self._normalize_exit_code(ex['exit_code'])
                    if norm_code not in seen_exit_codes:
                        ex_copy = ex.copy()
                        ex_copy['exit_code'] = norm_code
                        new_entry['exits'].append(ex_copy)
                        seen_exit_codes.add(norm_code)
                consolidated.append(new_entry)

        # Final cleanup: Sort exits for every station
        for station in consolidated:
            station['exits'] = sorted(station['exits'], key=self._exit_sort_key)

        return consolidated

    def _normalize_exit_code(self, code):
        """Standardizes labels like 'A' to 'Exit A'."""
        code_str = str(code).strip()
        # If it's just a letter/number, add "Exit"
        if len(code_str) <= 2 or not code_str.upper().startswith("EXIT"):
            # Strip "Exit" if it was already there without a space (e.g., ExitA)
            clean_val = re.sub(r'^EXIT', '', code_str, flags=re.IGNORECASE).strip()
            return f"Exit {clean_val}"
        
        # Ensure format "Exit [Value]"
        match = re.search(r'EXIT\s*(.*)', code_str, re.IGNORECASE)
        if match:
            return f"Exit {match.group(1).strip()}"
        return code_str

    def _exit_sort_key(self, exit_obj):
        """Natural sort: Letters first, then Numbers (A, B, C... 1, 2, 3)."""
        val = exit_obj['exit_code'].replace("Exit ", "").strip()
        if val.isdigit():
            return (1, int(val))
        return (0, val.upper())
