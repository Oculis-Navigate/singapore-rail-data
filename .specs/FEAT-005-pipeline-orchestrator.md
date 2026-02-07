# Feature: Pipeline Orchestrator & Configuration

## Feature ID: FEAT-005
**Priority:** P1 (Integration Layer)
**Estimated Effort:** 2-3 hours
**Dependencies:** FEAT-001, FEAT-002, FEAT-003, FEAT-004

---

## Context

### Current State
- Each pipeline stage (Stage 1, 2, 3) can be run independently via separate scripts
- No unified entry point to run the entire pipeline end-to-end
- No checkpoint/resume capability
- Configuration is scattered (env vars, hardcoded values, multiple places)
- No centralized logging or run tracking

### Goal
Create a unified orchestrator that:
1. Runs all pipeline stages sequentially (1 → 2 → 3)
2. Supports resuming from any stage
3. Manages configuration centrally via YAML
4. Saves checkpoints after each stage
5. Tracks run metadata and lineage
6. Provides CLI interface for manual and automated runs

---

## Requirements

### 1. Pipeline Orchestrator (src/orchestrator.py)

Create the main orchestrator class:

```python
#!/usr/bin/env python3
"""
Pipeline Orchestrator

Manages the execution of all pipeline stages with checkpoint support.
"""

import os
import sys
import json
import argparse
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import yaml

from src.contracts.schemas import Stage1Output, Stage2Output, Stage3Output
from src.pipelines.stage1_ingestion import Stage1Ingestion
from src.pipelines.stage2_enrichment import Stage2Enrichment
from src.pipelines.stage3_merger import Stage3Merger
from src.utils.logger import logger

class PipelineOrchestrator:
    """
    Orchestrates the execution of MRT Data Pipeline stages.
    
    Supports:
    - Full pipeline runs (Stage 1 → 2 → 3)
    - Resuming from any stage
    - Checkpoint management
    - Configuration management
    """
    
    def __init__(self, config_path: str = "config/pipeline.yaml"):
        self.config = self._load_config(config_path)
        self.run_id = str(uuid.uuid4())
        self.run_timestamp = datetime.utcnow()
        self.output_base_dir = None
        self.checkpoints = {}
        
        # Initialize stages
        self.stage1 = Stage1Ingestion(self.config)
        self.stage2 = Stage2Enrichment(self.config)
        self.stage3 = Stage3Merger(self.config)
    
    def _load_config(self, config_path: str) -> dict:
        """Load pipeline configuration from YAML"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in config: {e}")
            raise
    
    def _setup_output_directory(self, output_dir: Optional[str] = None) -> str:
        """Setup output directory for this run"""
        if output_dir:
            base_dir = output_dir
        else:
            # Use timestamp-based directory
            timestamp_str = self.run_timestamp.strftime("%Y%m%d_%H%M%S")
            base_dir = f"outputs/{timestamp_str}"
        
        os.makedirs(base_dir, exist_ok=True)
        
        # Create symlink to 'latest'
        latest_link = "outputs/latest"
        if os.path.islink(latest_link):
            os.unlink(latest_link)
        elif os.path.exists(latest_link):
            os.remove(latest_link)
        
        try:
            os.symlink(os.path.abspath(base_dir), latest_link)
        except OSError:
            logger.warning("Could not create 'latest' symlink (may require admin on Windows)")
        
        return base_dir
    
    def _save_run_manifest(self):
        """Save run metadata manifest"""
        manifest = {
            "run_id": self.run_id,
            "timestamp": self.run_timestamp.isoformat(),
            "config": self.config,
            "checkpoints": self.checkpoints,
            "status": "completed"
        }
        
        manifest_path = os.path.join(self.output_base_dir, "manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2, default=str)
        
        logger.info(f"Run manifest saved: {manifest_path}")
    
    def _load_checkpoint(self, stage: int) -> Optional[Any]:
        """Load checkpoint from previous run"""
        checkpoint_file = self.checkpoints.get(f"stage{stage}")
        if not checkpoint_file or not os.path.exists(checkpoint_file):
            return None
        
        try:
            with open(checkpoint_file, 'r') as f:
                data = json.load(f)
            
            # Parse based on stage
            if stage == 1:
                return Stage1Output.model_validate(data)
            elif stage == 2:
                return Stage2Output.model_validate(data)
            elif stage == 3:
                return Stage3Output.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to load checkpoint for stage {stage}: {e}")
            return None
    
    def run_stage1(self, skip_if_exists: bool = False) -> Stage1Output:
        """Execute Stage 1: Deterministic Data Ingestion"""
        logger.section("Executing Stage 1: Deterministic Data Ingestion")
        
        # Check if we should skip
        if skip_if_exists:
            existing = self._load_checkpoint(1)
            if existing:
                logger.info("Stage 1 checkpoint exists, skipping")
                return existing
        
        # Execute
        output = self.stage1.execute(input_data=None)
        
        # Save checkpoint
        checkpoint_path = self.stage1.save_checkpoint(output, self.output_base_dir)
        self.checkpoints["stage1"] = checkpoint_path
        
        return output
    
    def run_stage2(self, stage1_output: Stage1Output, skip_if_exists: bool = False) -> Stage2Output:
        """Execute Stage 2: Enrichment Extraction"""
        logger.section("Executing Stage 2: Enrichment Extraction")
        
        # Check if we should skip
        if skip_if_exists:
            existing = self._load_checkpoint(2)
            if existing:
                logger.info("Stage 2 checkpoint exists, skipping")
                return existing
        
        # Execute
        output = self.stage2.execute(stage1_output)
        
        # Save checkpoint
        checkpoint_path = self.stage2.save_checkpoint(output, self.output_base_dir)
        self.checkpoints["stage2"] = checkpoint_path
        
        return output
    
    def run_stage3(self, stage1_output: Stage1Output, stage2_output: Stage2Output, 
                   skip_if_exists: bool = False) -> Stage3Output:
        """Execute Stage 3: Data Merging & Validation"""
        logger.section("Executing Stage 3: Data Merging & Validation")
        
        # Check if we should skip
        if skip_if_exists:
            existing = self._load_checkpoint(3)
            if existing:
                logger.info("Stage 3 checkpoint exists, skipping")
                return existing
        
        # Execute
        output = self.stage3.execute((stage1_output, stage2_output))
        
        # Save checkpoint
        checkpoint_path = self.stage3.save_checkpoint(output, self.output_base_dir)
        self.checkpoints["stage3"] = checkpoint_path
        
        return output
    
    def run_full_pipeline(self, output_dir: Optional[str] = None, 
                         resume_from: Optional[int] = None) -> Stage3Output:
        """
        Run the complete pipeline from start to finish.
        
        Args:
            output_dir: Custom output directory (default: auto-generated)
            resume_from: Stage number to resume from (1, 2, or 3)
        
        Returns:
            Final Stage3Output
        """
        # Setup
        self.output_base_dir = self._setup_output_directory(output_dir)
        logger.section(f"Starting Pipeline Run: {self.run_id}")
        logger.info(f"Output directory: {self.output_base_dir}")
        
        # Stage 1: Ingestion
        if resume_from is None or resume_from <= 1:
            stage1_output = self.run_stage1()
        else:
            stage1_output = self._load_checkpoint(1)
            if not stage1_output:
                raise ValueError("Cannot resume: Stage 1 checkpoint not found")
        
        # Stage 2: Enrichment
        if resume_from is None or resume_from <= 2:
            stage2_output = self.run_stage2(stage1_output)
        else:
            stage2_output = self._load_checkpoint(2)
            if not stage2_output:
                raise ValueError("Cannot resume: Stage 2 checkpoint not found")
        
        # Stage 3: Merging
        final_output = self.run_stage3(stage1_output, stage2_output)
        
        # Save manifest
        self._save_run_manifest()
        
        # Summary
        logger.section("Pipeline Complete")
        logger.result(f"Run ID: {self.run_id}")
        logger.stats("Total Stations", str(len(final_output.stations)))
        logger.stats("Output Directory", self.output_base_dir)
        
        return final_output
    
    def run_single_stage(self, stage: int, output_dir: Optional[str] = None) -> Any:
        """
        Run a single pipeline stage.
        
        Args:
            stage: Stage number (1, 2, or 3)
            output_dir: Output directory for checkpoints
        """
        self.output_base_dir = self._setup_output_directory(output_dir)
        
        if stage == 1:
            return self.run_stage1()
        elif stage == 2:
            stage1_output = self._load_checkpoint(1)
            if not stage1_output:
                raise ValueError("Stage 1 checkpoint required to run Stage 2")
            return self.run_stage2(stage1_output)
        elif stage == 3:
            stage1_output = self._load_checkpoint(1)
            stage2_output = self._load_checkpoint(2)
            if not stage1_output or not stage2_output:
                raise ValueError("Stage 1 and 2 checkpoints required to run Stage 3")
            return self.run_stage3(stage1_output, stage2_output)
        else:
            raise ValueError(f"Invalid stage number: {stage}")

def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description='MRT Data Pipeline Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline
  python src/orchestrator.py

  # Run with custom output directory
  python src/orchestrator.py --output-dir outputs/custom-run

  # Resume from Stage 2
  python src/orchestrator.py --resume-from 2

  # Run only Stage 1
  python src/orchestrator.py --stage 1

  # Use custom config
  python src/orchestrator.py --config config/custom.yaml
        """
    )
    
    parser.add_argument('--config', default='config/pipeline.yaml',
                       help='Path to pipeline configuration file')
    parser.add_argument('--output-dir', default=None,
                       help='Output directory for results (default: auto-generated)')
    parser.add_argument('--stage', type=int, choices=[1, 2, 3], default=None,
                       help='Run only a single stage (1, 2, or 3)')
    parser.add_argument('--resume-from', type=int, choices=[1, 2, 3], default=None,
                       help='Resume pipeline from specified stage')
    parser.add_argument('--skip-existing', action='store_true',
                       help='Skip stages if checkpoint already exists')
    
    args = parser.parse_args()
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Initialize orchestrator
    orchestrator = PipelineOrchestrator(config_path=args.config)
    
    try:
        if args.stage:
            # Run single stage
            output = orchestrator.run_single_stage(args.stage, args.output_dir)
            logger.result(f"Stage {args.stage} Complete")
        else:
            # Run full pipeline
            output = orchestrator.run_full_pipeline(
                output_dir=args.output_dir,
                resume_from=args.resume_from
            )
            logger.result("Full Pipeline Complete")
        
        # Print final stats
        if hasattr(output, 'stations'):
            logger.stats("Total Stations", str(len(output.stations)))
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### 2. Configuration Management (config/settings.py)

Create a settings module for easy config access:

```python
"""
Configuration management for the pipeline.
"""

import os
from typing import Any
import yaml

class PipelineConfig:
    """Configuration manager with dot notation access"""
    
    def __init__(self, config_path: str = "config/pipeline.yaml"):
        self._config = self._load_config(config_path)
    
    def _load_config(self, path: str) -> dict:
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot notation (e.g., 'stages.stage1.batch_size')"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value
    
    def __getitem__(self, key: str) -> Any:
        return self.get(key)
    
    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None
    
    @property
    def pipeline(self) -> dict:
        return self._config.get('pipeline', {})
    
    @property
    def stages(self) -> dict:
        return self._config.get('stages', {})
    
    @property
    def apis(self) -> dict:
        return self._config.get('apis', {})

# Singleton instance
_config_instance = None

def get_config(config_path: str = None) -> PipelineConfig:
    """Get or create config singleton"""
    global _config_instance
    if _config_instance is None or config_path:
        path = config_path or os.getenv('PIPELINE_CONFIG', 'config/pipeline.yaml')
        _config_instance = PipelineConfig(path)
    return _config_instance
```

### 3. Update config/pipeline.yaml

Ensure the config file is comprehensive:

```yaml
pipeline:
  name: "MRT Data Pipeline"
  version: "2.0.0"
  description: "Singapore MRT/LRT station data extraction and enrichment"

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

# Expected counts for validation
expected_stations: 187
expected_lines: 9  # NSL, EWL, CCL, DTL, NEL, TEL, BPL, SKL, PGL

output:
  versioning: true
  keep_last_n_versions: 10
  symlink_latest: true
  formats:
    - json

logging:
  level: INFO
  format: structured
  
alerting:
  enabled: false  # Set to true when alerting is configured
  on_failure:
    - log
    # - email  # Add when email is configured
    # - webhook  # Add when webhook is configured
```

---

## Success Criteria

1. [ ] `PipelineOrchestrator` class implemented in `src/orchestrator.py`
2. [ ] Can run full pipeline: `python src/orchestrator.py`
3. [ ] Can run single stage: `python src/orchestrator.py --stage 1`
4. [ ] Can resume from stage: `python src/orchestrator.py --resume-from 2`
5. [ ] Saves checkpoints after each stage
6. [ ] Creates run manifest with metadata
7. [ ] Generates timestamped output directories
8. [ ] Creates 'latest' symlink to most recent run
9. [ ] CLI provides helpful usage information
10. [ ] Returns appropriate exit codes (0 for success, 1 for failure)
11. [ ] Configuration is loaded from YAML and accessible via `PipelineConfig`

---

## CLI Usage Examples

```bash
# Full pipeline run (most common)
python src/orchestrator.py

# Run with custom output directory
python src/orchestrator.py --output-dir outputs/quarterly-2026-q1

# Resume from Stage 2 (Stage 1 already complete)
python src/orchestrator.py --resume-from 2

# Run only Stage 1
python src/orchestrator.py --stage 1

# Skip stages if checkpoints exist
python src/orchestrator.py --skip-existing

# Use custom configuration
python src/orchestrator.py --config config/production.yaml
```

---

## Directory Structure After Run

```
outputs/
├── 20260207_143022/           # Timestamp-based directory
│   ├── manifest.json          # Run metadata
│   ├── stage1_deterministic.json
│   ├── stage2_enrichment.json
│   ├── stage3_final.json
│   └── mrt_transit_graph.json # Backward compatible
├── 20260207_150045/           # Previous run
└── latest -> 20260207_143022  # Symlink to most recent
```

---

## Dependencies

**Requires:**
- FEAT-001: Project Restructure & Data Contracts
- FEAT-002: Stage 1 - Deterministic Data Ingestion
- FEAT-003: Stage 2 - Enrichment Extraction Pipeline
- FEAT-004: Stage 3 - Data Merging & Validation

**Required By:**
- FEAT-006: Alerting, Testing & Automation

---

## Integration with Stages

The orchestrator expects each stage to have:

1. `execute(input_data)` method
2. `save_checkpoint(output, output_dir)` method
3. `stage_name` property
4. Input validation via `validate_input()`
5. Output validation via `validate_output()`

These interfaces are defined in FEAT-001 (PipelineStage ABC).

---

## Error Handling

The orchestrator should handle:

1. **Config Not Found**: Clear error message with path
2. **Stage Failure**: Log error, don't save checkpoint for failed stage
3. **Missing Checkpoint**: Clear message when resuming fails
4. **Invalid Stage Number**: Validation before execution
5. **Disk Full**: Try-catch around file operations
6. **Keyboard Interrupt**: Graceful shutdown, save partial results
