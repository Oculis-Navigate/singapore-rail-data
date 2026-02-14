#!/usr/bin/env python3
"""
Standalone script to run Stage 2: Enrichment Extraction

Usage:
    python scripts/run_stage2.py --stage1-output outputs/2026-02-07/stage1_deterministic.json
    python scripts/run_stage2.py --output-dir outputs/2026-02-07
    python scripts/run_stage2.py --stage1-output outputs/latest/stage1_deterministic.json --resume
    python scripts/run_stage2.py --stage1-output outputs/latest/stage1_deterministic.json --restart
    python scripts/run_stage2.py --stage1-output outputs/latest/stage1_deterministic.json --resume --retry-failed
"""

import os
import sys
import json
import argparse
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.contracts.schemas import Stage1Output
from src.pipelines.stage2_enrichment import Stage2Enrichment
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
    parser = argparse.ArgumentParser(description='Run Stage 2: Enrichment Extraction')
    parser.add_argument('--stage1-output', required=True, help='Path to Stage 1 output JSON')
    parser.add_argument('--output-dir', default='outputs/latest', help='Output directory')
    parser.add_argument('--config', default='config/pipeline.yaml', help='Config file path')
    parser.add_argument('--resume', action='store_true', help='Resume from existing checkpoint')
    parser.add_argument('--restart', action='store_true', help='Restart and ignore existing checkpoint')
    parser.add_argument('--retry-failed', action='store_true', help='Retry permanently failed stations (useful after fixing validation issues)')
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
    if not os.path.exists(args.stage1_output):
        print(f"Stage 1 output file not found: {args.stage1_output}")
        return 1

    with open(args.stage1_output, 'r') as f:
        stage1_data = json.load(f)

    stage1_output = Stage1Output.model_validate(stage1_data)

    # Load environment variables
    load_dotenv()

    # Check for existing checkpoint (main, backup, or enrichment)
    checkpoint_path = os.path.join(args.output_dir, "stage2_incremental.json")
    backup_path = os.path.join(args.output_dir, "stage2_incremental.json.bak")
    enrichment_path = os.path.join(args.output_dir, "stage2_enrichment.json")
    resume_mode = False

    checkpoint_exists = os.path.exists(checkpoint_path) or os.path.exists(backup_path) or os.path.exists(enrichment_path)

    if checkpoint_exists and not args.restart:
        if args.resume:
            resume_mode = True
            logger.info("Resuming from checkpoint (--resume flag provided)")
        else:
            # Prompt user
            temp_stage = Stage2Enrichment(config, args.output_dir, resume_mode=False)
            checkpoint = temp_stage._load_incremental_checkpoint()
            if checkpoint and temp_stage._prompt_for_resume(checkpoint):
                resume_mode = True

    # Initialize and run
    stage = Stage2Enrichment(config, args.output_dir, resume_mode, retry_failed=args.retry_failed)
    stage.stage1_output_path = args.stage1_output  # Store for resume message
    output = stage.execute(stage1_output)

    # Save final checkpoint (only if completed, not timed out)
    if not output.metadata.get("timeout_reached", False):
        checkpoint_path = stage.save_checkpoint(output, args.output_dir)

        # Print summary
        logger.result("Stage 2 Complete")
        logger.stats("Successful", str(len(output.stations)))
        logger.stats("Failed", str(len([f for f in output.failed_stations if f.get("permanent")])))
        logger.stats("Skipped (not on Fandom)", str(len(output.skipped_stations)))
        logger.stats("Checkpoint", checkpoint_path)
    else:
        # Timed out - checkpoint already saved as incremental
        logger.result("Stage 2 Paused (Time Limit Reached)")
        logger.stats("Processed", str(len(output.stations)))
        logger.stats("Failed", str(len(output.failed_stations)))

    return 0


if __name__ == "__main__":
    sys.exit(main())