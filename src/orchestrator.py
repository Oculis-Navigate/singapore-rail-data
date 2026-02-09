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

from src.contracts.schemas import Stage1Output, Stage2Output, FinalOutput
from src.pipelines.stage1_ingestion import Stage1Ingestion
from src.pipelines.stage2_enrichment import Stage2Enrichment
from src.pipelines.stage3_merger import Stage3Merger
from src.alerts.alert_manager import AlertManager, AlertLevel
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
        
        # Initialize alerting
        self.alert_manager = AlertManager(self.config)
        
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
        if not self.output_base_dir:
            raise ValueError("Output directory not set")
            
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
        # First check if we have a checkpoint path stored
        checkpoint_file = self.checkpoints.get(f"stage{stage}")
        
        # If not, look for checkpoint file in output directory
        if not checkpoint_file and self.output_base_dir:
            checkpoint_patterns = [
                f"stage{stage}_deterministic.json",
                f"stage{stage}_enrichment.json", 
                f"stage{stage}_final.json",
                f"stage{stage}.json"
            ]
            for pattern in checkpoint_patterns:
                potential_path = os.path.join(self.output_base_dir, pattern)
                if os.path.exists(potential_path):
                    checkpoint_file = potential_path
                    break
        
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
                return FinalOutput.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to load checkpoint for stage {stage}: {e}")
            return None
    
    def run_stage1(self, skip_if_exists: bool = False) -> Stage1Output:
        """Execute Stage 1: Deterministic Data Ingestion"""
        logger.section("Executing Stage 1: Deterministic Data Ingestion")
        self.alert_manager.info("Starting Stage 1: Deterministic Data Ingestion")
        
        # Check if we should skip
        if skip_if_exists:
            existing = self._load_checkpoint(1)
            if existing:
                logger.info("Stage 1 checkpoint exists, skipping")
                self.alert_manager.info("Stage 1 checkpoint exists, skipping execution")
                return existing
        
        try:
            # Execute
            output = self.stage1.execute(input_data=None)
            
            # Save checkpoint
            if not self.output_base_dir:
                raise ValueError("Output directory not set")
            checkpoint_path = self.stage1.save_checkpoint(output, self.output_base_dir)
            self.checkpoints["stage1"] = checkpoint_path
            
            self.alert_manager.info(f"Stage 1 complete: {len(output.stations)} stations ingested")
            return output
        except Exception as e:
            self.alert_manager.critical(f"Stage 1 failed: {str(e)}", {"error_type": type(e).__name__})
            raise
    
    def run_stage2(self, stage1_output: Stage1Output, skip_if_exists: bool = False) -> Stage2Output:
        """Execute Stage 2: Enrichment Extraction"""
        logger.section("Executing Stage 2: Enrichment Extraction")
        self.alert_manager.info("Starting Stage 2: Enrichment Extraction")
        
        # Check if we should skip
        if skip_if_exists:
            existing = self._load_checkpoint(2)
            if existing:
                logger.info("Stage 2 checkpoint exists, skipping")
                self.alert_manager.info("Stage 2 checkpoint exists, skipping execution")
                return existing
        
        try:
            # Execute
            output = self.stage2.execute(stage1_output)
            
            # Save checkpoint
            if not self.output_base_dir:
                raise ValueError("Output directory not set")
            checkpoint_path = self.stage2.save_checkpoint(output, self.output_base_dir)
            self.checkpoints["stage2"] = checkpoint_path
            
            # Calculate enrichment coverage
            total_stations = len(output.stations)
            enriched_count = sum(1 for s in output.stations.values() if s.extraction_result == "success")
            coverage = enriched_count / total_stations if total_stations > 0 else 0
            
            self.alert_manager.info(
                f"Stage 2 complete: {enriched_count}/{total_stations} stations enriched ({coverage:.1%} coverage)"
            )
            
            # Warn if coverage is low
            if coverage < 0.7:
                self.alert_manager.warning(
                    f"Low enrichment coverage: {coverage:.1%} (threshold: 70%)",
                    {"coverage": coverage, "threshold": 0.7}
                )
            
            return output
        except Exception as e:
            self.alert_manager.critical(f"Stage 2 failed: {str(e)}", {"error_type": type(e).__name__})
            raise
    
    def run_stage3(self, stage1_output: Stage1Output, stage2_output: Stage2Output, 
                   skip_if_exists: bool = False) -> FinalOutput:
        """Execute Stage 3: Data Merging & Validation"""
        logger.section("Executing Stage 3: Data Merging & Validation")
        self.alert_manager.info("Starting Stage 3: Data Merging & Validation")
        
        # Check if we should skip
        if skip_if_exists:
            existing = self._load_checkpoint(3)
            if existing:
                logger.info("Stage 3 checkpoint exists, skipping")
                self.alert_manager.info("Stage 3 checkpoint exists, skipping execution")
                return existing
        
        try:
            # Execute
            output = self.stage3.execute((stage1_output, stage2_output))
            
            # Save checkpoint
            if not self.output_base_dir:
                raise ValueError("Output directory not set")
            checkpoint_path = self.stage3.save_checkpoint(output, self.output_base_dir)
            self.checkpoints["stage3"] = checkpoint_path
            
            # Check station count
            expected_stations = self.config.get('pipeline', {}).get('expected_stations', 187)
            actual_stations = len(output.stations)
            
            if actual_stations < expected_stations:
                self.alert_manager.error(
                    f"Station count below expected: {actual_stations} < {expected_stations}",
                    {"expected": expected_stations, "actual": actual_stations}
                )
            
            self.alert_manager.info(f"Stage 3 complete: {actual_stations} stations merged and validated")
            return output
        except Exception as e:
            self.alert_manager.critical(f"Stage 3 failed: {str(e)}", {"error_type": type(e).__name__})
            raise
    
    def run_full_pipeline(self, output_dir: Optional[str] = None, 
                         resume_from: Optional[int] = None) -> FinalOutput:
        """
        Run the complete pipeline from start to finish.
        
        Args:
            output_dir: Custom output directory (default: auto-generated)
            resume_from: Stage number to resume from (1, 2, or 3)
        
        Returns:
            Final FinalOutput
        """
        # Setup
        self.output_base_dir = self._setup_output_directory(output_dir)
        logger.section(f"Starting Pipeline Run: {self.run_id}")
        logger.info(f"Output directory: {self.output_base_dir}")
        
        # Add file channel for alerts to output directory
        from src.alerts.alert_manager import FileChannel
        file_channel = FileChannel(self.output_base_dir)
        self.alert_manager.channels.append(file_channel)
        
        self.alert_manager.info(
            "Pipeline started",
            {"run_id": self.run_id, "output_dir": self.output_base_dir, "resume_from": resume_from}
        )
        
        try:
            # Stage 1: Ingestion
            if resume_from is None or resume_from <= 1:
                stage1_output = self.run_stage1()
            else:
                stage1_output = self._load_checkpoint(1)
                if not stage1_output:
                    raise ValueError("Cannot resume: Stage 1 checkpoint not found")
                self.alert_manager.info("Resumed from Stage 1 checkpoint")
            
            # Stage 2: Enrichment
            if resume_from is None or resume_from <= 2:
                stage2_output = self.run_stage2(stage1_output)
            else:
                stage2_output = self._load_checkpoint(2)
                if not stage2_output:
                    raise ValueError("Cannot resume: Stage 2 checkpoint not found")
                self.alert_manager.info("Resumed from Stage 2 checkpoint")
            
            # Stage 3: Merging
            final_output = self.run_stage3(stage1_output, stage2_output)
            
            # Save manifest
            self._save_run_manifest()
            
            # Save alerts
            alerts_path = os.path.join(self.output_base_dir, "alerts.json")
            self.alert_manager.save_alert_log(alerts_path)
            logger.info(f"Alert log saved: {alerts_path}")
            
            # Summary
            logger.section("Pipeline Complete")
            logger.result(f"Run ID: {self.run_id}")
            logger.stats("Total Stations", str(len(final_output.stations)))
            logger.stats("Output Directory", self.output_base_dir)
            
            # Final alert
            alert_summary = {
                "total_alerts": self.alert_manager.get_alert_count(),
                "critical": self.alert_manager.get_alert_count(AlertLevel.CRITICAL),
                "error": self.alert_manager.get_alert_count(AlertLevel.ERROR),
                "warning": self.alert_manager.get_alert_count(AlertLevel.WARNING),
                "info": self.alert_manager.get_alert_count(AlertLevel.INFO),
            }
            
            if self.alert_manager.has_critical_alerts():
                self.alert_manager.critical(
                    "Pipeline completed with critical alerts",
                    alert_summary
                )
            else:
                self.alert_manager.info(
                    "Pipeline completed successfully",
                    alert_summary
                )
            
            return final_output
            
        except Exception as e:
            self.alert_manager.critical(
                f"Pipeline failed: {str(e)}",
                {"error_type": type(e).__name__, "run_id": self.run_id}
            )
            # Save alerts even on failure
            if self.output_base_dir:
                alerts_path = os.path.join(self.output_base_dir, "alerts.json")
                self.alert_manager.save_alert_log(alerts_path)
            raise
    
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
        description="MRT Data Pipeline Orchestrator",
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