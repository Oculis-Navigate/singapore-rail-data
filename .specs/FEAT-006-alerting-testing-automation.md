# Feature: Alerting, Testing & Automation

## Feature ID: FEAT-006
**Priority:** P2 (Operational Features)
**Estimated Effort:** 3-4 hours
**Dependencies:** FEAT-001, FEAT-005 (can be started after FEAT-005 is complete)

---

## Context

### Current State
- No alerting mechanism for pipeline failures
- No automated testing for data quality
- No cron/automation setup
- Validation is manual
- No notification system

### Goal
Implement operational features:
1. Alerting system for critical failures (404, no matches, schema errors)
2. Testing framework for data validation
3. Quarterly automation with cron
4. Post-run validation scripts

---

## Requirements

### 1. Alerting System (src/alerts/alert_manager.py)

Create a flexible alerting system:

```python
"""
Alert management system for pipeline failures and issues.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class Alert:
    level: AlertLevel
    message: str
    context: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "message": self.message,
            "context": self.context,
            "timestamp": self.timestamp.isoformat()
        }

class AlertManager:
    """
    Manages alerts for the pipeline.
    
    Supports multiple alert channels:
    - Logging (always enabled)
    - File (alerts.json)
    """
    
    def __init__(self, config: dict):
        self.config = config.get('alerting', {})
        self.enabled = self.config.get('enabled', True)
        self.alert_log: List[Alert] = []
        
        # Initialize channels
        self.channels = []
        
        # Always add log channel
        self.channels.append(LogChannel())
        
        # Add file channel if output dir specified
        if 'output_dir' in config:
            self.channels.append(FileChannel(config['output_dir']))
        
    def alert(self, level: AlertLevel, message: str, context: dict = None):
        """Send an alert through all channels"""
        if not self.enabled:
            return
        
        alert = Alert(
            level=level,
            message=message,
            context=context or {},
            timestamp=datetime.utcnow()
        )
        
        self.alert_log.append(alert)
        
        # Send to all channels
        for channel in self.channels:
            try:
                channel.send(alert)
            except Exception as e:
                logging.error(f"Failed to send alert via {channel.__class__.__name__}: {e}")
    
    def info(self, message: str, context: dict = None):
        self.alert(AlertLevel.INFO, message, context)
    
    def warning(self, message: str, context: dict = None):
        self.alert(AlertLevel.WARNING, message, context)
    
    def error(self, message: str, context: dict = None):
        self.alert(AlertLevel.ERROR, message, context)
    
    def critical(self, message: str, context: dict = None):
        self.alert(AlertLevel.CRITICAL, message, context)
    
    def save_alert_log(self, output_path: str):
        """Save all alerts to file"""
        alerts_data = [a.to_dict() for a in self.alert_log]
        with open(output_path, 'w') as f:
            json.dump(alerts_data, f, indent=2)

# Alert channel implementations

class LogChannel:
    """Sends alerts to Python logging"""
    
    def send(self, alert: Alert):
        logger = logging.getLogger('pipeline.alerts')
        msg = f"[{alert.level.value.upper()}] {alert.message}"
        
        if alert.level == AlertLevel.CRITICAL:
            logger.critical(msg)
        elif alert.level == AlertLevel.ERROR:
            logger.error(msg)
        elif alert.level == AlertLevel.WARNING:
            logger.warning(msg)
        else:
            logger.info(msg)

class FileChannel:
    """Sends alerts to JSON file"""
    
    def __init__(self, output_dir: str):
        self.output_file = os.path.join(output_dir, 'alerts.json')
    
    def send(self, alert: Alert):
        # Append to file
        alerts = []
        if os.path.exists(self.output_file):
            with open(self.output_file, 'r') as f:
                try:
                    alerts = json.load(f)
                except json.JSONDecodeError:
                    alerts = []
        
        alerts.append(alert.to_dict())
        
        with open(self.output_file, 'w') as f:
            json.dump(alerts, f, indent=2)

```

### 2. Pipeline Integration with Alerting

Update orchestrator to use alerting:

```python
# In src/orchestrator.py, add to __init__:
from src.alerts.alert_manager import AlertManager

def __init__(self, config_path: str = "config/pipeline.yaml"):
    self.config = self._load_config(config_path)
    self.alert_manager = AlertManager(self.config)
    # ... rest of init

# In execute methods, add alerts:
def run_stage1(self, ...):
    try:
        # ... existing code
        self.alert_manager.info(f"Stage 1 complete: {len(output.stations)} stations")
        return output
    except Exception as e:
        self.alert_manager.critical(f"Stage 1 failed: {e}")
        raise
```

### 3. Testing Framework (tests/)

Create comprehensive tests:

**tests/test_schemas.py:**
```python
"""Tests for data contract schemas"""

import pytest
from src.contracts.schemas import (
    Stage1Output, Stage1Station, Exit, StationType,
    Stage2Output, Stage2Station, FinalOutput, FinalStation
)

class TestStage1Station:
    def test_valid_station(self):
        station = Stage1Station(
            station_id="NS13",
            official_name="YISHUN MRT STATION",
            display_name="Yishun",
            mrt_codes=["NS13"],
            lines=["NSL"],
            station_type=StationType.MRT,
            exits=[Exit(exit_code="A", lat=1.429, lng=103.835, source="onemap")],
            fandom_url="https://example.com"
        )
        assert station.station_id == "NS13"
    
    def test_invalid_station_code(self):
        with pytest.raises(ValueError):
            Stage1Station(
                station_id="invalid",  # Should match pattern
                official_name="YISHUN MRT STATION",
                display_name="Yishun",
                mrt_codes=["NS13"],
                lines=["NSL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.429, lng=103.835, source="onemap")],
                fandom_url="https://example.com"
            )
    
    def test_coordinates_out_of_singapore(self):
        with pytest.raises(ValueError):
            Exit(exit_code="A", lat=50.0, lng=100.0, source="onemap")

class TestSchemaValidation:
    def test_stage1_output_validation(self):
        data = {
            "metadata": {"test": True},
            "stations": [
                {
                    "station_id": "NS13",
                    "official_name": "YISHUN MRT STATION",
                    "display_name": "Yishun",
                    "mrt_codes": ["NS13"],
                    "lines": ["NSL"],
                    "station_type": "mrt",
                    "exits": [{"exit_code": "A", "lat": 1.429, "lng": 103.835, "source": "onemap"}],
                    "fandom_url": "https://example.com"
                }
            ]
        }
        output = Stage1Output.model_validate(data)
        assert len(output.stations) == 1
```

**tests/test_validation.py:**
```python
"""Tests for data validation logic"""

import json
import pytest
from src.pipelines.stage3_merger import Stage3Merger

class TestSanityChecks:
    def test_coordinates_in_singapore(self):
        """Verify coordinates are within Singapore bounds"""
        # Lat: 1.0-2.0, Lng: 103.0-105.0
        valid_coords = [
            (1.35, 103.85),  # Central Singapore
            (1.44, 103.78),  # Northern Singapore
            (1.30, 104.00),  # Eastern Singapore
        ]
        
        for lat, lng in valid_coords:
            assert 1.0 <= lat <= 2.0
            assert 103.0 <= lng <= 105.0
    
    def test_invalid_coordinates(self):
        """Detect coordinates outside Singapore"""
        invalid_coords = [
            (0.0, 103.0),    # Too far south
            (50.0, 103.0),   # Way too far north
            (1.35, 0.0),     # Too far west
            (1.35, 150.0),   # Way too far east
        ]
        
        for lat, lng in invalid_coords:
            assert not (1.0 <= lat <= 2.0 and 103.0 <= lng <= 105.0)

class TestCompletenessChecks:
    def test_station_count(self):
        """Verify expected station count"""
        expected_count = 187
        # This would load actual output
        # assert len(stations) == expected_count
        pass
    
    def test_all_stations_have_exits(self):
        """Every station must have at least one exit"""
        # Implementation would load output and check
        pass
    
    def test_no_duplicate_station_names(self):
        """Station names should be unique"""
        # Implementation would check for duplicates
        pass

class TestDataQuality:
    def test_enrichment_coverage(self):
        """Check what percentage of stations have enrichment data"""
        # Load final output
        # Count stations with/without enrichment
        # Assert coverage > threshold (e.g., 80%)
        pass
    
    def test_exit_code_consistency(self):
        """Verify exit codes are consistent across sources"""
        pass
```

**tests/test_stages.py:**
```python
"""Integration tests for pipeline stages"""

import pytest
import yaml
from src.pipelines.stage1_ingestion import Stage1Ingestion
from src.pipelines.stage2_enrichment import Stage2Enrichment
from src.pipelines.stage3_merger import Stage3Merger

@pytest.fixture
def config():
    with open('config/pipeline.yaml') as f:
        return yaml.safe_load(f)

class TestStage1:
    @pytest.mark.integration
    def test_stage1_execution(self, config):
        """Test Stage 1 runs successfully (requires API access)"""
        stage = Stage1Ingestion(config)
        output = stage.execute(None)
        
        assert len(output.stations) > 0
        assert all(s.fandom_url for s in output.stations)
        assert all(len(s.exits) > 0 for s in output.stations)

class TestStage3:
    def test_exit_code_normalization(self):
        """Test exit code matching logic"""
        from src.pipelines.stage3_merger import Stage3Merger
        
        merger = Stage3Merger({})
        
        # Test various formats
        assert merger._normalize_exit_code("Exit A") == "A"
        assert merger._normalize_exit_code("EXIT B") == "B"
        assert merger._normalize_exit_code("1") == "1"
        assert merger._normalize_exit_code("  a  ") == "A"
```

**tests/conftest.py:**
```python
"""Pytest configuration and fixtures"""

import pytest
import os
import sys

# Ensure src is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

@pytest.fixture
def sample_stage1_output():
    """Sample Stage 1 output for testing"""
    return {
        "metadata": {"test": True},
        "stations": [
            {
                "station_id": "NS13",
                "official_name": "YISHUN MRT STATION",
                "display_name": "Yishun",
                "mrt_codes": ["NS13"],
                "lines": ["NSL"],
                "station_type": "mrt",
                "exits": [
                    {"exit_code": "A", "lat": 1.429, "lng": 103.835, "source": "onemap"}
                ],
                "fandom_url": "https://example.com"
            }
        ]
    }
```

### 4. Post-Run Validation Script (scripts/validate_output.py)

```python
#!/usr/bin/env python3
"""
Post-run validation script for pipeline output.

Usage:
    python scripts/validate_output.py outputs/latest/stage3_final.json
    python scripts/validate_output.py --expected-count 187
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from contracts.schemas import FinalOutput

def validate_schema(filepath: str) -> bool:
    """Validate output against Pydantic schema"""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Handle both wrapped and unwrapped formats
        if 'stations' in data:
            FinalOutput.model_validate(data)
        else:
            # Assume it's a list of stations
            FinalOutput.model_validate({"metadata": {}, "stations": data})
        
        print("✓ Schema validation passed")
        return True
    except Exception as e:
        print(f"✗ Schema validation failed: {e}")
        return False

def validate_completeness(filepath: str, expected_count: int) -> bool:
    """Validate station count"""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    stations = data.get('stations', data)  # Handle both formats
    actual_count = len(stations)
    
    if actual_count >= expected_count:
        print(f"✓ Station count: {actual_count} (expected {expected_count})")
        return True
    else:
        print(f"✗ Station count: {actual_count} (expected {expected_count})")
        return False

def validate_sanity(filepath: str) -> bool:
    """Run sanity checks on data"""
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    stations = data.get('stations', data)
    issues = []
    
    for station in stations:
        name = station.get('official_name', 'unknown')
        
        for exit_data in station.get('exits', []):
            lat = exit_data.get('lat')
            lng = exit_data.get('lng')
            
            if lat is not None and not (1.0 <= lat <= 2.0):
                issues.append(f"Invalid lat {lat} in {name}")
            
            if lng is not None and not (103.0 <= lng <= 105.0):
                issues.append(f"Invalid lng {lng} in {name}")
    
    if issues:
        print(f"✗ Sanity checks failed ({len(issues)} issues):")
        for issue in issues[:5]:
            print(f"  - {issue}")
        if len(issues) > 5:
            print(f"  ... and {len(issues) - 5} more")
        return False
    else:
        print("✓ Sanity checks passed")
        return True

def main():
    parser = argparse.ArgumentParser(description='Validate pipeline output')
    parser.add_argument('input', nargs='?', default='outputs/latest/stage3_final.json',
                       help='Input JSON file')
    parser.add_argument('--expected-count', type=int, default=187,
                       help='Expected station count')
    args = parser.parse_args()
    
    print(f"Validating: {args.input}")
    print("=" * 50)
    
    results = []
    
    # Schema validation
    results.append(validate_schema(args.input))
    
    # Completeness
    results.append(validate_completeness(args.input, args.expected_count))
    
    # Sanity checks
    results.append(validate_sanity(args.input))
    
    print("=" * 50)
    
    if all(results):
        print("✓ All validations passed")
        return 0
    else:
        print("✗ Some validations failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

### 5. Quarterly Automation Script (scripts/quarterly_run.sh)

```bash
#!/bin/bash
# Quarterly MRT Data Pipeline Run
# 
# Usage: ./scripts/quarterly_run.sh
# 
# This script should be run via cron every quarter.
# Add to crontab: 0 2 1 1,4,7,10 * /path/to/mrt-data/scripts/quarterly_run.sh

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RUN_DATE=$(date +%Y-%m-%d)
RUN_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="${PROJECT_DIR}/outputs/${RUN_TIMESTAMP}"
LOG_FILE="${PROJECT_DIR}/logs/pipeline_${RUN_TIMESTAMP}.log"

# Ensure log directory exists
mkdir -p "${PROJECT_DIR}/logs"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Error handling
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log "ERROR: Pipeline failed with exit code $exit_code"
        # Could send alert here
    fi
    exit $exit_code
}
trap cleanup EXIT

log "=========================================="
log "Starting MRT Data Pipeline - ${RUN_DATE}"
log "Output directory: ${OUTPUT_DIR}"
log "Log file: ${LOG_FILE}"
log "=========================================="

# Change to project directory
cd "$PROJECT_DIR"

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    log "Activating virtual environment..."
    source .venv/bin/activate
fi

# Install/update dependencies
log "Installing dependencies..."
pip install -q -e . || pip install -q -r requirements.txt || true

# Run pipeline
log "Running full pipeline..."
python src/orchestrator.py \
    --output-dir "$OUTPUT_DIR" \
    2>&1 | tee -a "$LOG_FILE"

# Validate output
log "Validating output..."
python scripts/validate_output.py \
    "${OUTPUT_DIR}/stage3_final.json" \
    --expected-count 187 \
    2>&1 | tee -a "$LOG_FILE"

# Check for alerts
if [ -f "${OUTPUT_DIR}/alerts.json" ]; then
    ALERT_COUNT=$(python3 -c "import json; print(len(json.load(open('${OUTPUT_DIR}/alerts.json'))))")
    log "Pipeline generated ${ALERT_COUNT} alerts"
    
    # Check for critical alerts
    CRITICAL_COUNT=$(python3 -c "import json; print(sum(1 for a in json.load(open('${OUTPUT_DIR}/alerts.json')) if a['level'] == 'critical'))")
    if [ "$CRITICAL_COUNT" -gt 0 ]; then
        log "WARNING: ${CRITICAL_COUNT} critical alerts detected"
    fi
fi

# Cleanup old outputs (keep last 10)
log "Cleaning up old outputs..."
cd "${PROJECT_DIR}/outputs"
ls -1t | tail -n +11 | xargs -r rm -rf

# Update latest symlink
log "Updating latest symlink..."
ln -sfn "${OUTPUT_DIR}" "${PROJECT_DIR}/outputs/latest"

log "=========================================="
log "Pipeline completed successfully!"
log "Output: ${OUTPUT_DIR}"
log "=========================================="

exit 0
```

### 6. Run Tests Script (scripts/run_tests.sh)

```bash
#!/bin/bash
# Run all tests

set -e

cd "$(dirname "$0")/.."

echo "Running tests..."

# Unit tests
echo "1. Running unit tests..."
python -m pytest tests/ -v --tb=short -x

# Schema validation
echo "2. Running schema validation..."
python -c "from src.contracts.schemas import *; print('✓ All schemas valid')"

# Config validation
echo "3. Running config validation..."
python -c "import yaml; yaml.safe_load(open('config/pipeline.yaml')); print('✓ Config valid')"

echo ""
echo "All tests passed!"
```

---

## Configuration Updates

Add to `config/pipeline.yaml`:

```yaml
alerting:
  enabled: true
  on_failure:
    - log
    - file

testing:
  expected_stations: 187
  min_enrichment_coverage: 0.7  # 70% of stations should have enrichment
  coordinate_bounds:
    lat_min: 1.0
    lat_max: 2.0
    lng_min: 103.0
    lng_max: 105.0
```

---

## Success Criteria

1. [ ] `AlertManager` class implemented with multiple channels
2. [ ] Tests created in `tests/` directory
3. [ ] `pytest tests/` runs successfully
4. [ ] `scripts/validate_output.py` validates schema, completeness, and sanity
5. [ ] `scripts/quarterly_run.sh` runs full pipeline with logging
6. [ ] `scripts/run_tests.sh` runs all tests
7. [ ] Alerts are generated for critical failures (404, schema errors)
8. [ ] Alerts saved to `alerts.json` in output directory
9. [ ] Old outputs automatically cleaned up (keep last 10)
10. [ ] Cron job can trigger `quarterly_run.sh` successfully

---

## Cron Setup

Add to crontab:

```cron
# Run MRT Data Pipeline quarterly (Jan 1, Apr 1, Jul 1, Oct 1 at 2 AM)
0 2 1 1,4,7,10 * /Users/ryanyeo/Projects/mrt-data/scripts/quarterly_run.sh >> /Users/ryanyeo/Projects/mrt-data/logs/cron.log 2>&1
```

---

## Alert Triggers

The following should trigger alerts:

**CRITICAL:**
- HTTP 404 from any API
- HTTP 500 from any API
- Schema validation failure
- Missing required fields
- 100% pipeline failure

**ERROR:**
- Individual station extraction failure
- Missing expected stations (< 187)
- Coordinate out of bounds
- Duplicate station names

**WARNING:**
- Low enrichment coverage (< 70%)
- API timeout (but retry succeeded)
- Data quality warnings

**INFO:**
- Pipeline start/stop
- Stage completion
- Checkpoint saved

---

## Dependencies

**Requires:**
- FEAT-001: Project Restructure & Data Contracts
- FEAT-005: Pipeline Orchestrator & Configuration (partial)

**Required By:**
- None (this is the final operational layer)

---

## Files to Create

1. `src/alerts/__init__.py`
2. `src/alerts/alert_manager.py`
3. `tests/__init__.py`
4. `tests/conftest.py`
5. `tests/test_schemas.py`
6. `tests/test_validation.py`
7. `tests/test_stages.py`
8. `scripts/validate_output.py`
9. `scripts/quarterly_run.sh`
10. `scripts/run_tests.sh`
