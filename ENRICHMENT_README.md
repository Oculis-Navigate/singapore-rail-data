# MRT Station Enrichment Data

This directory contains additional station information extracted from Singapore MRT Fandom pages.

## Files

- **output/mrt_enrichment_data.json** - Merged enrichment data for all stations
- **output/mrt_transit_graph.json** - Main output file (deterministic data + merged enrichment)

## How It Works

### Data Flow

1. **Deterministic Data Sources** (data.gov.sg, OneMap)
   - Station names and locations
   - Exit locations (lat/lng)
   - MRT codes
   - Updated automatically when you run `main.py`

2. **Enrichment Data** (LLM-extracted)
   - Platform directions per exit
   - Accessibility features per exit
   - Bus stops near each exit
   - Nearby landmarks
   - Extracted via batch scripts in `tmp/extraction_scripts/`

3. **Merge Process**
   - `main.py` fetches deterministic data
   - Batch enrichment data from `tmp/extraction_scripts/batch*_enrichment_data.json`
   - Final output combines both

## Current Status

- **Total Stations**: 187
- **Stations Extracted**: 131 (70.1%)
- **Completed Batches**: 15
- **See** `tmp/extraction_scripts/PROGRESS_REPORT.md` for detailed progress

## Directory Structure

```
mrt-data/
├── main.py                      # Main entry point
├── enrichment_scraper.py         # Extraction scraper
├── ENRICHMENT_README.md         # This file
├── output/
│   ├── mrt_enrichment_data.json # Merged enrichment data
│   └── mrt_transit_graph.json   # Main output
├── tmp/
│   └── extraction_scripts/
│       ├── batch*_enrichment_data.json  # Batch files (15 batches)
│       ├── PROGRESS_REPORT.md           # Progress tracker
│       ├── EXTRACTION_MANIFEST.json     # Batch registry
│       ├── SCHEMA_VERSION.md           # Data format spec
│       ├── MERGE_INSTRUCTIONS.md        # Merge guide
│       ├── validate_batches.py          # Validation script
│       ├── failed_stations.json        # Failed extractions
│       └── AGENTS.md                # Agent guide
├── fetchers/                    # Data fetchers
├── processors/                  # Data processors
├── storage/                    # Data storage
└── utils/                      # Utilities
```

## Running

### Fetch Latest Data
```bash
python main.py
```

### Extract New Batch
See `tmp/extraction_scripts/AGENTS.md` for batch extraction instructions.

### Validate Batches
```bash
cd tmp/extraction_scripts
python3 validate_batches.py
```

## Data Schema

### Station Enrichment

| Field | Type | Description |
|-------|------|-------------|
| `official_name` | string | Full station name |
| `station_code` | string | Primary station code (e.g., "CC10") |
| `lines` | array | Lines served (e.g., ["CCL", "DTL"]) |
| `exits` | array | List of ExitEnrichment objects |
| `accessibility_notes` | array | Station-level accessibility info |
| `last_updated` | string | ISO timestamp |
| `source_url` | string | Fandom page URL |
| `extraction_confidence` | string | "high", "medium", or "low" |

### Exit Enrichment

| Field | Type | Description |
|-------|------|-------------|
| `exit_code` | string | Exit identifier (e.g., "A", "1") |
| `platforms` | array | Platform directions |
| `accessibility` | array | Features (see below) |
| `bus_stops` | array | Nearby bus stops |
| `nearby_landmarks` | array | Notable nearby locations |

### Accessibility Values

- `wheelchair_accessible` - Full wheelchair access
- `barrier_free` - No barriers for disabled
- `lift` - Has elevator/lift
- `escalator` - Has escalator
- `stairs_only` - Only stairs (no lift/escalator)
- `tactile_guidance` - Tactile paving for visually impaired
- `accessible_toilet` - Accessible toilet nearby

## Agent Context

All agent-related files are in `tmp/extraction_scripts/`:
- `AGENTS.md` - Agent guide and context
- `PROGRESS_REPORT.md` - Live progress tracker
- `EXTRACTION_MANIFEST.json` - Batch registry
- `SCHEMA_VERSION.md` - Data format specification
- `MERGE_INSTRUCTIONS.md` - Merge instructions
- `validate_batches.py` - Validation script
- `failed_stations.json` - Failed extraction log
