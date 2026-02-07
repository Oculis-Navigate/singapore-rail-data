import os
import sys
import warnings

# Suppress warnings BEFORE importing urllib3
warnings.filterwarnings('ignore', category=UserWarning, module='urllib3')
warnings.filterwarnings('ignore', message='.*OpenSSL.*')
warnings.filterwarnings('ignore', message='.*NotOpenSSLWarning.*')

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
from src.utils.logger import logger
from src.utils.helpers import suppress_library_warnings
from src.fetchers.datagov_fetcher import DataGovFetcher
from src.fetchers.onemap_fetcher import OneMapFetcher
from src.fetchers.missing_station_fetcher import MissingStationFetcher
from src.processors.matching_engine import MatchingEngine
from src.processors.consolidator import Consolidator
from src.processors.enrichment_merger import merge_enrichment_data
from src.storage.json_storage import JSONStorage


def main():
    suppress_library_warnings()
    load_dotenv()

    logger.section("MRT Transit Graph Builder")

    dg_fetcher = DataGovFetcher()
    om_fetcher = OneMapFetcher()
    missing_fetcher = MissingStationFetcher(om_fetcher)
    matcher = MatchingEngine(om_fetcher)
    consolidator = Consolidator()
    storage = JSONStorage()

    # 1. Fetch from Data.gov.sg
    logger.subsection("Fetching Data")
    records = dg_fetcher.fetch_all_exits()
    logger.success(f"Retrieved {len(records)} exit records from Data.gov.sg")

    # 1b. Augment with missing stations from OneMap
    records = missing_fetcher.augment_datagov_data(records)
    logger.success(f"Total records after augmentation: {len(records)}")

    # 2. Group by station
    logger.subsection("Processing Stations")
    dg_groups = {}
    for r in records:
        name = r["STATION_NA"]
        if name not in dg_groups:
            dg_groups[name] = []
        dg_groups[name].append({"exit_code": r["EXIT_CODE"], "lat": r["LATITUDE"], "lng": r["LONGITUDE"]})

    logger.info(f"Grouped into {len(dg_groups)} station groups")

    # 3. Match to official OneMap info
    raw_matches = []
    for i, (dg_name, exits) in enumerate(dg_groups.items(), 1):
        logger.progress(i, len(dg_groups), "Matching stations")
        match_result = matcher.match_station(dg_name, exits)
        if match_result:
            raw_matches.append(
                {"official_name": match_result["official_name"], "codes": match_result["codes"], "exits": exits}
            )
    
    # 3b. Add LRT hub codes BEFORE consolidation to ensure proper merging
    LRT_CODES_PRE_CONSOLIDATION = {
        "PUNGGOL MRT STATION": "PTC",
        "CHOA CHU KANG MRT STATION": "BP1"
    }
    for match in raw_matches:
        station_name = match.get("official_name", "")
        if station_name in LRT_CODES_PRE_CONSOLIDATION:
            lrt_code = LRT_CODES_PRE_CONSOLIDATION[station_name]
            if lrt_code not in match["codes"]:
                match["codes"].append(lrt_code)

    # 4. Consolidate interchanges
    logger.subsection("Consolidating Interchanges")
    final_output = consolidator.consolidate(raw_matches)

    # 4b. Add remaining LRT hub codes (Sengkang only, others handled pre-consolidation)
    LRT_HUB_CODES = {
        "SENGKANG MRT STATION": ["STC"]
    }
    for station in final_output:
        station_name = station.get("official_name", "")
        if station_name in LRT_HUB_CODES:
            station["mrt_codes"] = sorted(list(set(station["mrt_codes"]) | set(LRT_HUB_CODES[station_name])))
    
    # 4c. Standardize naming: Rename LRT stations to MRT for consistency
    for station in final_output:
        station_name = station.get("official_name", "")
        if station_name == "CHOA CHU KANG LRT STATION":
            station["official_name"] = "CHOA CHU KANG MRT STATION"
    
    logger.info("Injected LRT hub codes (STC)")

    # 5. Merge enrichment data (LLM-extracted + manually maintained)
    logger.subsection("Merging Enrichment Data")
    final_output = merge_enrichment_data(final_output)

    # 6. Save
    logger.subsection("Saving Results")
    storage.save(final_output, "mrt_transit_graph.json")

    # Results
    logger.result("Build Complete")
    logger.stats("Total Stations", str(len(final_output)))
    logger.stats("Total Exits", str(sum(len(s["exits"]) for s in final_output)))
    logger.stats("Interchanges", str(len([s for s in final_output if len(s["mrt_codes"]) > 1])))


if __name__ == "__main__":
    main()
