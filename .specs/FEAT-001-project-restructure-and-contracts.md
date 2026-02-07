# Feature: Project Restructure & Data Contracts

## Feature ID: FEAT-001
**Priority:** P0 (Foundation - must be implemented first)
**Estimated Effort:** 1-2 hours
**Dependencies:** None

---

## Context

### Current State
The project currently has a flat structure with scripts scattered at root level:
- `main.py` - handles deterministic data fetching
- `enrichment_scraper.py` - standalone enrichment extraction
- `processors/`, `fetchers/`, `utils/`, `storage/` - existing modules
- `tmp/extraction_scripts/` - temporary batch files from initial extraction
- `output/` - final JSON outputs

### Problem
1. No clear separation between pipeline stages
2. No formal data contracts between components
3. Mix of temporary and permanent code
4. No configuration management
5. Difficult for new developers to understand data flow

### Goal
Establish a clean, modular architecture with explicit data contracts that separate concerns and enable reliable quarterly pipeline runs.

---

## Requirements

### 1. Directory Structure
Create the following directory structure under `/Users/ryanyeo/Projects/mrt-data/`:

```
mrt-data/
├── src/
│   ├── pipelines/              # Pipeline stage implementations
│   │   ├── __init__.py
│   │   ├── stage1_ingestion.py
│   │   ├── stage2_enrichment.py
│   │   └── stage3_merger.py
│   ├── contracts/              # Data schemas and interfaces
│   │   ├── __init__.py
│   │   ├── schemas.py          # Pydantic models
│   │   └── interfaces.py       # Type definitions
│   ├── fetchers/               # Move existing fetchers here
│   ├── processors/             # Move existing processors here
│   └── utils/                  # Move existing utils here
├── scripts/
│   ├── run_pipeline.py         # CLI entry point
│   ├── validate_output.py      # Post-run validation
│   └── quarterly_run.sh        # Cron wrapper
├── config/
│   ├── __init__.py
│   └── pipeline.yaml           # Pipeline configuration
├── outputs/                    # Versioned outputs (keep existing)
├── logs/                       # Structured logs per run
└── tests/                      # Test suite
    ├── __init__.py
    ├── test_schemas.py
    ├── test_stages.py
    └── fixtures/
```

**Implementation Notes:**
- Move existing `fetchers/`, `processors/`, `utils/`, `storage/` into `src/`
- Update all import statements to use new paths (e.g., `from src.fetchers...`)
- Keep `tmp/extraction_scripts/` as archive (don't delete historical batch files)
- Keep `output/` for backward compatibility during migration

### 2. Data Contracts (schemas.py)

Implement Pydantic models for all data structures:

**Stage 1 Output Schema:**
```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum

class StationType(str, Enum):
    MRT = "mrt"
    LRT = "lrt"

class Exit(BaseModel):
    exit_code: str = Field(..., description="Exit identifier (A, B, 1, 2, etc.)")
    lat: float = Field(..., ge=1.0, le=2.0, description="Latitude in Singapore")
    lng: float = Field(..., ge=103.0, le=105.0, description="Longitude in Singapore")
    source: Literal["onemap", "datagov"] = Field(..., description="Data source")

class Stage1Station(BaseModel):
    station_id: str = Field(..., pattern=r"^[A-Z]{1,3}\d+$", description="Primary station code (NS13)")
    official_name: str = Field(..., pattern=r".*MRT STATION$|.*LRT STATION$", description="Full station name in CAPS")
    display_name: str = Field(..., description="Human-readable name (Yishun)")
    mrt_codes: List[str] = Field(..., min_length=1, description="All station codes for this station")
    lines: List[str] = Field(..., min_length=1, description="Line codes (NSL, EWL, etc.)")
    station_type: StationType
    exits: List[Exit] = Field(..., min_length=1)
    fandom_url: str = Field(..., description="Pre-computed Fandom wiki URL")
    extraction_status: Literal["pending", "completed", "failed"] = "pending"

class Stage1Output(BaseModel):
    metadata: dict = Field(..., description="Run metadata")
    stations: List[Stage1Station] = Field(..., min_length=1)
```

**Stage 2 Output Schema:**
```python
class Platform(BaseModel):
    platform_code: str
    towards_code: str = Field(..., pattern=r"^[A-Z]{1,3}\d+$")
    line_code: str = Field(..., pattern=r"^[A-Z]{2,3}$")

class BusStop(BaseModel):
    code: str = Field(..., pattern=r"^\d{5}$", description="5-digit bus stop code")
    services: List[str] = Field(default_factory=list)

class EnrichedExit(BaseModel):
    exit_code: str
    platforms: Optional[List[Platform]] = None
    accessibility: Optional[List[str]] = None
    bus_stops: Optional[List[BusStop]] = None
    nearby_landmarks: Optional[List[str]] = None

class Stage2Station(BaseModel):
    station_id: str
    official_name: str
    extraction_result: Literal["success", "failed"]
    extraction_confidence: Optional[Literal["high", "medium", "low"]] = None
    exits: List[EnrichedExit]
    accessibility_notes: List[str] = Field(default_factory=list)
    extraction_timestamp: datetime
    source_url: str
    error_message: Optional[str] = None

class Stage2Output(BaseModel):
    metadata: dict
    stations: dict[str, Stage2Station]  # Keyed by station_id
    failed_stations: List[dict]
    retry_queue: List[str]
```

**Final Output Schema:**
```python
class FinalExit(BaseModel):
    exit_code: str
    lat: float
    lng: float
    platforms: Optional[List[Platform]] = None
    accessibility: Optional[List[str]] = None
    bus_stops: Optional[List[BusStop]] = None
    nearby_landmarks: Optional[List[str]] = None

class FinalStation(BaseModel):
    official_name: str
    mrt_codes: List[str]
    exits: List[FinalExit]
    lines_served: Optional[List[str]] = None
    accessibility_notes: Optional[List[str]] = None
    enrichment_last_updated: Optional[datetime] = None
    data_quality: Optional[dict] = None

class FinalOutput(BaseModel):
    metadata: dict
    stations: List[FinalStation]
```

### 3. Configuration (config/pipeline.yaml)

Create a YAML configuration file:

```yaml
pipeline:
  name: "MRT Data Pipeline"
  version: "2.0.0"
  
  # Stage configurations
  stages:
    stage1_ingestion:
      enabled: true
      sources:
        - datagov
        - onemap
      cache_ttl_days: 30
      
    stage2_enrichment:
      enabled: true
      batch_size: 8
      delay_seconds: 2
      max_retries: 3
      retry_delay_seconds: 5
      sources:
        - fandom_wiki
        - openrouter_llm
        
    stage3_merger:
      enabled: true
      validation:
        schema_check: true
        completeness_check: true
        sanity_check: true
        
  # API configurations
  apis:
    onemap:
      base_url: "https://www.onemap.gov.sg/api"
      timeout: 30
      
    openrouter:
      base_url: "https://openrouter.ai/api/v1"
      model: "anthropic/claude-3.5-sonnet"
      timeout: 120
      max_tokens: 4000
      temperature: 0.1
      
    fandom:
      base_url: "https://singapore-mrt-lines.fandom.com/wiki"
      timeout: 30
      
  # Expected station count (for validation)
  expected_stations: 187
  
  # Output configuration
  output:
    versioning: true
    keep_last_n_versions: 10
    symlink_latest: true
    
  # Logging
  logging:
    level: INFO
    format: structured  # structured or simple
```

### 4. Interfaces (contracts/interfaces.py)

Define abstract base classes:

```python
from abc import ABC, abstractmethod
from typing import Any

class PipelineStage(ABC):
    """Abstract base class for all pipeline stages"""
    
    @property
    @abstractmethod
    def stage_name(self) -> str:
        """Return the stage name"""
        pass
    
    @abstractmethod
    def execute(self, input_data: Any) -> Any:
        """Execute the stage and return output"""
        pass
    
    @abstractmethod
    def validate_input(self, input_data: Any) -> bool:
        """Validate input data before processing"""
        pass
    
    @abstractmethod
    def validate_output(self, output_data: Any) -> bool:
        """Validate output data after processing"""
        pass
```

---

## Success Criteria

1. [ ] Directory structure created as specified
2. [ ] All Pydantic models implemented in `contracts/schemas.py`
3. [ ] Configuration file created at `config/pipeline.yaml`
4. [ ] Abstract interfaces defined in `contracts/interfaces.py`
5. [ ] Existing code moved to `src/` with updated imports
6. [ ] `python -c "from src.contracts.schemas import *"` executes without error
7. [ ] Configuration can be loaded: `python -c "import yaml; yaml.safe_load(open('config/pipeline.yaml'))"`

---

## Implementation Notes

### Import Path Updates
When moving files, update imports:
- `from fetchers.datagov_fetcher import ...` → `from src.fetchers.datagov_fetcher import ...`
- `from utils.logger import logger` → `from src.utils.logger import logger`
- Add `sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))` if needed

### Pydantic Installation
Ensure pydantic is available:
```bash
pip install pydantic pyyaml
# or update pyproject.toml
```

### Backward Compatibility
During migration, keep old imports working by creating temporary shim files at root level that import from new locations.

---

## Files to Create

1. `src/pipelines/__init__.py`
2. `src/contracts/__init__.py`
3. `src/contracts/schemas.py` (comprehensive Pydantic models)
4. `src/contracts/interfaces.py` (abstract base classes)
5. `config/__init__.py`
6. `config/pipeline.yaml` (configuration)
7. `scripts/__init__.py`
8. `tests/__init__.py`
9. Update existing files in `src/fetchers/`, `src/processors/`, `src/utils/`, `src/storage/`

---

## Dependencies for Next Features

This feature is a dependency for:
- FEAT-002: Stage 1 - Deterministic Data Ingestion
- FEAT-003: Stage 2 - Enrichment Extraction Pipeline
- FEAT-004: Stage 3 - Data Merging & Validation
- FEAT-005: Pipeline Orchestrator & Configuration
- FEAT-006: Alerting, Testing & Automation

**DO NOT proceed with other features until this foundation is complete.**
