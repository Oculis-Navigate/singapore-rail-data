# Feature: Stage 3 - Data Merging & Validation Pipeline

## Feature ID: FEAT-004
**Priority:** P1 (Core Pipeline Stage)
**Estimated Effort:** 2-3 hours
**Dependencies:** FEAT-001, FEAT-002, FEAT-003

---

## Context

### Current State
- `processors/enrichment_merger.py` exists and merges enrichment data into main output
- It reads from `output/mrt_enrichment_data.json` (the old format)
- Logic handles exit matching by exit code (case-insensitive)
- Validation is minimal
- No schema validation of final output

### Goal
Create a robust Stage 3 pipeline that:
1. Consumes Stage 1 (deterministic) and Stage 2 (enrichment) outputs
2. Merges data correctly using station_id and exit_code matching
3. Validates final output against schema
4. Runs completeness checks (all stations, all exits)
5. Runs sanity checks (coordinates in Singapore, expected station count)
6. Produces the final `mrt_transit_graph.json` format

---

## Requirements

### 1. Stage 3 Implementation (src/pipelines/stage3_merger.py)

Create a `Stage3Merger` class:

```python
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from src.contracts.interfaces import PipelineStage
from src.contracts.schemas import (
    Stage1Output, Stage2Output, FinalOutput,
    FinalStation, FinalExit, Stage1Station, Stage2Station
)
from src.utils.logger import logger

class Stage3Merger(PipelineStage):
    """
    Stage 3: Merge deterministic and enrichment data, validate final output.
    
    Input: Stage1Output + Stage2Output
    Output: FinalOutput (mrt_transit_graph.json format)
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.stage_config = config.get('stages', {}).get('stage3_merger', {})
        self.validation_config = self.stage_config.get('validation', {})
        self.expected_stations = config.get('expected_stations', 187)
    
    @property
    def stage_name(self) -> str:
        return "stage3_merger"
    
    def execute(self, input_data: tuple[Stage1Output, Stage2Output]) -> FinalOutput:
        """
        Execute Stage 3 merging and validation.
        
        Steps:
        1. Validate inputs
        2. Merge deterministic + enrichment data for each station
        3. Validate merged output
        4. Run completeness checks
        5. Run sanity checks
        6. Return final output
        """
        stage1_output, stage2_output = input_data
        
        logger.section("Stage 3: Data Merging & Validation")
        
        if not self.validate_input(input_data):
            raise ValueError("Invalid input for Stage 3")
        
        # Merge data
        logger.subsection("Merging Station Data")
        merged_stations = self._merge_all_stations(stage1_output, stage2_output)
        
        # Build output
        output = FinalOutput(
            metadata={
                "timestamp": datetime.utcnow().isoformat(),
                "source": "stage3_merger",
                "version": "2.0.0",
                "total_stations": len(merged_stations),
                "enriched_stations": sum(1 for s in merged_stations if s.enrichment_last_updated),
                "input_stations_stage1": len(stage1_output.stations),
                "input_stations_stage2": len(stage2_output.stations)
            },
            stations=merged_stations
        )
        
        # Validation
        logger.subsection("Validating Output")
        if not self.validate_output(output):
            raise ValueError("Stage 3 output validation failed")
        
        # Additional checks
        if self.validation_config.get('completeness_check', True):
            self._run_completeness_check(output)
        
        if self.validation_config.get('sanity_check', True):
            self._run_sanity_check(output)
        
        logger.success(f"Stage 3 complete: {len(merged_stations)} stations merged and validated")
        return output
    
    def _merge_all_stations(
        self, 
        stage1: Stage1Output, 
        stage2: Stage2Output
    ) -> List[dict]:
        """Merge all stations from Stage 1 and Stage 2"""
        merged = []
        
        for station1 in stage1.stations:
            station2 = stage2.stations.get(station1.station_id)
            merged_station = self._merge_single_station(station1, station2)
            merged.append(merged_station)
        
        return merged
    
    def _merge_single_station(
        self, 
        station1: Stage1Station, 
        station2: Optional[Stage2Station]
    ) -> dict:
        """
        Merge a single station's data.
        
        Strategy:
        - Start with deterministic data (Stage 1)
        - Add enrichment data where available (Stage 2)
        - Match exits by exit_code (case-insensitive, normalize formats)
        """
        # Start with deterministic data
        merged = {
            "official_name": station1.official_name,
            "mrt_codes": station1.mrt_codes,
            "exits": []
        }
        
        # Merge exits
        if station2:
            merged["exits"] = self._merge_exits(
                station1.exits, 
                station2.exits,
                station1.station_id
            )
            
            # Add enrichment metadata
            if station2.extraction_result == "success":
                merged["lines_served"] = self._extract_lines_served(station2)
                merged["accessibility_notes"] = station2.accessibility_notes
                merged["enrichment_last_updated"] = station2.extraction_timestamp.isoformat()
                merged["data_quality"] = {
                    "extraction_confidence": station2.extraction_confidence,
                    "source": "enrichment_data"
                }
        else:
            # No enrichment data - use deterministic exits only
            merged["exits"] = [
                {
                    "exit_code": e.exit_code,
                    "lat": e.lat,
                    "lng": e.lng
                }
                for e in station1.exits
            ]
        
        return merged
    
    def _merge_exits(
        self, 
        deterministic_exits: List[Exit], 
        enrichment_exits: List[EnrichedExit],
        station_id: str
    ) -> List[dict]:
        """
        Merge exit data from both sources.
        
        Matches exits by normalized exit code.
        """
        # Create lookup by normalized exit code
        enrichment_by_code = {}
        for exit_data in enrichment_exits:
            code = self._normalize_exit_code(exit_data.exit_code)
            enrichment_by_code[code] = exit_data
        
        merged_exits = []
        for det_exit in deterministic_exits:
            norm_code = self._normalize_exit_code(det_exit.exit_code)
            
            # Start with deterministic data
            merged_exit = {
                "exit_code": det_exit.exit_code,
                "lat": det_exit.lat,
                "lng": det_exit.lng
            }
            
            # Add enrichment if available
            if norm_code in enrichment_by_code:
                enrichment = enrichment_by_code[norm_code]
                
                if enrichment.platforms:
                    merged_exit["platforms"] = [
                        p.model_dump() if hasattr(p, 'model_dump') else p
                        for p in enrichment.platforms
                    ]
                
                if enrichment.accessibility:
                    merged_exit["accessibility"] = enrichment.accessibility
                
                if enrichment.bus_stops:
                    merged_exit["bus_stops"] = [
                        b.model_dump() if hasattr(b, 'model_dump') else b
                        for b in enrichment.bus_stops
                    ]
                
                if enrichment.nearby_landmarks:
                    merged_exit["nearby_landmarks"] = enrichment.nearby_landmarks
            
            merged_exits.append(merged_exit)
        
        return merged_exits
    
    def _normalize_exit_code(self, code: str) -> str:
        """
        Normalize exit code for matching.
        
        Examples:
        - "Exit A" → "A"
        - "Exit 1" → "1"
        - "A" → "A"
        - "  a  " → "A"
        """
        code = code.upper().strip()
        code = code.replace("EXIT ", "").replace("EXIT", "")
        return code.strip()
    
    def _extract_lines_served(self, station2: Stage2Station) -> List[str]:
        """Extract unique line codes from enrichment data"""
        lines = set()
        for exit_data in station2.exits:
            if exit_data.platforms:
                for platform in exit_data.platforms:
                    if hasattr(platform, 'line_code'):
                        lines.add(platform.line_code)
                    elif isinstance(platform, dict):
                        lines.add(platform.get('line_code'))
        return sorted(list(lines))
    
    def validate_input(self, input_data: tuple) -> bool:
        """Validate Stage 1 and Stage 2 outputs"""
        try:
            stage1, stage2 = input_data
            assert isinstance(stage1, Stage1Output), "First input must be Stage1Output"
            assert isinstance(stage2, Stage2Output), "Second input must be Stage2Output"
            assert len(stage1.stations) > 0, "Stage 1 has no stations"
            return True
        except Exception as e:
            logger.error(f"Input validation failed: {e}")
            return False
    
    def validate_output(self, output_data: Stage3Output) -> bool:
        """Validate final output against schema"""
        try:
            from src.contracts.schemas import FinalOutput
            
            # Convert to dict for Pydantic validation
            output_dict = {
                "metadata": output_data.metadata,
                "stations": output_data.stations
            }
            
            validated = FinalOutput.model_validate(output_dict)
            
            # Additional validation
            assert len(validated.stations) > 0, "No stations in output"
            
            for station in validated.stations:
                assert station.official_name, "Missing official_name"
                assert len(station.mrt_codes) > 0, "Missing mrt_codes"
                assert len(station.exits) > 0, f"No exits for {station.official_name}"
            
            return True
        except Exception as e:
            logger.error(f"Output validation failed: {e}")
            return False
    
    def _run_completeness_check(self, output: Stage3Output):
        """Check that all expected data is present"""
        logger.subsection("Running Completeness Checks")
        
        issues = []
        
        # Check station count
        actual_count = len(output.stations)
        if actual_count < self.expected_stations:
            issues.append(f"Station count: expected {self.expected_stations}, got {actual_count}")
        
        # Check each station has required fields
        for station in output.stations:
            if not station.get("official_name"):
                issues.append(f"Missing official_name in station")
            if not station.get("mrt_codes"):
                issues.append(f"Missing mrt_codes in {station.get('official_name', 'unknown')}")
            if not station.get("exits"):
                issues.append(f"No exits in {station.get('official_name', 'unknown')}")
        
        if issues:
            for issue in issues:
                logger.warning(f"Completeness issue: {issue}")
        else:
            logger.success("All completeness checks passed")
    
    def _run_sanity_check(self, output: Stage3Output):
        """Run sanity checks on data values"""
        logger.subsection("Running Sanity Checks")
        
        issues = []
        
        # Check coordinates are in Singapore
        for station in output.stations:
            for exit_data in station.get("exits", []):
                lat = exit_data.get("lat")
                lng = exit_data.get("lng")
                
                if lat is not None:
                    if not (1.0 <= lat <= 2.0):
                        issues.append(f"Invalid latitude {lat} in {station['official_name']}")
                
                if lng is not None:
                    if not (103.0 <= lng <= 105.0):
                        issues.append(f"Invalid longitude {lng} in {station['official_name']}")
        
        # Check for duplicate station names
        names = [s["official_name"] for s in output.stations]
        duplicates = set([n for n in names if names.count(n) > 1])
        if duplicates:
            issues.append(f"Duplicate station names: {duplicates}")
        
        if issues:
            for issue in issues:
                logger.warning(f"Sanity check issue: {issue}")
        else:
            logger.success("All sanity checks passed")
    
    def save_checkpoint(self, output: Stage3Output, output_dir: str):
        """Save final output to file"""
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert to JSON-serializable dict
        output_dict = {
            "metadata": output.metadata,
            "stations": output.stations
        }
        
        filepath = os.path.join(output_dir, "stage3_final.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False, default=str)
        
        logger.success(f"Final output saved: {filepath}")
        
        # Also save as mrt_transit_graph.json (backward compatibility)
        compat_filepath = os.path.join(output_dir, "mrt_transit_graph.json")
        with open(compat_filepath, 'w', encoding='utf-8') as f:
            json.dump(output.stations, f, indent=2, ensure_ascii=False, default=str)
        
        logger.success(f"Backward compatibility output saved: {compat_filepath}")
        
        return filepath
```

### 2. Execution Script (scripts/run_stage3.py)

```python
#!/usr/bin/env python3
"""
Standalone script to run Stage 3: Data Merging & Validation

Usage:
    python scripts/run_stage3.py \
        --stage1 outputs/2026-02-07/stage1_deterministic.json \
        --stage2 outputs/2026-02-07/stage2_enrichment.json \
        --output-dir outputs/2026-02-07
"""

import argparse
import json
import os
import sys
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from contracts.schemas import Stage1Output, Stage2Output
from pipelines.stage3_merger import Stage3Merger
from utils.logger import logger

def main():
    parser = argparse.ArgumentParser(description='Run Stage 3: Data Merging & Validation')
    parser.add_argument('--stage1', required=True, help='Path to Stage 1 output JSON')
    parser.add_argument('--stage2', required=True, help='Path to Stage 2 output JSON')
    parser.add_argument('--output-dir', default='outputs/latest', help='Output directory')
    parser.add_argument('--config', default='config/pipeline.yaml', help='Config file path')
    args = parser.parse_args()
    
    # Load config
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)
    
    # Load Stage 1 output
    with open(args.stage1, 'r') as f:
        stage1_data = json.load(f)
    stage1_output = Stage1Output.model_validate(stage1_data)
    
    # Load Stage 2 output
    with open(args.stage2, 'r') as f:
        stage2_data = json.load(f)
    stage2_output = Stage2Output.model_validate(stage2_data)
    
    # Run stage
    stage = Stage3Merger(config)
    output = stage.execute((stage1_output, stage2_output))
    
    # Save checkpoint
    checkpoint_path = stage.save_checkpoint(output, args.output_dir)
    
    # Print summary
    logger.result("Stage 3 Complete")
    logger.stats("Total Stations", str(len(output.stations)))
    logger.stats("Enriched Stations", str(output.metadata.get('enriched_stations', 0)))
    logger.stats("Final Output", checkpoint_path)

if __name__ == "__main__":
    main()
```

### 3. Update enrichment_merger.py (Backward Compatibility)

Keep the existing `processors/enrichment_merger.py` but update imports:

```python
# Add deprecation warning and redirect to new implementation
import warnings
warnings.warn(
    "enrichment_merger is deprecated. Use pipelines.stage3_merger instead.",
    DeprecationWarning
)

# Re-export from new location
from src.pipelines.stage3_merger import Stage3Merger, merge_enrichment_data
```

---

## Success Criteria

1. [ ] `Stage3Merger` class implemented in `src/pipelines/stage3_merger.py`
2. [ ] Class implements `PipelineStage` interface
3. [ ] Correctly merges deterministic + enrichment data by station_id and exit_code
4. [ ] Validates output against FinalOutput Pydantic schema
5. [ ] Completeness check verifies station count and required fields
6. [ ] Sanity check verifies coordinates are in Singapore bounds
7. [ ] Handles missing enrichment data gracefully (uses deterministic only)
8. [ ] Normalizes exit codes for matching (case-insensitive, "Exit A" → "A")
9. [ ] Saves checkpoint as `stage3_final.json`
10. [ ] Also saves backward-compatible `mrt_transit_graph.json`
11. [ ] `python scripts/run_stage3.py --stage1 ... --stage2 ...` runs successfully

---

## Data Flow Example

### Input: Stage 1 Station
```json
{
  "station_id": "NS13",
  "official_name": "YISHUN MRT STATION",
  "display_name": "Yishun",
  "mrt_codes": ["NS13"],
  "lines": ["NSL"],
  "station_type": "mrt",
  "exits": [
    {"exit_code": "A", "lat": 1.429443, "lng": 103.835006, "source": "onemap"}
  ],
  "fandom_url": "https://singapore-mrt-lines.fandom.com/wiki/Yishun_MRT_Station"
}
```

### Input: Stage 2 Station
```json
{
  "station_id": "NS13",
  "official_name": "YISHUN MRT STATION",
  "extraction_result": "success",
  "extraction_confidence": "high",
  "exits": [
    {
      "exit_code": "A",
      "platforms": [{"platform_code": "A", "towards_code": "NS1", "line_code": "NS"}],
      "accessibility": ["wheelchair_accessible", "lift"],
      "bus_stops": [{"code": "12345", "services": ["123"]}],
      "nearby_landmarks": ["Yishun Mall"]
    }
  ],
  "accessibility_notes": ["All exits accessible"],
  "extraction_timestamp": "2026-02-07T10:05:00Z",
  "source_url": "https://singapore-mrt-lines.fandom.com/wiki/Yishun_MRT_Station"
}
```

### Output: Final Station
```json
{
  "official_name": "YISHUN MRT STATION",
  "mrt_codes": ["NS13"],
  "exits": [
    {
      "exit_code": "A",
      "lat": 1.429443,
      "lng": 103.835006,
      "platforms": [{"platform_code": "A", "towards_code": "NS1", "line_code": "NS"}],
      "accessibility": ["wheelchair_accessible", "lift"],
      "bus_stops": [{"code": "12345", "services": ["123"]}],
      "nearby_landmarks": ["Yishun Mall"]
    }
  ],
  "lines_served": ["NS"],
  "accessibility_notes": ["All exits accessible"],
  "enrichment_last_updated": "2026-02-07T10:05:00Z",
  "data_quality": {
    "extraction_confidence": "high",
    "source": "enrichment_data"
  }
}
```

---

## Configuration Requirements

Ensure `config/pipeline.yaml` has:

```yaml
stages:
  stage3_merger:
    enabled: true
    validation:
      schema_check: true
      completeness_check: true
      sanity_check: true

expected_stations: 187
```

---

## Dependencies

**Requires:**
- FEAT-001: Project Restructure & Data Contracts
- FEAT-002: Stage 1 - Deterministic Data Ingestion
- FEAT-003: Stage 2 - Enrichment Extraction Pipeline

**Required By:**
- FEAT-005: Pipeline Orchestrator & Configuration
- FEAT-006: Alerting, Testing & Automation

---

## Validation Logic Details

### Exit Code Matching
The merger normalizes exit codes to handle variations:
- "Exit A" → "A"
- "EXIT B" → "B"
- "1" → "1"
- "  a  " → "A"

This ensures deterministic exit "A" matches enrichment exit "Exit A".

### Enrichment Data Handling
If Stage 2 has no data for a station:
- Use deterministic exit data only (exit_code, lat, lng)
- Omit enrichment fields (platforms, accessibility, etc.)
- Don't add enrichment_last_updated or data_quality

If Stage 2 has data but missing an exit:
- Still use deterministic data for that exit
- Only add enrichment fields for matched exits

### Line Detection
Lines served are extracted from platform data:
- Collect all unique `line_code` values from platforms
- Return sorted list (e.g., ["CCL", "DTL"] for interchange)

---

## Implementation Notes

### Schema Clarification
The specification originally mentioned `Stage3Output`, but this schema does not exist in the codebase. The implementation correctly uses `FinalOutput` from `src.contracts.schemas` as the return type for Stage 3. This is the appropriate schema for the final pipeline output.

### Improvements Over Specification
The actual implementation includes several enhancements beyond the original specification:

1. **Enhanced Exit Code Normalization**
   - Handles edge cases like empty codes or "EXIT" without identifier
   - Prevents crashes from malformed exit codes

2. **Stage 2-Only Exit Preservation**
   - The spec states to ignore enrichment exits not in deterministic data
   - Implementation actually preserves these exits with a warning log
   - Uses placeholder coordinates (0.0, 0.0) for exits only found in Stage 2
   - Prevents data loss from enrichment extraction

3. **Optimized Validation**
   - Spec showed double conversion (to dict then back to Pydantic)
   - Implementation validates Pydantic objects directly
   - More efficient and type-safe

### Backward Compatibility
The deprecated `enrichment_merger.py` module:
- Includes deprecation warning as specified
- Re-exports `Stage3Merger` from new location for compatibility
- Maintains old `EnrichmentMerger` class for existing code

