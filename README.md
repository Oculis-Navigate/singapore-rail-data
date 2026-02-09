# MRT Data Pipeline

Singapore MRT/LRT station data extraction and enrichment pipeline.

## Quick Start

```bash
# Run full pipeline
uv run python scripts/run_pipeline.py

# Run single stage
uv run python scripts/run_pipeline.py --stage 1
uv run python scripts/run_pipeline.py --stage 2
uv run python/scripts/run_pipeline.py --stage 3

# Validate output
uv run python scripts/validate_output.py
```

## Project Structure

```
mrt-data/
├── .specs/                    # Feature specifications
├── src/                        # Source code
│   ├── contracts/              # Data contracts & schemas
│   ├── pipelines/             # Pipeline stages
│   ├── alerts/                 # Alerting system
│   └── utils/                 # Utilities
├── scripts/                    # Execution scripts
│   ├── run_pipeline.py         # Main entry point
│   ├── run_stage1.py           # Stage 1 only
│   ├── run_stage2.py           # Stage 2 only
│   ├── run_stage3.py           # Stage 3 only
│   ├── validate_output.py       # Output validation
│   ├── run_tests.sh            # Test runner
│   └── quarterly_run.sh         # Cron automation
├── config/                     # Configuration
├── tests/                      # Test suite
└── outputs/                     # Pipeline output
```

## Pipeline Stages

### Stage 1: Deterministic Data Ingestion
- Fetches station data from Data.gov.sg and OneMap API
- Outputs: `stage1_deterministic.json`

### Stage 2: Enrichment Extraction
- Extracts platform, accessibility, bus stop data from Fandom wiki
- Uses LLM for structured extraction
- Outputs: `stage2_enrichment.json`

### Stage 3: Merging & Validation
- Merges deterministic + enrichment data
- Validates schema, completeness, sanity checks
- Outputs: `stage3_final.json`, `mrt_transit_graph.json`

## Configuration

Edit `config/pipeline.yaml` to configure:
- API endpoints and timeouts
- Batch sizes and retry settings
- Alerting channels
- Expected station counts

## Testing

```bash
# Run all tests
uv run bash scripts/run_tests.sh

# Run specific test file
uv run python -m pytest tests/test_schemas.py -v
```

## Automation

Quarterly runs via cron:
```bash
0 2 1 1,4,7,10 * /path/to/mrt-data/scripts/quarterly_run.sh
```
