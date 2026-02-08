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
    required_keys = ['pipeline']
    for key in required_keys:
        if key not in config:
            print(f"Missing required config key: {key}")
            return False
    
    # Check nested structure
    pipeline = config['pipeline']
    required_pipeline_keys = ['stages', 'apis', 'output']
    for key in required_pipeline_keys:
        if key not in pipeline:
            print(f"Missing required pipeline config key: {key}")
            return False
    
    return True


def run_stage(stage_name: str, config: Dict[str, Any], input_data: Any = None, dry_run: bool = False) -> Optional[Any]:
    """Run a specific pipeline stage with proper input data"""
    try:
        if dry_run:
            print(f"DRY RUN: Would execute stage {stage_name}")
            return None
        
        print(f"Executing stage: {stage_name}")
        
        # Import and instantiate the appropriate stage
        if stage_name == "stage1_ingestion":
            from src.pipelines.stage1_ingestion import Stage1Ingestion
            stage = Stage1Ingestion(config)
            # Stage 1 expects None as input (per specification)
            stage_input_data = None
        elif stage_name == "stage2_enrichment":
            from src.pipelines.stage2_enrichment import Stage2Enrichment
            stage = Stage2Enrichment(config)
            # Stage 2 expects Stage1Output as input
            stage_input_data = input_data
        elif stage_name == "stage3_merger":
            from src.pipelines.stage3_merger import Stage3Merger
            stage = Stage3Merger(config)
            # Stage 3 expects (Stage1Output, Stage2Output) as input
            stage_input_data = input_data
        else:
            raise ValueError(f"Unknown stage: {stage_name}")
        
        # Validate input with correct data
        if not stage.validate_input(stage_input_data):  # type: ignore
            print(f"Input validation failed for {stage_name}")
            return None
        
        # Execute stage with proper input
        output = stage.execute(stage_input_data)  # type: ignore
        
        if not stage.validate_output(output):  # type: ignore
            print(f"Output validation failed for {stage_name}")
            return None
        
        print(f"Stage {stage_name} completed successfully")
        return output
        
    except ImportError as e:
        print(f"ERROR: Failed to import stage {stage_name}: {e}")
        return None
    except Exception as e:
        print(f"ERROR: Stage {stage_name} failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_full_pipeline(config: Dict[str, Any], dry_run: bool = False) -> bool:
    """Run the complete pipeline with proper data flow"""
    print("Starting MRT Data Pipeline...")
    print("=" * 50)
    
    # Stage 1: Ingestion (input: None)
    if not config["pipeline"]["stages"].get("stage1_ingestion", {}).get("enabled", True):
        print("Skipping disabled stage: stage1_ingestion")
        stage1_output = None
    else:
        print("Stage 1/3: Deterministic Data Ingestion")
        stage1_output = run_stage("stage1_ingestion", config, None, dry_run)
        if stage1_output is None and not dry_run:
            print("❌ Pipeline failed at stage: stage1_ingestion")
            return False
        if not dry_run and stage1_output:
            print(f"✅ Stage 1 complete: {len(stage1_output.stations)} stations")
    
    # Stage 2: Enrichment (input: Stage1Output)
    if not config["pipeline"]["stages"].get("stage2_enrichment", {}).get("enabled", True):
        print("Skipping disabled stage: stage2_enrichment")
        stage2_output = None
    else:
        print("\nStage 2/3: Enrichment Data Extraction")
        stage2_output = run_stage("stage2_enrichment", config, stage1_output, dry_run)
        if stage2_output is None and not dry_run:
            print("❌ Pipeline failed at stage: stage2_enrichment")
            return False
        if not dry_run and stage2_output:
            print(f"✅ Stage 2 complete: {len(stage2_output.stations)} stations enriched")
    
    # Stage 3: Merger (input: (Stage1Output, Stage2Output))
    if not config["pipeline"]["stages"].get("stage3_merger", {}).get("enabled", True):
        print("Skipping disabled stage: stage3_merger")
        final_output = None
    else:
        print("\nStage 3/3: Data Merging & Validation")
        stage3_input = (stage1_output, stage2_output)
        final_output = run_stage("stage3_merger", config, stage3_input, dry_run)
        if final_output is None and not dry_run:
            print("❌ Pipeline failed at stage: stage3_merger")
            return False
        if not dry_run and final_output:
            print(f"✅ Stage 3 complete: {len(final_output.stations)} stations in final output")
    
    print("\n" + "=" * 50)
    if not dry_run:
        print("🎉 Full pipeline completed successfully!")
        if final_output:
            print(f"📊 Final result: {len(final_output.stations)} stations processed")
        else:
            print("📊 Final result: Pipeline completed with no output")
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
        if args.stage == "stage1_ingestion":
            result = run_stage(args.stage, config, None, args.dry_run)
        elif args.stage == "stage2_enrichment":
            # For single stage 2 execution, we need to load Stage 1 output
            # This is a limitation - full pipeline is recommended
            print("WARNING: Stage 2 requires Stage 1 output. Run full pipeline or provide --stage1-input")
            return 1
        elif args.stage == "stage3_merger":
            print("WARNING: Stage 3 requires Stage 1 and Stage 2 outputs. Run full pipeline")
            return 1
        else:
            result = run_stage(args.stage, config, None, args.dry_run)
        success = result is not None or args.dry_run
    else:
        success = run_full_pipeline(config, args.dry_run)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())