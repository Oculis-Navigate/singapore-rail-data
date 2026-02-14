# MRT Data Pipeline

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive, automated pipeline for extracting and enriching Singapore MRT/LRT station data. This project combines official government APIs with community wiki data to produce a complete, structured dataset of all Singapore train stations.

## Overview

The pipeline processes data from multiple sources across three stages:

- **Stage 1**: Ingests deterministic station data from official sources (Data.gov.sg, OneMap API)
- **Stage 2**: Enriches data using LLM-powered extraction from the Singapore MRT Lines Fandom wiki
- **Stage 3**: Merges and validates all data, producing clean JSON outputs

## Data Sources

### Official Government Data (Stage 1)

| Source | API Endpoint | Data Provided | Authentication |
|--------|--------------|---------------|----------------|
| **Data.gov.sg** | https://data.gov.sg | Station exit locations and codes | None (open data) |
| **OneMap Singapore** | https://www.onemap.gov.sg | Station coordinates, building names, exit locations | Free API key |

**Coverage**: 187 stations across 9 MRT/LRT lines
- **NSL** - North South Line
- **EWL** - East West Line  
- **CCL** - Circle Line
- **DTL** - Downtown Line
- **NEL** - North East Line
- **TEL** - Thomson-East Coast Line
- **BPL** - Bukit Panjang LRT
- **SKL** - Sengkang LRT
- **PGL** - Punggol LRT

### Community Enrichment (Stage 2)

| Source | URL | Data Extracted | Method |
|--------|-----|----------------|--------|
| **Singapore MRT Lines Wiki** | https://singapore-mrt-lines.fandom.com | Platform info, bus stops, accessibility features, landmarks | LLM extraction via OpenRouter |

**OpenRouter Models Used**:
- `openai/gpt-oss-120b:free` (default) - For parsing structured station information
- Supports any OpenRouter model via config

### Future Lines Support

The pipeline includes infrastructure for upcoming lines:
- **CRL** - Cross Island Line (2027-2032)
- **JRL** - Jurong Region Line (2027-2028)

## Output Data Format

### Final Output Files

```
outputs/
└── YYYY-MM-DD/
    ├── stage3_final.json          # Complete enriched station data
    ├── mrt_transit_graph.json     # Network topology for graph analysis
    └── metadata.json              # Run metadata and checksums
```

### Station Data Schema

```json
{
  "stations": [
    {
      "station_id": "NS13",
      "official_name": "YISHUN MRT STATION",
      "display_name": "Yishun",
      "mrt_codes": ["NS13"],
      "lines": ["NSL"],
      "station_type": "mrt",
      "exits": [
        {
          "exit_code": "A",
          "lat": 1.429453,
          "lng": 103.835041,
          "platforms": [
            {
              "platform_code": "A",
              "towards_code": "NS1",
              "line_code": "NSL"
            }
          ],
          "accessibility": ["lift", "wheelchair_accessible"],
          "bus_stops": [
            {
              "code": "59009",
              "services": ["117", "171", "811"]
            }
          ],
          "nearby_landmarks": ["Northpoint City", "Yishun Bus Interchange"]
        }
      ],
      "fandom_url": "https://singapore-mrt-lines.fandom.com/wiki/Yishun_MRT_Station"
    }
  ]
}
```

## Quick Start

### Prerequisites

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) package manager (recommended)
- API keys for OneMap and OpenRouter

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USER/mrt-data.git
cd mrt-data

# Install dependencies
uv sync

# Set up environment
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Create `.env` file with your API keys:

```bash
# OneMap API (free) - https://www.onemap.gov.sg
ONEMAP_API_KEY=your_onemap_api_key

# OpenRouter API (free tier available) - https://openrouter.ai
OPENROUTER_API_KEY=your_openrouter_api_key
```

### Running the Pipeline

```bash
# Run full pipeline
uv run python scripts/run_pipeline.py

# Run specific stage
uv run python scripts/run_pipeline.py --stage 1  # Ingestion only
uv run python scripts/run_pipeline.py --stage 2  # Enrichment only
uv run python scripts/run_pipeline.py --stage 3  # Merge only

# Resume interrupted Stage 2
uv run python scripts/run_pipeline.py --stage 2 --resume

# Retry failed extractions
uv run python scripts/run_pipeline.py --stage 2 --retry-failed
```

### Validation

```bash
# Validate final output
uv run python scripts/validate_output.py

# Run test suite
uv run bash scripts/run_tests.sh
```

## Project Structure

```
mrt-data/
├── src/
│   ├── contracts/           # Pydantic schemas and interfaces
│   │   ├── schemas.py       # Data models (Stage1Output, Stage2Output, FinalOutput)
│   │   └── interfaces.py    # PipelineStage protocol
│   ├── pipelines/           # Core pipeline stages
│   │   ├── stage1_ingestion.py    # Deterministic data ingestion
│   │   ├── stage2_enrichment.py   # LLM enrichment extraction
│   │   ├── stage3_merger.py       # Data merging and validation
│   │   ├── fandom_scraper.py      # Fandom wiki scraper
│   │   ├── html_extractor.py      # HTML content extractor
│   │   └── openrouter_client.py   # LLM API client
│   ├── fetchers/            # Data source clients
│   │   ├── datagov_fetcher.py     # Data.gov.sg API
│   │   ├── onemap_fetcher.py      # OneMap API
│   │   └── missing_station_fetcher.py  # Fallback station finder
│   ├── processors/          # Data processing
│   │   ├── matching_engine.py     # Station/exit matching
│   │   ├── consolidator.py        # Data consolidation
│   │   ├── enrichment_merger.py   # Enrichment merging
│   │   └── spatial_utils.py       # Coordinate calculations
│   ├── storage/             # Data persistence
│   │   └── json_storage.py        # JSON file storage
│   ├── alerts/              # Alerting system
│   │   └── alert_manager.py       # Failure alerts
│   ├── utils/               # Utilities
│   │   ├── logger.py              # Structured logging
│   │   ├── url_cache.py           # URL caching
│   │   ├── content_quality.py     # Content validation
│   │   └── extraction_metrics.py  # Extraction analytics
│   └── orchestrator.py      # Main pipeline orchestrator
├── scripts/                 # Execution scripts
│   ├── run_pipeline.py      # Main entry point
│   ├── run_stage1.py        # Stage 1 runner
│   ├── run_stage2.py        # Stage 2 runner
│   ├── run_stage3.py        # Stage 3 runner
│   ├── validate_output.py   # Output validation
│   └── quarterly_run.sh     # Cron automation script
├── config/
│   └── pipeline.yaml        # Pipeline configuration
├── tests/                   # Test suite
│   ├── test_schemas.py      # Schema validation tests
│   ├── test_stages.py       # Stage integration tests
│   ├── test_validation.py   # Validation logic tests
│   └── conftest.py          # Pytest configuration
├── outputs/                 # Pipeline outputs (gitignored)
└── README.md
```

## Configuration

Edit `config/pipeline.yaml` to customize:

```yaml
pipeline:
  stages:
    stage1_ingestion:
      cache_ttl_days: 30          # Cache API responses
      
    stage2_enrichment:
      batch_size: 8               # LLM requests per batch
      delay_seconds: 2            # Rate limiting
      daily_timeout_minutes: 90   # Max runtime for free tier
      checkpoint_interval: 1      # Save after N stations
      
    stage3_merger:
      validation:
        schema_check: true
        completeness_check: true
        sanity_check: true
        
  output:
    versioning: true              # Date-based versioning
    symlink_latest: true          # Create 'latest' symlink
    create_github_release: true   # Auto-release on GitHub
```

## Features

### Resumable Processing
- **Checkpoint System**: Stage 2 saves progress after each station
- **Resume Support**: Resume interrupted runs without losing progress
- **Retry Failed**: Re-attempt only failed extractions

### Data Quality
- **Schema Validation**: Pydantic models ensure data integrity
- **Completeness Checks**: Verify all stations and required fields
- **Sanity Checks**: Validate coordinates, exit counts, station codes
- **Confidence Scoring**: LLM extraction includes confidence levels (high/medium/low)

### Rate Limiting & Caching
- **OneMap API**: Built-in delays (~60 req/min limit)
- **OpenRouter**: 2-second delay between requests
- **URL Caching**: Fandom URLs cached for 30 days
- **Smart Retries**: Exponential backoff with max 3 retries

### Alerting & Monitoring
- **Structured Logging**: JSON-formatted logs
- **Alert Channels**: Log, file, email (configurable)
- **Exit Codes**: Pipeline returns proper exit codes for CI/CD

### Automation
- **Quarterly Runs**: Cron script for scheduled execution
- **GitHub Releases**: Automated release creation with versioning
- **CI/CD Ready**: Designed for GitHub Actions integration

## Testing

```bash
# Run all tests
uv run bash scripts/run_tests.sh

# Run specific test file
uv run python -m pytest tests/test_schemas.py -v

# Run with coverage
uv run python -m pytest --cov=src tests/
```

## Automation

### Cron Setup

Schedule quarterly runs (1st of Jan, Apr, Jul, Oct at 2 AM):

```bash
# Edit crontab
crontab -e

# Add line:
0 2 1 1,4,7,10 * /path/to/mrt-data/scripts/quarterly_run.sh
```

### GitHub Actions

Create `.github/workflows/pipeline.yml`:

```yaml
name: Quarterly Data Update
on:
  schedule:
    - cron: '0 2 1 1,4,7,10 *'  # Quarterly
  workflow_dispatch:  # Manual trigger

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run python scripts/run_pipeline.py
        env:
          ONEMAP_API_KEY: ${{ secrets.ONEMAP_API_KEY }}
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
```

## API Reference

### Data.gov.sg
- **Endpoint**: https://data.gov.sg/api/action/datastore_search
- **Dataset**: MRT Station Exit Coordinates
- **Authentication**: None (open data)
- **Format**: GeoJSON

### OneMap
- **Endpoint**: https://www.onemap.gov.sg/api
- **Documentation**: https://www.onemap.gov.sg/apidocs/
- **Authentication**: API key header
- **Rate Limit**: ~1000 req/day, 60 req/min

### OpenRouter
- **Endpoint**: https://openrouter.ai/api/v1
- **Documentation**: https://openrouter.ai/docs
- **Authentication**: Bearer token
- **Rate Limit**: Varies by model

### Fandom Wiki
- **Base URL**: https://singapore-mrt-lines.fandom.com/wiki
- **Format**: HTML pages
- **Rate Limit**: Respectful crawling with delays

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`uv run bash scripts/run_tests.sh`)
5. Commit (`git commit -m 'Add amazing feature'`)
6. Push (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Setup

```bash
# Install dev dependencies
uv sync --all-extras

# Run linting
uv run ruff check src/

# Run type checking
uv run mypy src/
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **Land Transport Authority (LTA)** - For providing open data via Data.gov.sg
- **Singapore Land Authority** - For the OneMap API
- **Singapore MRT Lines Fandom Community** - For maintaining detailed station information
- **OpenRouter** - For providing LLM API access

## Changelog

### v2.0.0 (2024-02-14)
- Complete pipeline rewrite with stage-based architecture
- Added LLM-powered enrichment extraction
- Implemented checkpoint/resume functionality
- Added comprehensive validation and alerting
- Support for both MRT and LRT stations

## Troubleshooting

### Common Issues

**Stage 2 timeouts**: Increase `daily_timeout_minutes` in config or use `--resume`

**Rate limit errors**: Increase `delay_seconds` in config

**Missing stations**: Check logs for API errors; some stations may not be on Fandom yet

**Import errors**: Ensure you're using `uv run` or have activated the virtual environment

### Getting Help

- Check [Issues](https://github.com/YOUR_USER/mrt-data/issues) for known problems
- Review the [Discussions](https://github.com/YOUR_USER/mrt-data/discussions) for Q&A
- Open a new issue with logs and reproduction steps
