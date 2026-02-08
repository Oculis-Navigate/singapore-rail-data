#!/usr/bin/env python3
"""
Standalone script to run Stage 3: Data Merging & Validation

Usage:
    python scripts/run_stage3.py \
        --stage1 outputs/2026-02-07/stage1_deterministic.json \
        --stage2 outputs/2026-02-07/stage2_enrichment.json \
        --output-dir outputs/2026-02-07
"""

import argparse
import json
import os
import sys
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.contracts.schemas import Stage1Output, Stage2Output
from src.pipelines.stage3_merger import Stage3Merger
from src.utils.logger import logger


def load_config(config_path: str) -> dict:
    """Load pipeline configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def validate_config(config: dict) -> bool:
    """Validate configuration structure"""
    required_keys = ['pipeline']
    for key in required_keys:
        if key not in config:
            print(f"Missing required config key: {key}")
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description='Run Stage 3: Data Merging & Validation')
    parser.add_argument('--stage1', required=True, help='Path to Stage 1 output JSON')
    parser.add_argument('--stage2', required=True, help='Path to Stage 2 output JSON')
    parser.add_argument('--output-dir', default='outputs/latest', help='Output directory')
    parser.add_argument('--config', default='config/pipeline.yaml', help='Config file path')
    args = parser.parse_args()
    
    # Load and validate configuration
    if not os.path.exists(args.config):
        print(f"Configuration file not found: {args.config}")
        return 1
    
    config = load_config(args.config)
    if not validate_config(config):
        print("Configuration validation failed")
        return 1
    
    # Load Stage 1 output
    if not os.path.exists(args.stage1):
        print(f"Stage 1 output file not found: {args.stage1}")
        return 1
    
    with open(args.stage1, 'r') as f:
        stage1_data = json.load(f)
    stage1_output = Stage1Output.model_validate(stage1_data)
    
    # Load Stage 2 output
    if not os.path.exists(args.stage2):
        print(f"Stage 2 output file not found: {args.stage2}")
        return 1
    
    with open(args.stage2, 'r') as f:
        stage2_data = json.load(f)
    stage2_output = Stage2Output.model_validate(stage2_data)
    
    # Load environment variables
    load_dotenv()
    
    # Run stage
    stage = Stage3Merger(config)
    output = stage.execute((stage1_output, stage2_output))
    
    # Save checkpoint
    checkpoint_path = stage.save_checkpoint(output, args.output_dir)
    
    # Print summary
    logger.result("Stage 3 Complete")
    logger.stats("Total Stations", str(len(output.stations)))
    logger.stats("Enriched Stations", str(output.metadata.get('enriched_stations', 0)))
    logger.stats("Final Output", checkpoint_path)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())