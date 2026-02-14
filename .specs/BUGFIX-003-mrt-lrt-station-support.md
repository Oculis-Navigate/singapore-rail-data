# Bugfix: MRT/LRT Station Type Support

## Bugfix ID: BUGFIX-003
**Priority:** P1 (Critical - affects data completeness)
**Estimated Effort:** 1-2 hours
**Dependencies:** FEAT-002

---

## Context

### Current State
- The pipeline currently focuses on MRT stations but doesn't explicitly handle LRT stations
- LRT stations (e.g., Bukit Panjang LRT, Sengkang LRT, Punggol LRT) exist in Singapore's transit network
- Stage 1 may be filtering out or mishandling LRT stations
- The `StationType` enum exists in schemas but may not be properly utilized
- Data sources (data.gov.sg, OneMap) include both MRT and LRT station data

### Problem
1. LRT stations are not being processed through the pipeline
2. No clear separation between MRT and LRT stations in the output
3. Fandom URLs for LRT stations may have different naming conventions
4. Stage 1 ingestion may be hardcoded to only look for "MRT" in station names
5. Downstream consumers expect both MRT and LRT data

### Goal
Ensure the pipeline correctly identifies, processes, and outputs both MRT and LRT stations with proper type classification throughout all stages.

---

## Requirements

### 1. Update Station Type Detection (src/pipelines/stage1_ingestion.py)

Modify the Stage 1 ingestion logic to:

```python
from src.contracts.schemas import StationType

def determine_station_type(station_name: str) -> StationType:
    """
    Determine if station is MRT or LRT based on official name.
    
    Rules:
    - Contains 'LRT STATION' -> StationType.LRT
    - Contains 'MRT STATION' -> StationType.MRT
    - Default to MRT if unclear (backward compatibility)
    """
    name_upper = station_name.upper()
    if 'LRT STATION' in name_upper:
        return StationType.LRT
    elif 'MRT STATION' in name_upper:
        return StationType.MRT
    else:
        # Log warning and default to MRT
        logger.warning(f"Cannot determine station type for '{station_name}', defaulting to MRT")
        return StationType.MRT
```

**Implementation Notes:**
- Station names from data.gov.sg follow pattern: "BUKIT PANJANG LRT STATION" or "YISHUN MRT STATION"
- Update all places where station type is inferred
- Ensure StationType enum is properly imported and used
- The `_detect_lines()` method should read station code prefixes from the same config to ensure consistency

### 1b. Fix Station Code Extraction (src/processors/matching_engine.py + config/pipeline.yaml)

**Problem:** The current regex extracts single-letter codes like A1, A2 as station codes when they are actually exit codes from OneMap building names (e.g., "BUKIT PANJANG MRT STATION (A1)").

**Solution:** Make the regex a configurable parameter so new station code prefixes can be added without code changes.

**Config changes (config/pipeline.yaml):**
```yaml
station_code_prefixes:
  # Operational MRT Lines
  - NS  # North South Line
  - EW  # East West Line
  - NE  # North East Line
  - CC  # Circle Line
  - CE  # Circle Line Extension
  - DT  # Downtown Line
  - TE  # Thomson-East Coast Line
  - CG  # Changi Airport Line
  # Operational LRT Lines
  - BP  # Bukit Panjang LRT
  - SW  # Sengkang LRT West Loop
  - SE  # Sengkang LRT East Loop
  - PW  # Punggol LRT West Loop
  - PE  # Punggol LRT East Loop
  - STC # Sengkang Town Centre
  - PTC # Punggol Town Centre
  # Under Construction (Future Lines)
  - CR  # Cross Island Line (opening 2030-2032)
  - JS  # Jurong Region Line Central (opening 2027)
  - JW  # Jurong Region Line West (opening 2027)
  - JE  # Jurong Region Line East (opening 2028)
```

**Code changes (matching_engine.py):**
```python
# OLD (hardcoded regex, incorrectly matches A1, B2 as station codes)
self.code_regex = r'([A-Z]{1,3}\d+|\b(?:NS|EW|NE|CC|DT|TE|BP|SW|SE|PW|STC|PTC)\b)'

# NEW (read from config)
import re
prefixes = config.get('station_code_prefixes', [])
if prefixes:
    prefix_pattern = '|'.join(prefixes)
    self.code_regex = rf'\b({prefix_pattern})\d*\b'
else:
    # Fallback to default if config not available
    self.code_regex = r'\b(NS|EW|NE|CC|DT|TE|CG|CE|BP|SW|SE|PW|PE|STC|PTC)\d*\b'
```

**Key points:**
- Single letters like A, B, C followed by numbers are EXIT codes, NOT station codes
- Future lines (CR, JS, JW, JE) are included so the pipeline is ready when they open
- Adding new prefixes only requires updating the config file, no code changes needed

### 2. Update Fandom URL Generation

Modify URL generation to handle MRT, LRT, and interchange stations:

```python
def generate_fandom_url(station_name: str, station_type: StationType, 
                        mrt_codes: List[str]) -> str:
    """
    Generate Fandom wiki URL for a station.
    
    Examples:
    - "Yishun MRT Station" -> "https://singapore-mrt-lines.fandom.com/wiki/Yishun_MRT_Station"
    - "Senja LRT Station" -> "https://singapore-mrt-lines.fandom.com/wiki/Senja_LRT_Station"
    - "Bukit Panjang MRT/LRT Station" (interchange) -> "https://singapore-mrt-lines.fandom.com/wiki/Bukit_Panjang_MRT/LRT_Station"
    """
    # Check if this is an interchange station (has both MRT and LRT codes)
    has_mrt = any(code.startswith(('NS', 'EW', 'NE', 'CC', 'DT', 'TE')) for code in mrt_codes)
    has_lrt = any(code.startswith(('BP', 'STC', 'PTC', 'SW', 'SE', 'PW', 'PE')) for code in mrt_codes)
    
    is_interchange = has_mrt and has_lrt
    
    if is_interchange:
        # Special handling for interchange stations
        return generate_interchange_url(station_name, mrt_codes)
    
    # Standard URL generation for non-interchange stations
    suffix = "LRT_Station" if station_type == StationType.LRT else "MRT_Station"
    url_name = station_name.replace(' ', '_')
    return f"https://singapore-mrt-lines.fandom.com/wiki/{url_name}_{suffix}"


def generate_interchange_url(station_name: str, mrt_codes: List[str]) -> str:
    """
    Generate Fandom URL for interchange stations (MRT + LRT).
    
    SPECIAL RULE: Interchange stations use "_MRT/LRT_Station" suffix in Fandom URL
    to indicate they serve both MRT and LRT lines.
    
    Known interchange stations:
    - Bukit Panjang (DT1 + BP6) -> Bukit_Panjang_MRT/LRT_Station
    - Sengkang (NE16 + STC) -> Sengkang_MRT/LRT_Station  
    - Punggol (NE17 + PTC) -> Punggol_MRT/LRT_Station
    - Choa Chu Kang (NS4 + BP1) -> Choa_Chu_Kang_MRT/LRT_Station
    """
    # Map of interchange station display names to their Fandom URL names
    INTERCHANGE_URL_NAMES = {
        "Bukit Panjang": "Bukit_Panjang",
        "Sengkang": "Sengkang", 
        "Punggol": "Punggol",
        "Choa Chu Kang": "Choa_Chu_Kang",
    }
    
    # Extract base name (remove "MRT Station", "LRT Station", etc.)
    base_name = station_name.replace(' MRT Station', '').replace(' LRT Station', '').replace(' Station', '')
    
    # Get URL-safe name
    url_name = INTERCHANGE_URL_NAMES.get(base_name, base_name.replace(' ', '_'))
    
    # All interchange stations use "_MRT/LRT_Station" suffix on Fandom
    return f"https://singapore-mrt-lines.fandom.com/wiki/{url_name}_MRT/LRT_Station"
```

**Implementation Notes:**
- Fandom wiki includes both MRT and LRT station pages
- URL format is consistent: underscores for spaces, "MRT_Station" or "LRT_Station" suffix
- **CRITICAL**: Interchange stations (MRT+LRT) use "_MRT/LRT_Station" suffix to indicate both line types
- Some LRT stations may have different naming (e.g., "Senja LRT Station" vs "Senja Station")

### 3. Update Data Source Queries

Ensure Stage 1 queries include LRT stations:

**data.gov.sg:**
- Current query may filter by description containing "MRT"
- Update to include both "MRT" and "LRT" in description filter
- Or remove filter and determine type post-query

**OneMap:**
- Check if OneMap API returns LRT stations
- May need separate query or different parameters

### 4. Update Schema Validation

Ensure schemas support both types:

```python
class Stage1Station(BaseModel):
    """Station information from Stage 1"""
    station_id: str
    official_name: str
    display_name: str
    mrt_codes: List[str]  # Keep name for backward compatibility, includes LRT codes
    lines: List[str]
    station_type: StationType  # Explicit type field
    exits: List[Exit]
    fandom_url: str
    extraction_status: Literal["pending", "completed", "failed"] = "pending"
```

**Implementation Notes:**
- Keep `mrt_codes` field name for backward compatibility even though it includes LRT
- Consider adding `lrt_codes` field if LRT stations have different code patterns
- LRT codes typically follow pattern: BP1, BP2 (Bukit Panjang), SW1, SW2 (Sengkang West), PE1, PE2 (Punggol East), PW1, PW2 (Punggol West)

### 5. Update Tests

Add test cases for LRT stations:

```python
def test_lrt_station_detection():
    """Test that LRT stations are correctly identified"""
    assert determine_station_type("BUKIT PANJANG LRT STATION") == StationType.LRT
    assert determine_station_type("SENGKANG LRT STATION") == StationType.LRT
    assert determine_station_type("YISHUN MRT STATION") == StationType.MRT

def test_lrt_fandom_url_generation():
    """Test URL generation for LRT stations"""
    station = Stage1Station(
        station_id="BP2",
        official_name="SOUTH VIEW LRT STATION",
        display_name="South View",
        mrt_codes=["BP2"],
        lines=["BPLRT"],
        station_type=StationType.LRT,
        # ... other fields
    )
    assert "South_View_LRT_Station" in station.fandom_url


def test_interchange_station_url_generation():
    """Test URL generation for interchange stations (MRT + LRT)"""
    # Bukit Panjang interchange: MRT (DT1) + LRT (BP6)
    bukit_panjang = Stage1Station(
        station_id="DT1",
        official_name="BUKIT PANJANG MRT/LRT STATION",
        display_name="Bukit Panjang",
        mrt_codes=["DT1", "BP6"],  # Both MRT and LRT codes
        lines=["DTL", "BPLRT"],
        station_type=StationType.MRT,  # Primary type
        # ... other fields
    )
    # Should use _MRT/LRT_Station suffix to indicate interchange
    assert "Bukit_Panjang_MRT/LRT_Station" in bukit_panjang.fandom_url
    
    # Sengkang interchange: MRT (NE16) + LRT (STC)
    sengkang = Stage1Station(
        station_id="NE16",
        official_name="SENGKANG MRT/LRT STATION",
        display_name="Sengkang",
        mrt_codes=["NE16", "STC"],
        lines=["NEL", "SKLRT"],
        station_type=StationType.MRT,
    )
    assert "Sengkang_MRT/LRT_Station" in sengkang.fandom_url
    
    # Punggol interchange: MRT (NE17) + LRT (PTC)
    punggol = Stage1Station(
        station_id="NE17",
        official_name="PUNGGOL MRT/LRT STATION",
        display_name="Punggol",
        mrt_codes=["NE17", "PTC"],
        lines=["NEL", "PGLRT"],
        station_type=StationType.MRT,
    )
    assert "Punggol_MRT/LRT_Station" in punggol.fandom_url
    
    # Choa Chu Kang interchange: MRT (NS4) + LRT (BP1)
    choa_chu_kang = Stage1Station(
        station_id="NS4",
        official_name="CHOA CHU KANG MRT/LRT STATION",
        display_name="Choa Chu Kang",
        mrt_codes=["NS4", "BP1"],
        lines=["NSL", "BPLRT"],
        station_type=StationType.MRT,
    )
    assert "Choa_Chu_Kang_MRT/LRT_Station" in choa_chu_kang.fandom_url
```

---

## Success Criteria

### Functional Requirements
- [ ] LRT stations are processed through Stage 1 alongside MRT stations
- [ ] StationType is correctly determined for both MRT and LRT stations
- [ ] Fandom URLs are correctly generated for LRT stations
- [ ] LRT station data appears in Stage 1 output JSON
- [ ] Stage 2 can extract enrichment data from LRT Fandom pages
- [ ] Stage 3 merger handles both MRT and LRT data correctly

### Test Requirements
- [ ] Unit tests pass for station type detection
- [ ] Unit tests pass for LRT URL generation
- [ ] Integration test with at least 3 LRT stations (one from each line: BPLRT, SKLRT, PGLRT)
- [ ] Full pipeline run includes both MRT and LRT stations

### Data Quality Requirements
- [ ] All Singapore LRT stations are present in final output:
  - Bukit Panjang LRT (13 stations: BP2-BP7, BP9-BP14 - BP1 and BP6 are interchange points)
  - Sengkang LRT (14 stations: SW1-SW8, SE1-SE6)
  - Punggol LRT (15 stations: PW1-PW7, PE1-PE8)
- [ ] Station type field is populated for 100% of stations
- [ ] LRT station codes follow expected patterns (BP, SW, SE, PW, PE prefixes)
- [ ] Interchange stations have correct Fandom URLs with "_MRT/LRT_Station" suffix:
  - Bukit Panjang (DT1 + BP6) → Bukit_Panjang_MRT/LRT_Station
  - Sengkang (NE16 + STC) → Sengkang_MRT/LRT_Station
  - Punggol (NE17 + PTC) → Punggol_MRT/LRT_Station
  - Choa Chu Kang (NS4 + BP1) → Choa_Chu_Kang_MRT/LRT_Station

### Backward Compatibility
- [ ] Existing MRT-only pipelines continue to work
- [ ] Output schema changes don't break downstream consumers
- [ ] Configuration option exists to filter by station type if needed

---

## Files to Modify

1. `src/pipelines/stage1_ingestion.py` - Add station type detection and interchange URL logic
2. `src/processors/matching_engine.py` - Fix station code extraction regex to exclude exit codes (A1, B2, etc.), read from config
3. `config/pipeline.yaml` - Add `station_code_prefixes` config parameter
4. `src/contracts/schemas.py` - Ensure StationType is properly used
5. `tests/test_stage1.py` - Add LRT test cases
6. `src/pipelines/fandom_scraper.py` - Verify LRT URL handling

---

## Known Issues

1. Some LRT stations may not have Fandom wiki pages (check coverage)
2. LRT line codes (BPLRT, SKLRT, PGLRT) may need special handling
3. **Interchange stations have special Fandom URLs**: Stations that serve both MRT and LRT lines use "_MRT/LRT_Station" suffix
   - Bukit Panjang (DT1 + BP6) → Bukit_Panjang_MRT/LRT_Station
   - Sengkang (NE16 + STC) → Sengkang_MRT/LRT_Station
   - Punggol (NE17 + PTC) → Punggol_MRT/LRT_Station
   - Choa Chu Kang (NS4 + BP1) → Choa_Chu_Kang_MRT/LRT_Station
4. **Bukit Panjang LRT Station page does NOT exist** - Bukit Panjang is an interchange station and only has the MRT/LRT combined page
5. Station naming may vary between sources (e.g., "Bukit Panjang MRT/LRT Station" vs "Bukit Panjang LRT Station")
6. **Single-letter codes (A1, A2, B1, etc.) are EXIT codes, not station codes** - These must be filtered out during code extraction using the configurable `station_code_prefixes` parameter
7. **Future MRT lines are included in config** - CR, JS, JW, JE codes are already in the config for when those lines open (2030-2032)

---

## Verification Steps

```bash
# Run Stage 1 and check for LRT stations
python scripts/run_stage1.py
cat outputs/latest/stage1_deterministic.json | jq '.stations[] | select(.station_type == "lrt") | .station_id'

# Expected output should include: BP1, BP2, ..., SW1, SW2, ..., PE1, PE2, ...

# Verify LRT station count
# Bukit Panjang: 13 unique LRT stations (BP2-BP7, BP9-BP14; BP1/BP6 are interchange)
# Sengkang: 14 stations (SW1-SW8, SE1-SE6)
# Punggol: 15 stations (PW1-PW7, PE1-PE8)
# Total: 42 LRT-only stations + 4 interchange stations
```
