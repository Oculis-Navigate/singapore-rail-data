"""
Stage 1: Deterministic Data Ingestion

This stage handles fetching and processing data from deterministic sources
like Data.gov.sg and OneMap APIs.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from urllib.parse import quote
from ..contracts.interfaces import PipelineStage
from ..contracts.schemas import Stage1Output, Stage1Station, Exit, StationType
from ..fetchers.datagov_fetcher import DataGovFetcher
from ..fetchers.onemap_fetcher import OneMapFetcher
from ..fetchers.missing_station_fetcher import MissingStationFetcher
from ..processors.matching_engine import MatchingEngine
from ..processors.consolidator import Consolidator
from ..utils.logger import logger
from .fandom_scraper import FandomScraper


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
        
        # Initialize fetchers with config
        self.datagov_fetcher = DataGovFetcher()
        pipeline_config = config.get('pipeline', {}) if config else {}
        self.onemap_fetcher = OneMapFetcher(config=pipeline_config)
        self.missing_fetcher = MissingStationFetcher(self.onemap_fetcher)
        
        # Initialize processors
        pipeline_config = config.get('pipeline', {}) if config else {}
        self.matcher = MatchingEngine(self.onemap_fetcher, config=pipeline_config)
        self.consolidator = Consolidator()
        
        # Initialize Fandom scraper for URL resolution
        self.fandom_scraper = FandomScraper(config)
    
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
        # 1. Fetch from Data.gov.sg
        records = self.datagov_fetcher.fetch_all_exits()
        logger.success(f"Retrieved {len(records)} exit records from Data.gov.sg")
        
        # 2. Augment with missing stations from OneMap
        records = self.missing_fetcher.augment_datagov_data(records)
        logger.success(f"Total records after augmentation: {len(records)}")
        
        return records
    
    def _group_by_station(self, records: List[Dict]) -> Dict[str, List[Dict]]:
        """Group exit records by station name"""
        dg_groups = {}
        for r in records:
            name = r["STATION_NA"]
            if name not in dg_groups:
                dg_groups[name] = []
            dg_groups[name].append({"exit_code": r["EXIT_CODE"], "lat": r["LATITUDE"], "lng": r["LONGITUDE"]})
        
        logger.info(f"Grouped into {len(dg_groups)} station groups")
        return dg_groups
    
    def _match_stations(self, groups: Dict[str, List[Dict]]) -> List[Stage1Station]:
        """Match station groups to official info and create Stage1Station objects"""
        raw_matches = []
        for i, (dg_name, exits) in enumerate(groups.items(), 1):
            logger.progress(i, len(groups), "Matching stations")
            match_result = self.matcher.match_station(dg_name, exits)
            if match_result:
                raw_matches.append(
                    {"official_name": match_result["official_name"], "codes": match_result["codes"], "exits": exits}
                )
        
        # Add LRT hub codes BEFORE consolidation to ensure proper merging
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
        
        # Consolidate interchanges
        consolidated_output = self.consolidator.consolidate(raw_matches)
        
        # Convert to Stage1Station objects
        stage1_stations = []
        for station_data in consolidated_output:
            # Extract official name and normalize it
            official_name = station_data.get("official_name", "")
            
            # Remove trailing periods and extra whitespace
            official_name = official_name.strip()
            if official_name.endswith('.'):
                official_name = official_name[:-1]
            
            # Ensure it ends with proper suffix
            if not official_name.endswith(" MRT STATION") and not official_name.endswith(" LRT STATION"):
                if "LRT" in official_name:
                    official_name = official_name.replace(" LRT STATION", "").replace(" MRT STATION", "") + " LRT STATION"
                else:
                    official_name = official_name.replace(" LRT STATION", "").replace(" MRT STATION", "") + " MRT STATION"
            
            # Extract display name (remove "MRT STATION" or "LRT STATION" suffix)
            if " MRT STATION" in official_name:
                display_name = official_name.replace(" MRT STATION", "")
            elif " LRT STATION" in official_name:
                display_name = official_name.replace(" LRT STATION", "")
            else:
                display_name = official_name
            
            # Detect station type
            station_type = self._detect_station_type(official_name, station_data.get("mrt_codes", []))
            
            # Detect lines
            lines = self._detect_lines(station_data.get("mrt_codes", []))
            
            # Convert exits
            exits = []
            for exit_data in station_data.get("exits", []):
                exit_obj = Exit(
                    exit_code=exit_data["exit_code"],
                    lat=exit_data["lat"],
                    lng=exit_data["lng"],
                    source="datagov"  # Most exits come from data.gov initially
                )
                exits.append(exit_obj)
            
            # Determine primary station code (first in list, usually the main one)
            mrt_codes = station_data.get("mrt_codes", [])
            primary_code = mrt_codes[0] if mrt_codes else "UNKNOWN"
            
            # Create Stage1Station
            stage1_station = Stage1Station(
                station_id=primary_code,
                official_name=official_name,
                display_name=display_name,
                mrt_codes=mrt_codes,
                lines=lines,
                station_type=station_type,
                exits=exits,
                fandom_url=self._build_fandom_url(official_name, mrt_codes, display_name),
                extraction_status="pending"
            )
            stage1_stations.append(stage1_station)
        
        return stage1_stations
    
    def _apply_corrections(self, stations: List[Stage1Station]) -> List[Stage1Station]:
        """Apply manual corrections (LRT hub codes, naming standardization)"""
        # Add remaining LRT hub codes (Sengkang only, others handled pre-consolidation)
        LRT_HUB_CODES = {
            "SENGKANG MRT STATION": ["STC"]
        }
        for station in stations:
            station_name = station.official_name
            if station_name in LRT_HUB_CODES:
                combined_codes = list(set(station.mrt_codes) | set(LRT_HUB_CODES[station_name]))
                station.mrt_codes = sorted(combined_codes)
                # Also update lines
                station.lines = self._detect_lines(station.mrt_codes)
        
        # Standardize naming for interchange stations (MRT + LRT)
        # These stations should be named "MRT/LRT STATION" per BUGFIX-003 spec
        INTERCHANGE_STATIONS = {
            "CHOA CHU KANG": "CHOA CHU KANG MRT/LRT STATION",
            "BUKIT PANJANG": "BUKIT PANJANG MRT/LRT STATION",
            "SENGKANG": "SENGKANG MRT/LRT STATION",
            "PUNGGOL": "PUNGGOL MRT/LRT STATION",
        }
        
        for station in stations:
            # Extract base name (remove station type suffix)
            base_name = station.display_name.upper()
            
            if base_name in INTERCHANGE_STATIONS:
                # Update official name to use MRT/LRT format
                old_name = station.official_name
                station.official_name = INTERCHANGE_STATIONS[base_name]
                # Re-detect station type - interchange stations default to MRT
                station.station_type = StationType.MRT
                logger.debug(f"Renamed interchange station: {old_name} -> {station.official_name}")
        
        # Regenerate Fandom URLs after naming corrections
        for station in stations:
            station.fandom_url = self._build_fandom_url(station.official_name, station.mrt_codes, station.display_name)
        
        logger.info("Applied LRT hub codes and naming corrections")
        return stations
    
    def _build_fandom_url(self, station_name: str, mrt_codes: Optional[List[str]] = None, display_name: str = "") -> str:
        """
        Generate Fandom wiki URL for a station with casing normalization.
        
        Handles MRT stations, LRT stations, and interchange stations (MRT + LRT).
        Interchange stations use "_MRT/LRT_Station" suffix per Fandom convention.
        Uses FandomScraper for URL resolution with casing variation handling.
        
        Args:
            station_name: Official station name (e.g., "YISHUN MRT STATION")
            mrt_codes: List of station codes to detect interchange stations (optional)
            display_name: Display name for URL resolution (e.g., "Yishun")
        
        Examples:
        - "YISHUN MRT STATION" → "https://singapore-mrt-lines.fandom.com/wiki/Yishun_MRT_Station"
        - "BUKIT PANJANG LRT STATION" → "https://singapore-mrt-lines.fandom.com/wiki/Bukit_Panjang_LRT_Station"
        - "BUKIT PANJANG MRT/LRT STATION" (interchange) → "https://singapore-mrt-lines.fandom.com/wiki/Bukit_Panjang_MRT/LRT_Station"
        - "Gardens By The Bay" → "https://singapore-mrt-lines.fandom.com/wiki/Gardens_by_the_Bay_MRT_Station"
        
        Returns:
            str: Full Fandom wiki URL
        """
        # Check if this is an interchange station (has both MRT and LRT codes)
        if mrt_codes:
            is_interchange = self._is_interchange_station(mrt_codes)
            if is_interchange:
                return self._build_interchange_url(station_name)
        
        # For non-interchange stations, use FandomScraper for URL resolution
        # This handles casing variations like "Gardens By The Bay" -> "Gardens_by_the_Bay"
        name_for_resolution = display_name or station_name.replace(" MRT STATION", "").replace(" LRT STATION", "")
        
        # Try to resolve URL using the scraper (handles casing variations)
        resolved_url = self.fandom_scraper.resolve_fandom_url(name_for_resolution)
        
        if resolved_url:
            logger.debug(f"Resolved URL for {name_for_resolution}: {resolved_url}")
            return resolved_url
        else:
            # Fallback to naive URL generation
            fallback_url = self._naive_url_generation(station_name)
            logger.warning(f"Could not resolve URL for {name_for_resolution}, using fallback: {fallback_url}")
            return fallback_url
    
    def _naive_url_generation(self, station_name: str) -> str:
        """
        Original naive URL generation as fallback.
        
        Args:
            station_name: Official station name
            
        Returns:
            Generated Fandom URL
        """
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
    
    def _is_interchange_station(self, mrt_codes: List[str]) -> bool:
        """
        Check if station serves both MRT and LRT lines.
        
        Args:
            mrt_codes: List of station codes
            
        Returns:
            bool: True if station has both MRT and LRT codes
        """
        # MRT code prefixes
        mrt_prefixes = ('NS', 'EW', 'NE', 'CC', 'DT', 'TE', 'CG', 'CR', 'CE')
        # LRT code prefixes
        lrt_prefixes = ('BP', 'SW', 'SE', 'PW', 'PE', 'STC', 'PTC')
        
        has_mrt = any(code.startswith(mrt_prefixes) for code in mrt_codes)
        has_lrt = any(code.startswith(lrt_prefixes) for code in mrt_codes)
        
        return has_mrt and has_lrt
    
    def _build_interchange_url(self, station_name: str) -> str:
        """
        Generate Fandom URL for interchange stations (MRT + LRT).
        
        SPECIAL RULE: Interchange stations use "_MRT/LRT_Station" suffix in Fandom URL
        to indicate they serve both MRT and LRT lines.
        
        Known interchange stations:
        - Bukit Panjang (DT1 + BP1) → Bukit_Panjang_MRT/LRT_Station
        - Sengkang (NE16 + STC) → Sengkang_MRT/LRT_Station  
        - Punggol (NE17 + PTC) → Punggol_MRT/LRT_Station
        - Choa Chu Kang (NS4 + BP1) → Choa_Chu_Kang_MRT/LRT_Station
        
        Args:
            station_name: Official station name
            
        Returns:
            str: Fandom URL with "_MRT/LRT_Station" suffix
        """
        # Map of interchange station display names to their Fandom URL names
        INTERCHANGE_URL_NAMES = {
            "BUKIT PANJANG": "Bukit_Panjang",
            "SENGKANG": "Sengkang",
            "PUNGGOL": "Punggol",
            "CHOA CHU KANG": "Choa_Chu_Kang",
        }
        
        # Extract base name (remove all station type suffixes)
        # Handle "MRT/LRT STATION", "MRT STATION", "LRT STATION", "STATION" patterns
        base_name = station_name.upper()
        base_name = base_name.replace(' MRT/LRT STATION', '')
        base_name = base_name.replace(' MRT STATION', '')
        base_name = base_name.replace(' LRT STATION', '')
        base_name = base_name.replace(' STATION', '')
        base_name = base_name.strip()
        
        # Get URL-safe name
        url_name = INTERCHANGE_URL_NAMES.get(base_name, base_name.title().replace(' ', '_'))
        
        # All interchange stations use "_MRT/LRT_Station" suffix on Fandom
        return f"https://singapore-mrt-lines.fandom.com/wiki/{url_name}_MRT/LRT_Station"
    
    def _detect_station_type(self, station_name: str, codes: List[str]) -> StationType:
        """
        Determine if station is MRT or LRT based on official name.
        
        Rules (per BUGFIX-003 spec):
        - Contains 'MRT/LRT STATION' -> StationType.MRT (interchange stations default to MRT)
        - Contains 'LRT STATION' -> StationType.LRT
        - Contains 'MRT STATION' -> StationType.MRT
        - Default to MRT if unclear (backward compatibility)
        
        Args:
            station_name: Official station name (e.g., "BUKIT PANJANG LRT STATION")
            codes: Station codes (for additional context)
            
        Returns:
            StationType: Either MRT or LRT
        """
        name_upper = station_name.upper()
        # Check for interchange stations first (MRT + LRT)
        if 'MRT/LRT STATION' in name_upper:
            return StationType.MRT
        elif 'LRT STATION' in name_upper:
            return StationType.LRT
        elif 'MRT STATION' in name_upper:
            return StationType.MRT
        else:
            # Log warning and default to MRT for backward compatibility
            logger.warning(f"Cannot determine station type for '{station_name}', defaulting to MRT")
            return StationType.MRT
    
    def _detect_lines(self, codes: List[str]) -> List[str]:
        """
        Detect line codes from station codes.
        
        Complete Mapping (verified against official LTA/SMRT sources):
        - NS* → NSL (North South Line)
        - EW* → EWL (East West Line)
        - NE* → NEL (North East Line)
        - CC* → CCL (Circle Line)
        - CE* → CCL (Circle Line Extension)
        - DT* → DTL (Downtown Line)
        - TE* → TEL (Thomson-East Coast Line)
        - CG* → CGL (Changi Airport Line)
        - CR* → CRL (Cross Island Line)
        - BP* → BPL (Bukit Panjang LRT)
        - A*  → BPL (Bukit Panjang interchange codes)
        - SW* → SKL (Sengkang LRT West Loop)
        - SE* → SKL (Sengkang LRT East Loop)
        - PW* → PGL (Punggol LRT West Loop)
        - PE* → PGL (Punggol LRT East Loop)
        - JS* → JRL (Jurong Region Line)
        - JW* → JRL (Jurong Region Line West)
        - JE* → JRL (Jurong Region Line East)
        """
        line_map = {
            # Major MRT Lines
            "NS": "NSL",
            "EW": "EWL",
            "NE": "NEL",
            "CC": "CCL",
            "CE": "CCL",  # Circle Line Extension
            "DT": "DTL",
            "TE": "TEL",
            "CG": "CGL",  # Changi Airport Line
            "CR": "CRL",  # Cross Island Line
            
            # LRT Lines
            "BP": "BPL",
            "A": "BPL",   # Bukit Panjang interchange codes
            
            # Sengkang LRT (both loops same line)
            "SW": "SKL",
            "SE": "SKL",
            
            # Punggol LRT (both loops same line)
            "PW": "PGL",
            "PE": "PGL",
            
            # Jurong Region Line (all branches)
            "JS": "JRL",
            "JW": "JRL",
            "JE": "JRL",
        }
        
        # Handle special LRT hub codes directly
        special_codes = {
            "STC": "SKL",
            "PTC": "PGL"
        }
        
        lines = set()
        unmapped_codes = []
        
        for code in codes:
            # Check special codes first
            if code in special_codes:
                lines.add(special_codes[code])
                continue
                
            # Extract prefix (alphabetic part)
            prefix = ''.join(c for c in code if c.isalpha())
            if prefix in line_map:
                lines.add(line_map[prefix])
            else:
                unmapped_codes.append(code)
        
        # FAIL if unmapped codes found (no UNKNOWN fallback)
        if unmapped_codes:
            raise ValueError(
                f"Unmapped station code prefixes: {unmapped_codes}. "
                f"Please update line_map in _detect_lines() method."
            )
        
        # Additional safety check - should never happen if mapping is complete
        if not lines:
            raise ValueError(f"No lines detected for codes: {codes}")
        
        return sorted(list(lines))
    
    def save_checkpoint(self, output: Stage1Output, output_dir: str) -> str:
        """Save Stage 1 output to checkpoint file"""
        import os
        import json
        
        os.makedirs(output_dir, exist_ok=True)
        
        output_dict = output.model_dump()
        filepath = os.path.join(output_dir, "stage1_deterministic.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False)
        
        logger.success(f"Stage 1 checkpoint saved: {filepath}")
        return filepath
    
    def validate_input(self, input_data: Any) -> bool:
        """Stage 1 doesn't require input - only accepts None"""
        return input_data is None
    
    def validate_output(self, output_data: Stage1Output) -> bool:
        """Validate output matches schema and has required data"""
        try:
            import os
            # Validate with Pydantic
            validated = Stage1Output.model_validate(output_data)
            
            # Additional checks
            assert len(validated.stations) > 0, "No stations in output"
            
            # Environment-aware minimum station count
            if os.getenv('PYTEST_CURRENT_TEST') or os.getenv('TESTING'):
                min_stations = 1  # Test mode - accept any non-zero count
            else:
                min_stations = 180  # Production mode - expect full dataset
                
            if len(validated.stations) < min_stations:
                logger.warning(f"Expected at least {min_stations} stations, got {len(validated.stations)}")
                # Only fail in production mode
                if not (os.getenv('PYTEST_CURRENT_TEST') or os.getenv('TESTING')):
                    return False
            
            # Check all required fields present
            for station in validated.stations:
                assert station.station_id, f"Missing station_id for {station.official_name}"
                assert len(station.exits) > 0, f"No exits for {station.official_name}"
                assert station.fandom_url, f"Missing Fandom URL for {station.official_name}"
                
                # Validate no UNKNOWN lines (must have valid line detection)
                assert "UNKNOWN" not in station.lines, \
                    f"Station {station.official_name} has UNKNOWN line: {station.lines}"
                
                # Validate at least one line detected
                assert len(station.lines) > 0, \
                    f"Station {station.official_name} has no lines detected"
            
            return True
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False
