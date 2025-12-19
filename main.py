import os
from dotenv import load_dotenv
from fetchers.datagov_fetcher import DataGovFetcher
from fetchers.onemap_fetcher import OneMapFetcher
from processors.matching_engine import MatchingEngine
from processors.consolidator import Consolidator
from storage.json_storage import JSONStorage

def main():
    load_dotenv()
    dg_fetcher = DataGovFetcher()
    om_fetcher = OneMapFetcher()
    matcher = MatchingEngine(om_fetcher)
    consolidator = Consolidator()
    storage = JSONStorage()

    print("--- MRT Graph Builder Start ---")
    
    # 1. Fetch
    records = dg_fetcher.fetch_all_exits()
    
    # 2. Group by DataGov Naming
    dg_groups = {}
    for r in records:
        name = r['STATION_NA']
        if name not in dg_groups: dg_groups[name] = []
        dg_groups[name].append({
            "exit_code": r['EXIT_CODE'], "lat": r['LATITUDE'], "lng": r['LONGITUDE']
        })

    # 3. Match each group to official OneMap info
    raw_matches = []
    print(f"Processing {len(dg_groups)} DataGov station groups...")
    for dg_name, exits in dg_groups.items():
        match_result = matcher.match_station(dg_name, exits)
        if match_result:
            raw_matches.append({
                "official_name": match_result['official_name'],
                "codes": match_result['codes'],
                "exits": exits
            })

    # 4. Consolidate (Merge by Code Intersection + Proximity)
    print("Consolidating interchanges and fragmented exits...")
    final_output = consolidator.consolidate(raw_matches)

    # 5. Save
    storage.save(final_output, "mrt_transit_graph.json")
    print(f"Build Complete. Found {len(final_output)} unique stations.")

if __name__ == "__main__":
    main()
