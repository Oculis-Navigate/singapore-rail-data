# Agent Context - MRT Station Enrichment Project

## Your Role
You are extracting detailed station information from Singapore MRT Fandom wiki to build a comprehensive transit dataset. This data will be merged with existing deterministic data (station locations, coordinates) to create a complete transit graph.

## Critical Project Facts

### Scope
- **Total Stations**: 187 (MRT + LRT)
- **Current Status**: 24 stations extracted (12.8% complete)
- **Completed Batches**: 3 batches (NSL North, NSL South, EWL East)
- **Data Source**: singapore-mrt-lines.fandom.com/wiki/{Station_Name}_MRT_Station

### Two-Tier Architecture
1. **Deterministic Data** (`output/mrt_transit_graph.json`): Station locations, exits, coordinates from APIs (auto-generated)
2. **Enrichment Data** (`batch*_enrichment_data.json`): Exit details, platforms, accessibility, bus stops from Fandom wiki (your job)

## Three Key Extraction Targets

### 1. Exit-Platform Mappings
**What**: Which exit leads to which platform and direction
**Format**:
```json
"platforms": [
  {
    "platform_code": "A",
    "towards_code": "NS1",  // USE STATION CODE, NOT NAME
    "line_code": "NS"       // NS, EW, CC, DT, NE, TE, BP
  }
]
```
**Critical**: Always use station CODES (NS1, CC29) not names (Jurong East, Harbourfront)

### 2. Exit-Bus Stop Mappings
**What**: Which bus stops are located at each exit with service numbers
**Format**:
```json
"bus_stops": [
  {
    "code": "59009",  // Must be exactly 5 digits
    "services": ["39", "85", "103"]
  }
]
```
**Critical**: Bus stop codes must be 5-digit numeric strings

### 3. Accessibility Information
**What**: Whether each exit is barrier-free or has limitations
**Format**:
```json
"accessibility": ["lift", "escalator", "wheelchair_accessible"]
// OR
"accessibility": ["stairs_only"]  // Mark non-accessible exits clearly
```
**Allowed Values**:
- `wheelchair_accessible` - General wheelchair access
- `barrier_free` - No barriers/steps
- `lift` - Has elevator/lift
- `escalator` - Has escalator
- `stairs_only` - Stairs only (NOT accessible) - **Important for disabled users**
- `tactile_guidance` - Tactile paving for visually impaired
- `accessible_toilet` - Accessible toilet nearby

**Critical**: Always mark stairs-only exits clearly. Check Fandom page carefully for accessibility notes.

## Schema Requirements (MUST FOLLOW)

### Station Object Structure
```json
{
  "official_name": "STATION NAME MRT STATION",  // ALL CAPS
  "station_code": "NS13",                        // Primary code
  "lines": ["NSL"],                              // Line abbreviations
  "exits": [
    {
      "exit_code": "A",                          // A, B, 1, 2, etc.
      "platforms": [...],                        // Array of platform objects
      "accessibility": [...],                    // Array of strings
      "bus_stops": [...],                        // Array of bus stop objects
      "nearby_landmarks": ["Landmark Name"]      // Array of strings
    }
  ],
  "accessibility_notes": ["Important note about station"],
  "last_updated": "2026-02-02T10:00:00",        // ISO8601 timestamp
  "source_url": "https://singapore-mrt-lines.fandom.com/wiki/...",
  "extraction_confidence": "high"                // high, medium, or low
}
```

### Required Fields (100% mandatory)
- `official_name` - ALL CAPS with "MRT STATION" suffix
- `station_code` - Primary identifier (NS13, not "Yishun")
- `lines` - Array of line codes (NSL, EWL, CCL, DTL, NEL, TEL)
- `exits` - Array of exit objects (every exit must be listed)
- `accessibility_notes` - Array (can be empty `[]`)
- `last_updated` - ISO8601 format
- `source_url` - Fandom wiki URL
- `extraction_confidence` - "high", "medium", or "low"

### Line Code Abbreviations
- **NSL** - North-South Line
- **EWL** - East-West Line
- **CCL** - Circle Line
- **DTL** - Downtown Line
- **NEL** - North-East Line
- **TEL** - Thomson-East Coast Line
- **BPL** - Bukit Panjang LRT
- **SKL** - Sengkang LRT
- **PGL** - Punggol LRT

## Workflow (ALWAYS FOLLOW)

### Before Starting
1. **Read PROGRESS_REPORT.md** - Check current status
2. **Read EXTRACTION_MANIFEST.json** - See which batches are complete
3. **Run validation**: `python3 validate_batches.py`
4. **Confirm batch plan with user** - Don't start extraction without user approval

### During Extraction
1. **Extract from Fandom wiki** using webfetch tool
2. **Process each station** systematically
3. **Use station codes** (NS13) not names (Yishun) in ALL fields
4. **Include nearby_landmarks** for every exit (check surrounding area)
5. **Mark accessibility clearly** - especially stairs-only exits
6. **Use 5-digit bus stop codes** with service numbers

### After Each Batch
1. **Validate the batch**: `python3 validate_batches.py`
2. **Update PROGRESS_REPORT.md** - Add batch summary table
3. **Update EXTRACTION_MANIFEST.json** - Add batch to completed list
4. **Update STATION_MASTER_INDEX.json** - Add extracted stations
5. **Create summary** for user review before proceeding

## Questions to Ask User Before Each Batch

1. **"Which stations should I include in this batch?"** - Confirm the list
2. **"Any stations to skip?"** - Some may have issues
3. **"Should I proceed with extraction?"** - Get explicit go-ahead
4. **"Do you want to review the batch before I save it?"** - Optional review step

## Common Pitfalls (AVOID THESE)

### ❌ Using Station Names Instead of Codes
**Wrong**: `"towards_code": "Jurong East"`
**Right**: `"towards_code": "NS1"`

### ❌ Missing Nearby Landmarks
Every exit MUST have `nearby_landmarks` array (can be empty but must exist)

### ❌ Forgetting Accessibility Notes
If exit is stairs-only, it MUST be in `accessibility` array AND noted in `accessibility_notes`

### ❌ Wrong Bus Stop Format
Bus stop codes must be 5-digit strings: `"59009"` not `59009` (number) or `"5909"` (4 digits)

### ❌ Inconsistent Exit Codes
Use exit codes exactly as they appear (A, B, 1, 2). Don't normalize letters to numbers.

### ❌ Skipping Validation
ALWAYS run `python3 validate_batches.py` before and after extraction

## Batch Size Guidelines

- **Optimal**: 8-12 stations per batch
- **Maximum**: 15 stations (for reviewability)
- **Minimum**: 5 stations (for meaningful progress)

**Why**: Smaller batches are easier to review and fix if errors are found.

## Fandom Wiki Extraction Tips

### URL Format
`https://singapore-mrt-lines.fandom.com/wiki/{Station_Name}_MRT_Station`

Examples:
- Yishun: `https://singapore-mrt-lines.fandom.com/wiki/Yishun_MRT_Station`
- Tampines: `https://singapore-mrt-lines.fandom.com/wiki/Tampines_MRT_Station`

### Key Sections to Extract
1. **Exit Information** - Look for "Exits" section
2. **Station Layout** - Platform directions
3. **Bus Services** - Bus stops and service numbers
4. **Accessibility** - Lifts, escalators, stairs-only warnings
5. **Nearby Landmarks** - Buildings, malls, facilities near each exit

### Red Flags to Note
- "Exit X does not provide barrier-free accessibility"
- "Exit Y is for emergency use only"
- "Exit Z has limited hours"
- "Station has both NSL and DTL but they are not connected by paid link"

## File Locations

| File | Path | Purpose |
|------|------|---------|
| Batch files | `tmp/extraction_scripts/batch*_enrichment_data.json` | Your output |
| Progress report | `tmp/extraction_scripts/PROGRESS_REPORT.md` | Update after each batch |
| Manifest | `EXTRACTION_MANIFEST.json` | Batch registry |
| Station index | `STATION_MASTER_INDEX.json` | Station lookup |
| Schema | `SCHEMA_VERSION.md` | Data format rules |
| Validation | `validate_batches.py` | Run this before/after |

## Emergency Contacts (If Stuck)

If you encounter issues:
1. Check `SCHEMA_VERSION.md` for field definitions
2. Look at existing batch files for examples
3. Ask the user for clarification
4. Document issues in `failed_stations.json`

## Success Criteria

A batch is complete when:
- ✅ All stations have valid JSON structure
- ✅ All required fields present
- ✅ Validation passes: `python3 validate_batches.py`
- ✅ User has reviewed and approved
- ✅ Progress report updated
- ✅ All context files updated

## Reminder

**You are building data that affects real users.** Disabled commuters rely on accurate accessibility information. Bus integration helps with multi-modal journeys. Platform directions prevent people from going the wrong way.

**Be thorough. Be accurate. Be consistent.**
