# MRT Data Project

Singapore MRT/LRT station enrichment data extraction and management.

## Quick Start

```bash
# Fetch latest data
python main.py

# Validate batch files
cd tmp/extraction_scripts
python3 validate_batches.py
```

## Project Status

- **Total Stations**: 187 (MRT + LRT)
- **Stations Extracted**: 131 (70.1%)
- **Completed Batches**: 15

See `tmp/extraction_scripts/PROGRESS_REPORT.md` for detailed progress.

## Directory Structure

```
mrt-data/
├── main.py                      # Main entry point - fetches deterministic data
├── enrichment_scraper.py         # Extraction scraper
├── ENRICHMENT_README.md         # User-facing documentation
├── README.md                    # This file
│
├── output/                      # Output files
│   ├── mrt_enrichment_data.json # Merged enrichment data
│   └── mrt_transit_graph.json   # Main output (187 stations)
│
├── tmp/                        # Temporary/agent workspace
│   └── extraction_scripts/
│       ├── batch*_enrichment_data.json    # 15 batch files (131 stations)
│       ├── PROGRESS_REPORT.md             # Live progress tracker
│       ├── EXTRACTION_MANIFEST.json       # Batch registry
│       ├── SCHEMA_VERSION.md             # Data format specification
│       ├── MERGE_INSTRUCTIONS.md        # Merge instructions
│       ├── validate_batches.py           # Validation script
│       ├── failed_stations.json         # Failed extraction log (19 stations)
│       ├── STATION_MASTER_INDEX.json    # Station lookup
│       ├── AGENTS.md                  # Agent guide
│       ├── DATA_QUALITY_REPORT.md      # Quality report
│       └── BATCH_15_EXTRACTION_PLAN.md # Extraction plan
│
├── fetchers/                    # Data source fetchers
├── processors/                  # Data processors
├── storage/                     # Data storage utilities
└── utils/                      # Utility functions
```

## Documentation

- **ENRICHMENT_README.md** - User-facing documentation
- **tmp/extraction_scripts/AGENTS.md** - Agent context guide
- **tmp/extraction_scripts/SCHEMA_VERSION.md** - Data format specification
- **tmp/extraction_scripts/MERGE_INSTRUCTIONS.md** - Merge instructions

## Data Sources

### Deterministic Data (main.py)
- data.gov.sg - Station metadata
- OneMap - Exit coordinates and locations

### Enrichment Data (batch extraction)
- singapore-mrt-lines.fandom.com - Platform directions, accessibility, bus stops

## Next Steps

Batch 16 - TEL Remaining (8 stations):
- TE2 (Woodlands)
- TE3 (Woodlands South)
- TE10 (Mount Pleasant)
- TE15 (Great World)
- TE16 (Havelock)
- TE20 (Marina Bay)
- TE21 (Marina South)
- TE30 (Bedok South)

See `tmp/extraction_scripts/PROGRESS_REPORT.md` for details.
