#!/usr/bin/env python3
"""
Standalone script to run Stage 1: Deterministic Data Ingestion

Usage:
    python scripts/run_stage1.py --output-dir outputs/2026-02-07
    python scripts/run_stage1.py --config config/pipeline.yaml
"""

import os
import sys
import argparse
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.pipelines.stage1_ingestion import Stage1Ingestion
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
    parser = argparse.ArgumentParser(description='Run Stage 1: Deterministic Data Ingestion')
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
    
    # Load environment variables
    load_dotenv()
    
    # Run stage
    stage = Stage1Ingestion(config)
    output = stage.execute(input_data=None)
    
    # Save checkpoint
    checkpoint_path = stage.save_checkpoint(output, args.output_dir)
    
    # Print summary
    logger.result("Stage 1 Complete")
    logger.stats("Total Stations", str(len(output.stations)))
    logger.stats("Checkpoint", checkpoint_path)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())