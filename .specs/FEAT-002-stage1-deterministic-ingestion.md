# Feature: Stage 1 - Deterministic Data Ingestion Pipeline

## Feature ID: FEAT-002
**Priority:** P1 (Core Pipeline Stage)
**Estimated Effort:** 2-3 hours
**Dependencies:** FEAT-001 (Project Restructure & Data Contracts)

---

## Context

### Current State
- `main.py` currently contains all deterministic data fetching logic
- It fetches from data.gov.sg (exit coordinates) and OneMap (station info)
- Outputs directly to `output/mrt_transit_graph.json`
- Has hardcoded LRT hub code injections and manual fixes
- Lacks proper error handling and validation

### Goal
Extract the deterministic data ingestion logic from `main.py` into a dedicated Stage 1 pipeline component that:
1. Fetches from multiple sources concurrently
2. Produces a standardized Stage1Output following the data contract
3. Pre-computes Fandom URLs for Stage 2
4. Handles errors gracefully with proper logging
5. Saves checkpoint data for downstream stages

---

## Requirements

### 1. Stage 1 Implementation (src/pipelines/stage1_ingestion.py)

Create a `Stage1Ingestion` class implementing the `PipelineStage` interface:

```python
from typing import List, Dict, Any
from datetime import datetime
import uuid
from src.contracts.interfaces import PipelineStage
from src.contracts.schemas import Stage1Output, Stage1Station, Exit, StationType
from src.fetchers.datagov_fetcher import DataGovFetcher
from src.fetchers.onemap_fetcher import OneMapFetcher
from src.fetchers.missing_station_fetcher import MissingStationFetcher
from src.utils.logger import logger

class Stage1Ingestion(PipelineStage):
    """
    Stage 1: Ingest deterministic station and exit data from official sources.
    
    Input: None (starts from external APIs)
    Output: Stage1Output containing all stations with exits and metadata
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.run_id = str(uuid.uuid4())
        self.timestamp = datetime.utcnow()
        
        # Initialize fetchers
        self.datagov_fetcher = DataGovFetcher()
        self.onemap_fetcher = OneMapFetcher()
        self.missing_fetcher = MissingStationFetcher(self.onemap_fetcher)
    
    @property
    def stage_name(self) -> str:
        return "stage1_ingestion"
    
    def execute(self, input_data: None) -> Stage1Output:
        """
        Execute Stage 1 ingestion pipeline.
        
        Steps:
        1. Fetch from data.gov.sg
        2. Augment with OneMap data
        3. Group by station
        4. Match to official station info
        5. Apply manual fixes (LRT hub codes, etc.)
        6. Generate Fandom URLs
        7. Return structured output
        """
        logger.section("Stage 1: Deterministic Data Ingestion")
        
        # Step 1: Fetch raw data
        logger.subsection("Fetching Data from Sources")
        raw_records = self._fetch_raw_data()
        
        # Step 2: Group and process
        logger.subsection("Processing Station Groups")
        station_groups = self._group_by_station(raw_records)
        
        # Step 3: Match to official info
        logger.subsection("Matching to Official Records")
        matched_stations = self._match_stations(station_groups)
        
        # Step 4: Apply fixes
        logger.subsection("Applying Manual Corrections")
        corrected_stations = self._apply_corrections(matched_stations)
        
        # Step 5: Build output
        output = Stage1Output(
            metadata={
                "run_id": self.run_id,
                "timestamp": self.timestamp.isoformat(),
                "version": "2.0.0",
                "source": "stage1_ingestion",
                "total_stations": len(corrected_stations)
            },
            stations=corrected_stations
        )
        
        # Step 6: Validate
        if not self.validate_output(output):
            raise ValueError("Stage 1 output validation failed")
        
        logger.success(f"Stage 1 complete: {len(corrected_stations)} stations processed")
        return output
    
    def _fetch_raw_data(self) -> List[Dict]:
        """Fetch and combine data from all sources"""
        # Implementation here
        pass
    
    def _group_by_station(self, records: List[Dict]) -> Dict[str, List[Dict]]:
        """Group exit records by station name"""
        # Implementation here
        pass
    
    def _match_stations(self, groups: Dict[str, List[Dict]]) -> List[Stage1Station]:
        """Match station groups to official info and create Stage1Station objects"""
        # Implementation here
        pass
    
    def _apply_corrections(self, stations: List[Stage1Station]) -> List[Stage1Station]:
        """Apply manual corrections (LRT hub codes, naming standardization)"""
        # Implementation here
        pass
    
    def _build_fandom_url(self, station_name: str) -> str:
        """Generate Fandom wiki URL for a station"""
        # Convert "YISHUN MRT STATION" → "Yishun_MRT_Station"
        # URL: https://singapore-mrt-lines.fandom.com/wiki/Yishun_MRT_Station
        pass
    
    def validate_input(self, input_data: Any) -> bool:
        """Stage 1 doesn't require input"""
        return input_data is None
    
    def validate_output(self, output_data: Stage1Output) -> bool:
        """Validate output matches schema and has required data"""
        try:
            # Validate with Pydantic
            validated = Stage1Output.model_validate(output_data)
            
            # Additional checks
            assert len(validated.stations) > 0, "No stations in output"
            assert len(validated.stations) >= 180, "Expected at least 180 stations"
            
            # Check all required fields present
            for station in validated.stations:
                assert station.station_id, f"Missing station_id for {station.official_name}"
                assert len(station.exits) > 0, f"No exits for {station.official_name}"
                assert station.fandom_url, f"Missing Fandom URL for {station.official_name}"
            
            return True
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False
```

### 2. Logic Extraction from main.py

Migrate the following logic from `main.py` into the class methods above:

**From main.py lines 37-44 (Data fetching):**
```python
# 1. Fetch from Data.gov.sg
records = dg_fetcher.fetch_all_exits()
logger.success(f"Retrieved {len(records)} exit records from Data.gov.sg")

# 1b. Augment with missing stations from OneMap
records = missing_fetcher.augment_datagov_data(records)
logger.success(f"Total records after augmentation: {len(records)}")
```

**From main.py lines 46-55 (Grouping):**
```python
# 2. Group by station
dg_groups = {}
for r in records:
    name = r["STATION_NA"]
    if name not in dg_groups:
        dg_groups[name] = []
    dg_groups[name].append({"exit_code": r["EXIT_CODE"], "lat": r["LATITUDE"], "lng": r["LONGITUDE"]})
```

**From main.py lines 57-77 (Matching):**
```python
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
```

**From main.py lines 79-99 (Consolidation and fixes):**
```python
# 4. Consolidate interchanges
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
```

### 3. Helper Methods

**URL Generation:**
```python
def _build_fandom_url(self, station_name: str) -> str:
    """
    Generate Fandom wiki URL from station name.
    
    Examples:
    - "YISHUN MRT STATION" → "https://singapore-mrt-lines.fandom.com/wiki/Yishun_MRT_Station"
    - "WOODLANDS MRT STATION" → "https://singapore-mrt-lines.fandom.com/wiki/Woodlands_MRT_Station"
    """
    from urllib.parse import quote
    
    # Remove "MRT STATION" or "LRT STATION" suffix for display name
    display_name = station_name.replace(" MRT STATION", "").replace(" LRT STATION", "")
    
    # Convert to Title Case with underscores
    url_name = display_name.title().replace(" ", "_")
    
    # Add suffix back
    if "LRT" in station_name:
        url_name += "_LRT_Station"
    else:
        url_name += "_MRT_Station"
    
    return f"https://singapore-mrt-lines.fandom.com/wiki/{quote(url_name)}"
```

**Station Type Detection:**
```python
def _detect_station_type(self, station_name: str, codes: List[str]) -> StationType:
    """
    Detect if station is MRT or LRT based on name and codes.
    
    Rules:
    - Contains "LRT" in name → LRT
    - Codes start with BP, SW, SE, PW → LRT
    - Otherwise → MRT
    """
    if "LRT" in station_name:
        return StationType.LRT
    
    lrt_prefixes = ("BP", "SW", "SE", "PW")
    if any(code.startswith(lrt_prefixes) for code in codes):
        return StationType.LRT
    
    return StationType.MRT
```

**Line Detection:**
```python
def _detect_lines(self, codes: List[str]) -> List[str]:
    """
    Detect line codes from station codes.
    
    Mapping:
    - NS* → NSL
    - EW* → EWL
    - NE* → NEL
    - CC* → CCL
    - DT* → DTL
    - TE* → TEL
    - BP* → BPL
    - SW*, SE* → SKL (Sengkang LRT)
    - PW* → PGL (Punggol LRT)
    """
    line_map = {
        "NS": "NSL",
        "EW": "EWL",
        "NE": "NEL",
        "CC": "CCL",
        "DT": "DTL",
        "TE": "TEL",
        "BP": "BPL",
        "SW": "SKL",
        "SE": "SKL",
        "PW": "PGL"
    }
    
    lines = set()
    for code in codes:
        prefix = ''.join(c for c in code if c.isalpha())
        if prefix in line_map:
            lines.add(line_map[prefix])
    
    return sorted(list(lines))
```

### 4. Checkpoint Saving

Add method to save Stage 1 output:

```python
def save_checkpoint(self, output: Stage1Output, output_dir: str):
    """Save Stage 1 output to checkpoint file"""
    import os
    import json
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Convert to dict for JSON serialization
    output_dict = output.model_dump()
    
    filepath = os.path.join(output_dir, "stage1_deterministic.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_dict, f, indent=2, ensure_ascii=False, default=str)
    
    logger.success(f"Stage 1 checkpoint saved: {filepath}")
    return filepath
```

### 5. Execution Script (scripts/run_stage1.py)

Create a standalone script to run Stage 1:

```python
#!/usr/bin/env python3
"""
Standalone script to run Stage 1: Deterministic Data Ingestion

Usage:
    python scripts/run_stage1.py --output-dir outputs/2026-02-07
    python scripts/run_stage1.py --config config/pipeline.yaml
"""

import argparse
import os
import sys
import yaml
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pipelines.stage1_ingestion import Stage1Ingestion
from utils.logger import logger

def main():
    parser = argparse.ArgumentParser(description='Run Stage 1: Deterministic Data Ingestion')
    parser.add_argument('--output-dir', default='outputs/latest', help='Output directory')
    parser.add_argument('--config', default='config/pipeline.yaml', help='Config file path')
    args = parser.parse_args()
    
    # Load config
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)
    
    # Load environment variables
    load_dotenv()
    
    # Run stage
    stage = Stage1Ingestion(config)
    output = stage.execute(input_data=None)
    
    # Save checkpoint
    checkpoint_path = stage.save_checkpoint(output, args.output_dir)
    
    # Print summary
    logger.result("Stage 1 Complete")
    logger.stats("Total Stations", str(len(output.stations)))
    logger.stats("Checkpoint", checkpoint_path)

if __name__ == "__main__":
    main()
```

---

## Success Criteria

1. [ ] `Stage1Ingestion` class implemented in `src/pipelines/stage1_ingestion.py`
2. [ ] Class implements `PipelineStage` interface from FEAT-001
3. [ ] `execute()` method runs without errors
4. [ ] Output validates against `Stage1Output` Pydantic schema
5. [ ] Produces at least 187 stations (current expected count)
6. [ ] All stations have valid Fandom URLs
7. [ ] All stations have at least 1 exit
8. [ ] Checkpoint file saves successfully to JSON
9. [ ] `python scripts/run_stage1.py` runs successfully
10. [ ] Output matches structure of current `main.py` deterministic data

---

## Manual Verification Steps

After implementation, verify:

```python
# Test the stage
from src.pipelines.stage1_ingestion import Stage1Ingestion
import yaml

with open('config/pipeline.yaml') as f:
    config = yaml.safe_load(f)

stage = Stage1Ingestion(config)
output = stage.execute(None)

# Verify output
print(f"Total stations: {len(output.stations)}")
print(f"Sample station: {output.stations[0].official_name}")
print(f"Has Fandom URL: {output.stations[0].fandom_url}")
print(f"Exit count: {len(output.stations[0].exits)}")
```

---

## Dependencies

**Requires:**
- FEAT-001: Project Restructure & Data Contracts (must be complete)

**Required By:**
- FEAT-003: Stage 2 - Enrichment Extraction Pipeline (needs Stage 1 output)
- FEAT-005: Pipeline Orchestrator & Configuration

---

## Known Issues to Handle

1. **LRT Hub Codes**: Some stations (Punggol, Choa Chu Kang, Sengkang) have LRT hub codes that need to be manually injected
2. **Interchange Consolidation**: Stations with multiple codes (e.g., "RAFFLES PLACE MRT STATION" with NS26 and EW14) need to be consolidated
3. **Missing Stations**: Some stations may not appear in data.gov.sg and need to be fetched from OneMap
4. **Naming Standardization**: Some LRT stations have "LRT STATION" in name but should be standardized

All these are currently handled in `main.py` and should be migrated to `Stage1Ingestion`.
