"""
Stage 3: Data Merging & Validation

This stage handles merging deterministic data with enrichment data
and performs final validation and quality checks.
"""

import json
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from ..contracts.interfaces import PipelineStage
from ..contracts.schemas import (
    FinalOutput, FinalStation, FinalExit,
    Stage1Output, Stage2Output, Stage1Station, Stage2Station,
    EnrichedExit, Platform, BusStop
)
from ..utils.logger import logger


class Stage3Merger(PipelineStage):
    """
    Stage 3: Merge deterministic and enrichment data, validate final output.

    Input: Tuple[Stage1Output, Stage2Output]
    Output: FinalOutput (mrt_transit_graph.json format)
    """
    
    def __init__(self, config: dict):
        self.config = config
        # Handle both nested 'pipeline' structure and flat structure
        pipeline_config = config.get('pipeline', config)
        self.stage_config = pipeline_config.get('stages', {}).get('stage3_merger', {})
        self.validation_config = self.stage_config.get('validation', {})
        self.expected_stations = pipeline_config.get('expected_stations', 187)
    
    @property
    def stage_name(self) -> str:
        return "stage3_merger"
    
    def execute(self, input_data: Tuple[Stage1Output, Stage2Output]) -> FinalOutput:
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
        logger.section("Stage 3: Data Merging & Validation")
        
        if not self.validate_input(input_data):
            raise ValueError("Invalid input for Stage 3")
        
        stage1_output, stage2_output = input_data
        
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
        
        # Validation (if enabled in config)
        if self.validation_config.get('schema_check', True):
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
    ) -> List[FinalStation]:
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
    ) -> FinalStation:
        """
        Merge a single station's data.
        
        Strategy:
        - Start with deterministic data (Stage 1)
        - Add enrichment data where available (Stage 2)
        - Match exits by exit_code (case-insensitive, normalize formats)
        """
        # Start with deterministic data
        merged_data = {
            "official_name": station1.official_name,
            "mrt_codes": station1.mrt_codes,
            "exits": []
        }
        
        # Merge exits
        if station2:
            merged_data["exits"] = self._merge_exits(
                station1.exits, 
                station2.exits,
                station1.station_id
            )
            
            # Add enrichment metadata
            if station2.extraction_result == "success":
                merged_data["lines_served"] = self._extract_lines_served(station2)
                merged_data["accessibility_notes"] = station2.accessibility_notes
                merged_data["enrichment_last_updated"] = station2.extraction_timestamp
                merged_data["data_quality"] = {
                    "extraction_confidence": station2.extraction_confidence,
                    "source": "enrichment_data"
                }
        else:
            # No enrichment data - use deterministic exits only
            merged_data["exits"] = [
                FinalExit(
                    exit_code=e.exit_code,
                    lat=e.lat,
                    lng=e.lng
                )
                for e in station1.exits
            ]
        
        return FinalStation(**merged_data)
    
    def _merge_exits(
        self,
        deterministic_exits: List[Any],
        enrichment_exits: List[EnrichedExit],
        station_id: str
    ) -> List[FinalExit]:
        """
        Merge exit data from both sources.

        Matches exits by normalized exit code.
        """
        # Create lookup by normalized exit code (skip entries with empty codes)
        enrichment_by_code = {}
        for exit_data in enrichment_exits:
            code = self._normalize_exit_code(exit_data.exit_code)
            if code:  # Skip empty/invalid exit codes
                enrichment_by_code[code] = exit_data

        merged_exits = []
        matched_enrichment_codes = set()

        for det_exit in deterministic_exits:
            norm_code = self._normalize_exit_code(det_exit.exit_code)
            if not norm_code:
                logger.warning(f"Station {station_id}: Skipping exit with empty/invalid exit_code")
                continue

            # Start with deterministic data
            merged_exit = FinalExit(
                exit_code=det_exit.exit_code,
                lat=det_exit.lat,
                lng=det_exit.lng
            )

            # Add enrichment if available
            if norm_code in enrichment_by_code:
                enrichment = enrichment_by_code[norm_code]
                matched_enrichment_codes.add(norm_code)

                if enrichment.platforms:
                    merged_exit.platforms = enrichment.platforms

                if enrichment.accessibility:
                    merged_exit.accessibility = enrichment.accessibility

                if enrichment.bus_stops:
                    merged_exit.bus_stops = enrichment.bus_stops

                if enrichment.nearby_landmarks:
                    merged_exit.nearby_landmarks = enrichment.nearby_landmarks

            merged_exits.append(merged_exit)

        # Check for enrichment exits not in deterministic data
        for norm_code, enrichment in enrichment_by_code.items():
            if norm_code not in matched_enrichment_codes:
                logger.warning(
                    f"Station {station_id}: Exit '{enrichment.exit_code}' found in "
                    f"enrichment but not in deterministic data. Skipping - cannot add exit without valid coordinates."
                )
                # Skip exits that don't have deterministic coordinate data
                # This prevents schema validation failures from placeholder coordinates

        return merged_exits
    
    def _normalize_exit_code(self, code: str) -> str:
        """
        Normalize exit code for matching.

        Examples:
        - "Exit A" → "A"
        - "Exit 1" → "1"
        - "A" → "A"
        - "  a  " → "A"
        - "EXIT" → "" (no identifier)
        """
        if not code:
            return ""
        
        code = str(code).upper().strip()
        if not code:
            return ""
        
        # Remove "EXIT" prefix/suffix
        code = code.replace("EXIT ", "").replace("EXIT", "")
        normalized = code.strip()
        
        return normalized
    
    def _extract_lines_served(self, station2: Stage2Station) -> List[str]:
        """Extract unique line codes from enrichment data"""
        lines = set()
        for exit_data in station2.exits:
            if exit_data.platforms:
                for platform in exit_data.platforms:
                    if hasattr(platform, 'line_code'):
                        lines.add(platform.line_code)
                    elif isinstance(platform, dict):
                        line_code = platform.get('line_code')
                        if line_code:  # Filter out None/empty values
                            lines.add(line_code)
        return sorted(list(lines))
    
    def validate_input(self, input_data: Tuple[Stage1Output, Stage2Output]) -> bool:
        """Validate Stage 1 and Stage 2 outputs"""
        try:
            # Check tuple length first
            if not isinstance(input_data, tuple) or len(input_data) != 2:
                raise AssertionError("Input must be tuple of (Stage1Output, Stage2Output)")
            
            stage1, stage2 = input_data
            
            assert isinstance(stage1, Stage1Output), "First input must be Stage1Output"
            assert isinstance(stage2, Stage2Output), "Second input must be Stage2Output"
            assert len(stage1.stations) > 0, "Stage 1 has no stations"
            return True
        except Exception as e:
            logger.error(f"Input validation failed: {e}")
            return False
    
    def validate_output(self, output_data: FinalOutput) -> bool:
        """Validate final output against schema"""
        try:
            # Validate directly using Pydantic model
            # This will catch schema violations and type errors
            assert isinstance(output_data, FinalOutput), "Output must be FinalOutput instance"
            assert len(output_data.stations) > 0, "No stations in output"

            for station in output_data.stations:
                assert station.official_name, "Missing official_name"
                assert len(station.mrt_codes) > 0, "Missing mrt_codes"
                assert len(station.exits) > 0, f"No exits for {station.official_name}"

            return True
        except Exception as e:
            logger.error(f"Output validation failed: {e}")
            return False
    
    def _run_completeness_check(self, output: FinalOutput):
        """Check that all expected data is present"""
        logger.subsection("Running Completeness Checks")
        
        issues = []
        
        # Check station count
        actual_count = len(output.stations)
        if actual_count < self.expected_stations:
            issues.append(f"Station count: expected {self.expected_stations}, got {actual_count}")
        
        # Check each station has required fields
        for station in output.stations:
            if not station.official_name:
                issues.append("Missing official_name in station")
            if not station.mrt_codes:
                issues.append(f"Missing mrt_codes in {station.official_name}")
            if not station.exits:
                issues.append(f"No exits in {station.official_name}")
        
        if issues:
            for issue in issues:
                logger.warning(f"Completeness issue: {issue}")
        else:
            logger.success("All completeness checks passed")
    
    def _run_sanity_check(self, output: FinalOutput):
        """Run sanity checks on data values"""
        logger.subsection("Running Sanity Checks")
        
        issues = []
        
        # Check coordinates are in Singapore
        for station in output.stations:
            for exit_data in station.exits:
                lat = exit_data.lat
                lng = exit_data.lng
                
                if lat is not None:
                    if not (1.0 <= lat <= 2.0):
                        issues.append(f"Invalid latitude {lat} in {station.official_name}")
                
                if lng is not None:
                    if not (103.0 <= lng <= 105.0):
                        issues.append(f"Invalid longitude {lng} in {station.official_name}")
        
        # Check for duplicate station names (optimized using Counter)
        from collections import Counter
        name_counts = Counter(s.official_name for s in output.stations)
        duplicates = {name for name, count in name_counts.items() if count > 1}
        if duplicates:
            issues.append(f"Duplicate station names: {duplicates}")
        
        if issues:
            for issue in issues:
                logger.warning(f"Sanity check issue: {issue}")
        else:
            logger.success("All sanity checks passed")
    
    def save_checkpoint(self, output: FinalOutput, output_dir: str) -> str:
        """Save final output to file"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert to JSON-serializable dict with custom datetime serializer
        def serialize_datetime(obj):
            if isinstance(obj, datetime):
                # Handle timezone-aware datetimes by converting to ISO format
                if obj.tzinfo is not None:
                    return obj.isoformat()
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
        
        output_dict = output.model_dump(mode='json')
        
        filepath = os.path.join(output_dir, "stage3_final.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False, default=serialize_datetime)
        
        logger.success(f"Final output saved: {filepath}")
        
        # Also save as mrt_transit_graph.json (backward compatibility)
        compat_filepath = os.path.join(output_dir, "mrt_transit_graph.json")
        with open(compat_filepath, 'w', encoding='utf-8') as f:
            json.dump(output.stations, f, indent=2, ensure_ascii=False, default=str)
        
        logger.success(f"Backward compatibility output saved: {compat_filepath}")
        
        return filepath


def merge_enrichment_data(
    stage1_output: Stage1Output,
    stage2_output: Stage2Output,
    config: Optional[dict] = None
) -> FinalOutput:
    """
    Convenience function to merge enrichment data with deterministic data.

    This is a high-level wrapper around Stage3Merger for simple use cases.

    Args:
        stage1_output: Stage 1 deterministic data output
        stage2_output: Stage 2 enrichment data output
        config: Optional configuration dict (uses defaults if not provided)

    Returns:
        FinalOutput: The merged and validated final output

    Example:
        from src.pipelines.stage3_merger import merge_enrichment_data
        from src.contracts.schemas import Stage1Output, Stage2Output

        final_output = merge_enrichment_data(stage1_data, stage2_data)
    """
    if config is None:
        config = {
            'stages': {
                'stage3_merger': {
                    'enabled': True,
                    'validation': {
                        'schema_check': True,
                        'completeness_check': True,
                        'sanity_check': True
                    }
                }
            },
            'expected_stations': 187
        }

    merger = Stage3Merger(config)
    return merger.execute((stage1_output, stage2_output))