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

### 2. Update Fandom URL Generation

Modify URL generation to handle MRT, LRT, and interchange stations:

```python
def generate_fandom_url(station_name: str, station_type: StationType, 
                        mrt_codes: List[str]) -> str:
    """
    Generate Fandom wiki URL for a station.
    
    Examples:
    - "Yishun MRT Station" -> "https://singapore-mrt-lines.fandom.com/wiki/Yishun_MRT_Station"
    - "Bukit Panjang LRT Station" -> "https://singapore-mrt-lines.fandom.com/wiki/Bukit_Panjang_LRT_Station"
    - "Bukit Panjang MRT/LRT Station" (interchange) -> "https://singapore-mrt-lines.fandom.com/wiki/Bukit_Panjang_LRT_Station"
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
    - Bukit Panjang (DT1 + BP1) -> Bukit_Panjang_MRT/LRT_Station
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
        station_id="BP1",
        official_name="BUKIT PANJANG LRT STATION",
        display_name="Bukit Panjang",
        mrt_codes=["BP1"],
        lines=["BPLRT"],
        station_type=StationType.LRT,
        # ... other fields
    )
    assert "Bukit_Panjang_LRT_Station" in station.fandom_url


def test_interchange_station_url_generation():
    """Test URL generation for interchange stations (MRT + LRT)"""
    # Bukit Panjang interchange: MRT (DT1) + LRT (BP1)
    bukit_panjang = Stage1Station(
        station_id="DT1",
        official_name="BUKIT PANJANG MRT/LRT STATION",
        display_name="Bukit Panjang",
        mrt_codes=["DT1", "BP1"],  # Both MRT and LRT codes
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
  - Bukit Panjang LRT (14 stations: BP1-BP14)
  - Sengkang LRT (14 stations: SW1-SW8, SE1-SE6)
  - Punggol LRT (15 stations: PW1-PW7, PE1-PE8)
- [ ] Station type field is populated for 100% of stations
- [ ] LRT station codes follow expected patterns (BP, SW, SE, PW, PE prefixes)
- [ ] Interchange stations have correct Fandom URLs with "_MRT/LRT_Station" suffix:
  - Bukit Panjang → Bukit_Panjang_MRT/LRT_Station
  - Sengkang → Sengkang_MRT/LRT_Station
  - Punggol → Punggol_MRT/LRT_Station
  - Choa Chu Kang → Choa_Chu_Kang_MRT/LRT_Station

### Backward Compatibility
- [ ] Existing MRT-only pipelines continue to work
- [ ] Output schema changes don't break downstream consumers
- [ ] Configuration option exists to filter by station type if needed

---

## Files to Modify

1. `src/pipelines/stage1_ingestion.py` - Add station type detection
2. `src/contracts/schemas.py` - Ensure StationType is properly used
3. `tests/test_stage1.py` - Add LRT test cases
4. `config/pipeline.yaml` - Add optional station type filter
5. `src/pipelines/fandom_scraper.py` - Verify LRT URL handling

---

## Known Issues

1. Some LRT stations may not have Fandom wiki pages (check coverage)
2. LRT line codes (BPLRT, SKLRT, PGLRT) may need special handling
3. **Interchange stations have special Fandom URLs**: Stations that serve both MRT and LRT lines use "_MRT/LRT_Station" suffix
   - Bukit Panjang (DT1 + BP1) → Bukit_Panjang_MRT/LRT_Station
   - Sengkang (NE16 + STC) → Sengkang_MRT/LRT_Station
   - Punggol (NE17 + PTC) → Punggol_MRT/LRT_Station
   - Choa Chu Kang (NS4 + BP1) → Choa_Chu_Kang_MRT/LRT_Station
4. Station naming may vary between sources (e.g., "Bukit Panjang MRT/LRT Station" vs "Bukit Panjang LRT Station")

---

## Verification Steps

```bash
# Run Stage 1 and check for LRT stations
python scripts/run_stage1.py
cat outputs/latest/stage1_deterministic.json | jq '.stations[] | select(.station_type == "lrt") | .station_id'

# Expected output should include: BP1, BP2, ..., SW1, SW2, ..., PE1, PE2, ...

# Verify LRT station count
# Bukit Panjang: 14 stations
# Sengkang: 14 stations  
# Punggol: 15 stations
# Total: 43 LRT stations (plus any interchange stations counted once)
```
