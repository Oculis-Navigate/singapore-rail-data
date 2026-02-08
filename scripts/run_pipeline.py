#!/usr/bin/env python3
"""
MRT Data Pipeline Entry Point

This is the main CLI entry point for the MRT data pipeline.
It orchestrates all three stages: ingestion, enrichment, and merging.

Usage:
    python run_pipeline.py [--stage STAGE] [--config CONFIG] [--dry-run]
"""

import os
import sys
import argparse
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.contracts.schemas import Stage1Output, Stage2Output, FinalOutput
from src.contracts.interfaces import PipelineStage


def load_config(config_path: str) -> Dict[str, Any]:
    """Load pipeline configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration structure"""
    required_keys = ['pipeline', 'stages', 'apis', 'output']
    for key in required_keys:
        if key not in config:
            print(f"Missing required config key: {key}")
            return False
    return True


def run_stage(stage_name: str, config: Dict[str, Any], dry_run: bool = False) -> Optional[Any]:
    """Run a specific pipeline stage"""
    if dry_run:
        print(f"DRY RUN: Would execute stage {stage_name}")
        return None
    
    # TODO: Implement actual stage execution
    print(f"Executing stage: {stage_name}")
    
    # Import and instantiate the appropriate stage
    if stage_name == "stage1_ingestion":
        from src.pipelines.stage1_ingestion import Stage1Ingestion
        stage = Stage1Ingestion(config)
    elif stage_name == "stage2_enrichment":
        from src.pipelines.stage2_enrichment import Stage2Enrichment
        stage = Stage2Enrichment(config)
    elif stage_name == "stage3_merger":
        from src.pipelines.stage3_merger import Stage3Merger
        stage = Stage3Merger(config)
    else:
        raise ValueError(f"Unknown stage: {stage_name}")
    
    # TODO: Pass appropriate input data to stage
    input_data = {"config": config[config["pipeline"]["stages"].get(stage_name, {})]}
    
    if not stage.validate_input(input_data):
        print(f"Input validation failed for {stage_name}")
        return None
    
    output = stage.execute(input_data)
    
    if not stage.validate_output(output):
        print(f"Output validation failed for {stage_name}")
        return None
    
    print(f"Stage {stage_name} completed successfully")
    return output


def run_full_pipeline(config: Dict[str, Any], dry_run: bool = False) -> bool:
    """Run the complete pipeline"""
    stages = ["stage1_ingestion", "stage2_enrichment", "stage3_merger"]
    
    for stage_name in stages:
        if not config["pipeline"]["stages"].get(stage_name, {}).get("enabled", True):
            print(f"Skipping disabled stage: {stage_name}")
            continue
            
        result = run_stage(stage_name, config, dry_run)
        if result is None and not dry_run:
            print(f"Pipeline failed at stage: {stage_name}")
            return False
    
    if not dry_run:
        print("Full pipeline completed successfully")
    else:
        print("DRY RUN: Full pipeline would execute successfully")
    
    return True


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="MRT Data Pipeline")
    parser.add_argument(
        "--stage", 
        choices=["stage1_ingestion", "stage2_enrichment", "stage3_merger"],
        help="Run specific stage (default: run full pipeline)"
    )
    parser.add_argument(
        "--config",
        default="config/pipeline.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without running"
    )
    
    args = parser.parse_args()
    
    # Load and validate configuration
    if not os.path.exists(args.config):
        print(f"Configuration file not found: {args.config}")
        return 1
    
    config = load_config(args.config)
    if not validate_config(config):
        print("Configuration validation failed")
        return 1
    
    print(f"MRT Data Pipeline v{config['pipeline']['version']}")
    
    # Run pipeline
    if args.stage:
        result = run_stage(args.stage, config, args.dry_run)
        success = result is not None or args.dry_run
    else:
        success = run_full_pipeline(config, args.dry_run)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())