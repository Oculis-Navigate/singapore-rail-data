"""
Stage 2: Enrichment Extraction

This stage handles extracting additional station information from
enrichment sources like Fandom wiki and LLM APIs.
"""

import time
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from tqdm import tqdm
from ..contracts.interfaces import PipelineStage
from ..contracts.schemas import (
    Stage1Output, Stage2Output, Stage2Station, EnrichedExit,
    Platform, BusStop, Stage1Station, Stage2IncrementalOutput
)
from ..utils.logger import logger


class Stage2Enrichment(PipelineStage):
    """
    Stage 2: Extract enrichment data from Fandom wiki using OpenRouter LLM.
    
    Input: Stage1Output (stations with Fandom URLs)
    Output: Stage2Output (enrichment data for each station)
    """
    
    def __init__(self, config: dict, output_dir: str = "outputs/latest", resume_mode: bool = False, retry_failed: bool = False):
        self.config = config
        self.stage_config = config.get('stages', {}).get('stage2_enrichment', {})
        self.batch_size = self.stage_config.get('batch_size', 8)
        self.delay_seconds = self.stage_config.get('delay_seconds', 2)
        self.max_retries = self.stage_config.get('max_retries', 3)
        self.retry_delay = self.stage_config.get('retry_delay_seconds', 5)
        self.daily_timeout_minutes = self.stage_config.get('daily_timeout_minutes', 90)
        self.checkpoint_interval = self.stage_config.get('checkpoint_interval', 1)
        self.output_dir = output_dir
        self.resume_mode = resume_mode
        self.retry_failed = retry_failed
        self.all_stations = []
        self.stage1_output_path = None
        
        # Test mode detection - clean configuration-based approach
        self.test_mode = self.stage_config.get('test_mode', False)
        
        # Lazy initialization - clients created only when needed
        self._llm_client = None
        self._scraper = None
    
    @property
    def stage_name(self) -> str:
        return "stage2_enrichment"
    
    @property
    def llm_client(self):
        """Lazy initialization of LLM client with test mode support"""
        if self._llm_client is None:
            if self.test_mode:
                raise RuntimeError(
                    "LLM client not available in test mode. Set test_mode=false "
                    "or provide OPENROUTER_API_KEY environment variable"
                )
            from .openrouter_client import OpenRouterClient
            self._llm_client = OpenRouterClient(self.config)
        return self._llm_client
    
    @property
    def scraper(self):
        """Lazy initialization of Fandom scraper with test mode support"""
        if self._scraper is None:
            if self.test_mode:
                raise RuntimeError(
                    "Fandom scraper not available in test mode. Set test_mode=false "
                    "or configure proper network access"
                )
            from .fandom_scraper import FandomScraper
            self._scraper = FandomScraper(self.config)
        return self._scraper
    
    def execute(self, input_data: Stage1Output) -> Stage2Output:
        """
        Execute Stage 2 enrichment pipeline.

        Steps:
        1. Validate input
        2. Check for existing checkpoint (resume mode)
        3. Process stations with progress bar
        4. Save incremental checkpoint after each station
        5. Handle 90-minute timeout gracefully
        6. Retry failed stations with permanent failure tracking
        7. Compile results into Stage2Output
        """
        logger.section("Stage 2: Enrichment Data Extraction")

        if not self.validate_input(input_data):
            raise ValueError("Invalid input for Stage 2")

        # Store all stations for checkpoint metadata
        self.all_stations = input_data.stations
        stations = input_data.stations

        # Check for existing checkpoint
        checkpoint = self._load_incremental_checkpoint()
        if checkpoint and self.resume_mode:
            processed_ids = set(checkpoint.processed_station_ids)
            # Filter out permanently failed stations (unless retry_failed is set)
            if self.retry_failed:
                # Reset permanent failures to allow retry
                permanently_failed_ids = set()
                failed_station_ids = {f["station_id"] for f in checkpoint.failed_stations}
                for failure in checkpoint.failed_stations:
                    if failure.get("permanent", False):
                        failure["permanent"] = False
                        failure["retry_attempted"] = True
                # Remove failed stations from processed_ids so they get reprocessed
                processed_ids = processed_ids - failed_station_ids
                logger.info(f"🔄 Retry mode: {len(failed_station_ids)} previously failed stations will be retried")
            else:
                permanently_failed_ids = set(
                    f["station_id"] for f in checkpoint.failed_stations
                    if f.get("permanent", False)
                )
            logger.info(f"Resuming from checkpoint: {len(processed_ids)}/{len(stations)} stations already processed")
            if not self.retry_failed:
                logger.info(f"Skipping {len(permanently_failed_ids)} permanently failed stations")
        else:
            processed_ids = set()
            permanently_failed_ids = set()

        # Initialize results (use checkpoint data if resuming)
        if checkpoint and self.resume_mode:
            # Filter out failed stations from processed_station_ids if retrying
            processed_station_ids = checkpoint.processed_station_ids.copy()
            stations_dict = checkpoint.stations.copy()
            failed_list = checkpoint.failed_stations.copy()
            
            if self.retry_failed:
                failed_ids = {f["station_id"] for f in checkpoint.failed_stations}
                processed_station_ids = [sid for sid in processed_station_ids if sid not in failed_ids]
                # Remove failed stations from stations dict so they can be reprocessed
                for station_id in failed_ids:
                    stations_dict.pop(station_id, None)
                # Clear failed list - they'll be re-added if they fail again
                failed_list = []
            
            results = {
                "stations": stations_dict,
                "failed_stations": failed_list,
                "skipped_stations": list(getattr(checkpoint, 'skipped_stations', [])),
                "processed_station_ids": processed_station_ids,
                "retry_queue": []
            }
        else:
            results = {
                "stations": {},
                "failed_stations": [],
                "skipped_stations": [],
                "processed_station_ids": [],
                "retry_queue": []
            }

        # Filter stations to process (exclude processed and permanently failed)
        stations_to_process = [
            s for s in stations
            if s.station_id not in processed_ids and s.station_id not in permanently_failed_ids
        ]

        # Setup progress bar
        initial_count = len(processed_ids)
        pbar = tqdm(
            total=len(stations),
            initial=initial_count,
            desc="Processing stations",
            unit="station",
            bar_format="{desc}: {n_fmt}/{total_fmt} [{percentage:3.0f}%] {elapsed}<{remaining}, {rate_fmt}"
        )

        start_time = time.time()
        timeout_seconds = self.daily_timeout_minutes * 60

        try:
            for station in stations_to_process:
                # Check timeout before processing
                elapsed = time.time() - start_time
                if elapsed >= timeout_seconds:
                    logger.info(f"⏰ Daily limit timer reached ({self.daily_timeout_minutes} min)")
                    self._save_incremental_checkpoint(results, timeout_reached=True)
                    pbar.close()
                    self._print_resume_message(len(results["processed_station_ids"]), len(stations))

                    # Return partial results
                    return Stage2Output(
                        metadata={
                            "timestamp": datetime.utcnow().isoformat(),
                            "source": "stage2_enrichment",
                            "total_stations": len(stations),
                            "successful": len(results["stations"]),
                            "failed": len(results["failed_stations"]),
                            "skipped_no_fandom": len(results.get("skipped_stations", [])),
                            "timeout_reached": True
                        },
                        stations=results["stations"],
                        failed_stations=results["failed_stations"],
                        skipped_stations=results.get("skipped_stations", []),
                        retry_queue=[]
                    )

                try:
                    enriched = self._extract_station(station)
                    
                    if enriched is None:
                        # Station not on Fandom - skip it
                        # Check if already in skipped list to avoid duplicates
                        already_skipped = any(
                            s["station_id"] == station.station_id 
                            for s in results["skipped_stations"]
                        )
                        if not already_skipped:
                            results["skipped_stations"].append({
                                "station_id": station.station_id,
                                "official_name": station.official_name,
                                "reason": "not_on_fandom",
                                "timestamp": datetime.utcnow().isoformat()
                            })
                        
                        # Remove from other lists if present
                        results["stations"].pop(station.station_id, None)
                        results["failed_stations"] = [
                            f for f in results["failed_stations"]
                            if f["station_id"] != station.station_id
                        ]
                        
                        # Only add to processed if not already there
                        if station.station_id not in results["processed_station_ids"]:
                            results["processed_station_ids"].append(station.station_id)
                        # Don't add to retry queue - skip permanently
                        continue
                    
                    results["stations"][station.station_id] = enriched
                    results["processed_station_ids"].append(station.station_id)
                    logger.item(f"✓ {station.official_name}")
                except Exception as e:
                    logger.warning(f"✗ {station.official_name}: {e}")
                    # Check if station already has a failure entry (e.g., from previous run)
                    existing_failure = None
                    for failure in results["failed_stations"]:
                        if failure["station_id"] == station.station_id:
                            existing_failure = failure
                            break
                    
                    if existing_failure:
                        # Update existing failure entry
                        existing_failure["error"] = str(e)
                        existing_failure["permanent"] = False
                        existing_failure["timestamp"] = datetime.utcnow().isoformat()
                    else:
                        # Add new failure entry
                        results["failed_stations"].append({
                            "station_id": station.station_id,
                            "error": str(e),
                            "permanent": False,  # Will be marked True after retries fail
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    results["retry_queue"].append(station.station_id)
                    results["processed_station_ids"].append(station.station_id)

                # Retry failed stations immediately
                if station.station_id in results["retry_queue"]:
                    self._retry_failed_stations(results, [station])

                # Save checkpoint after every station
                self._save_incremental_checkpoint(results)
                pbar.update(1)

                # Small delay to avoid rate limiting
                time.sleep(self.delay_seconds)

            pbar.close()

        except Exception as pipeline_error:
            pbar.close()
            # Save partial checkpoint on pipeline failure
            logger.error(f"Pipeline failed: {pipeline_error}")
            logger.info("Saving partial checkpoint...")
            self._save_incremental_checkpoint(results, timeout_reached=False)
            raise pipeline_error

        # All stations processed - create final checkpoint
        final_path = self._finalize_checkpoint(results)

        # Build final output
        output = Stage2Output(
            metadata={
                "timestamp": datetime.utcnow().isoformat(),
                "source": "stage2_enrichment",
                "total_stations": len(stations),
                "successful": len(results["stations"]),
                "failed": len([f for f in results["failed_stations"] if f.get("permanent")]),
                "skipped_no_fandom": len(results.get("skipped_stations", []))
            },
            stations=results["stations"],
            failed_stations=results["failed_stations"],
            skipped_stations=results.get("skipped_stations", []),
            retry_queue=[]
        )

        if not self.validate_output(output):
            raise ValueError("Stage 2 output validation failed")

        failed_count = len([f for f in results["failed_stations"] if f.get("permanent")])
        skipped_count = len(results.get("skipped_stations", []))
        logger.success(f"Stage 2 complete: {len(output.stations)} successful, {failed_count} failed, {skipped_count} skipped")
        return output
    
    def _batch_stations(self, stations: List[Stage1Station]):
        """Yield stations in batches"""
        for i in range(0, len(stations), self.batch_size):
            yield stations[i:i + self.batch_size]
    
    def _extract_station(self, station: Stage1Station) -> Optional[Stage2Station]:
        """
        Extract enrichment data for a single station.
        
        Steps:
        1. Fetch Fandom page HTML
        2. Send to OpenRouter for extraction
        3. Parse response
        4. Return structured data
        
        Returns:
            Stage2Station with enrichment data, or None if station not on Fandom
        """
        # Fetch HTML
        html, station_not_found = self.scraper.fetch_page(station.fandom_url, station.official_name)
        
        if station_not_found:
            # Station doesn't exist on Fandom (likely new/unconstructed)
            logger.info(f"⏭️  Skipping {station.official_name}: Not on Fandom (likely new station not yet constructed)")
            return None
        
        if not html:
            raise Exception(f"Failed to fetch Fandom page: {station.fandom_url}")
        
        # Extract with LLM
        extraction_result = self.llm_client.extract_station_data(
            station_name=station.display_name,
            html_content=html
        )
        
        if not extraction_result:
            raise Exception("LLM extraction returned no data")
        
        # Build exits - directly from extraction result as specified
        exits = []
        for exit_data in extraction_result.get("exits", []):
            enriched_exit = EnrichedExit(
                exit_code=exit_data.get("exit_code", ""),
                platforms=exit_data.get("platforms"),
                accessibility=exit_data.get("accessibility"),
                bus_stops=exit_data.get("bus_stops"),
                nearby_landmarks=exit_data.get("nearby_landmarks")
            )
            exits.append(enriched_exit)
        
        # Build Stage2Station
        return Stage2Station(
            station_id=station.station_id,
            official_name=station.official_name,
            extraction_result="success",
            extraction_confidence=extraction_result.get("confidence", "medium"),
            exits=exits,
            accessibility_notes=extraction_result.get("accessibility_notes", []),
            extraction_timestamp=datetime.utcnow(),
            source_url=station.fandom_url
        )
    
    def _retry_failed_stations(self, results: dict, batch: List[Stage1Station]):
        """Retry failed stations from current batch with permanent failure tracking"""
        if not results["retry_queue"]:
            return

        # Find failed stations in current batch that need retry
        station_map = {s.station_id: s for s in batch}
        to_retry = [station_map[sid] for sid in results["retry_queue"] if sid in station_map]

        if not to_retry:
            return

        logger.subsection(f"Retrying {len(to_retry)} failed stations")

        for station in to_retry:
            success = False
            for attempt in range(self.max_retries):
                try:
                    time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                    enriched = self._extract_station(station)
                    results["stations"][station.station_id] = enriched
                    results["retry_queue"].remove(station.station_id)
                    # Remove from failed list
                    results["failed_stations"] = [
                        f for f in results["failed_stations"]
                        if f["station_id"] != station.station_id
                    ]
                    logger.item(f"✓ {station.official_name} (retry successful)")
                    success = True
                    break
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        logger.warning(f"✗ {station.official_name}: Retry failed after {self.max_retries} attempts")

            # Mark as permanent failure if all retries exhausted
            if not success:
                for failure in results["failed_stations"]:
                    if failure["station_id"] == station.station_id:
                        failure["permanent"] = True
                        failure["timestamp"] = datetime.utcnow().isoformat()
                        failure["error"] = f"Failed after {self.max_retries} retry attempts"
                # Remove from retry queue
                if station.station_id in results["retry_queue"]:
                    results["retry_queue"].remove(station.station_id)
    
    def validate_input(self, input_data: Stage1Output) -> bool:
        """Validate Stage 1 output"""
        try:
            assert len(input_data.stations) > 0, "No stations in input"
            for station in input_data.stations:
                assert station.fandom_url, f"Missing Fandom URL for {station.official_name}"
            return True
        except Exception as e:
            logger.error(f"Input validation failed: {e}")
            return False
    
    def validate_output(self, output_data: Stage2Output) -> bool:
        """Validate Stage 2 output"""
        try:
            assert len(output_data.stations) > 0, "No stations in output"
            return True
        except Exception as e:
            logger.error(f"Output validation failed: {e}")
            return False

    def _load_incremental_checkpoint(self) -> Optional[Stage2IncrementalOutput]:
        """Load incremental checkpoint if it exists"""
        checkpoint_path = os.path.join(self.output_dir, "stage2_incremental.json")
        backup_path = os.path.join(self.output_dir, "stage2_incremental.json.bak")
        enrichment_path = os.path.join(self.output_dir, "stage2_enrichment.json")
        
        def _convert_enrichment_to_incremental(data: dict, source: str) -> Stage2IncrementalOutput:
            """Convert enrichment/checkpoint data to Stage2IncrementalOutput format"""
            stations_dict = data.get("stations", {})
            failed_list = data.get("failed_stations", [])
            skipped_list = data.get("skipped_stations", [])
            processed_ids = data.get("processed_station_ids", [])
            
            # Deduplicate skipped_list by station_id (handles corrupted checkpoints)
            seen_skipped_ids = set()
            unique_skipped = []
            for s in skipped_list:
                sid = s.get("station_id")
                if sid and sid not in seen_skipped_ids:
                    seen_skipped_ids.add(sid)
                    unique_skipped.append(s)
            skipped_list = unique_skipped
            
            # Remove any skipped stations that are also in successful stations
            # (they should be reprocessed, not considered done)
            skipped_ids_in_success = seen_skipped_ids & set(stations_dict.keys())
            if skipped_ids_in_success:
                logger.warning(f"Found {len(skipped_ids_in_success)} stations in both skipped and successful - will reprocess them")
                for sid in skipped_ids_in_success:
                    del stations_dict[sid]
            
            # Rebuild processed_station_ids if empty but stations exist
            if not processed_ids:
                processed_ids = list(stations_dict.keys())
                processed_ids.extend([f["station_id"] for f in failed_list if isinstance(f, dict)])
                processed_ids.extend([s["station_id"] for s in skipped_list if isinstance(s, dict)])
                # Deduplicate processed_ids
                processed_ids = list(dict.fromkeys(processed_ids))
                if processed_ids:
                    logger.info(f"Rebuilt processed_station_ids ({len(processed_ids)} stations) from {source}")
            
            return Stage2IncrementalOutput(
                metadata=data.get("metadata", {}),
                stations=stations_dict,
                failed_stations=failed_list,
                skipped_stations=skipped_list,
                processed_station_ids=processed_ids
            )
        
        def _load_checkpoint_file(path: str, source: str, allow_rebuild: bool = True) -> Optional[Stage2IncrementalOutput]:
            """Load and validate a checkpoint file
            
            Args:
                path: Path to checkpoint file
                source: Description of source for logging
                allow_rebuild: If True, rebuild processed IDs when corrupted. If False, return None for corrupted checkpoints.
            """
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                checkpoint = Stage2IncrementalOutput.model_validate(data)
                
                # Check if checkpoint is corrupted (0 processed IDs but has stations)
                if not checkpoint.processed_station_ids and checkpoint.stations:
                    if not allow_rebuild:
                        logger.debug(f"Checkpoint at {source} has stations but 0 processed IDs - treating as corrupted")
                        return None
                    logger.warning(f"Checkpoint has {len(checkpoint.stations)} stations but 0 processed IDs - rebuilding")
                    return _convert_enrichment_to_incremental(data, source)
                
                return checkpoint
            except Exception as e:
                logger.debug(f"Failed to load {source}: {e}")
                return None
        
        # Try main checkpoint first
        if os.path.exists(checkpoint_path):
            checkpoint = _load_checkpoint_file(checkpoint_path, "main checkpoint", allow_rebuild=False)
            if checkpoint and checkpoint.processed_station_ids:
                return checkpoint
            # Main checkpoint is empty or corrupted, try backup (don't rebuild main yet, use backup instead)
            if os.path.exists(backup_path):
                backup_checkpoint = _load_checkpoint_file(backup_path, "backup checkpoint", allow_rebuild=True)
                if backup_checkpoint and backup_checkpoint.processed_station_ids:
                    logger.info(f"Loading checkpoint from backup: {backup_path}")
                    return backup_checkpoint
                # Backup is also corrupted, fall back to rebuilding from main
                logger.warning("Backup checkpoint also corrupted, rebuilding from main checkpoint")
            # No backup or backup also failed - rebuild from main checkpoint
            checkpoint = _load_checkpoint_file(checkpoint_path, "main checkpoint", allow_rebuild=True)
            if checkpoint and checkpoint.processed_station_ids:
                return checkpoint
        
        # Try backup if main doesn't exist
        elif os.path.exists(backup_path):
            checkpoint = _load_checkpoint_file(backup_path, "backup checkpoint")
            if checkpoint and checkpoint.processed_station_ids:
                logger.info(f"Loading checkpoint from backup: {backup_path}")
                return checkpoint
        
        # Try enrichment file as last resort
        if os.path.exists(enrichment_path):
            logger.info(f"Loading checkpoint from enrichment file: {enrichment_path}")
            try:
                with open(enrichment_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                checkpoint = _convert_enrichment_to_incremental(data, "enrichment file")
                if checkpoint.processed_station_ids:
                    return checkpoint
                logger.warning("Enrichment file has no processed stations")
            except Exception as e:
                logger.warning(f"Failed to load enrichment checkpoint: {e}")
        
        return None

    def _save_incremental_checkpoint(self, results: dict, timeout_reached: bool = False):
        """Save incremental checkpoint after each station"""
        checkpoint = Stage2IncrementalOutput(
            metadata={
                "timestamp": datetime.utcnow().isoformat(),
                "source": "stage2_incremental",
                "total_stations": len(self.all_stations),
                "completed_stations": len(results["stations"]),
                "failed_stations": len(results["failed_stations"]),
                "skipped_stations": len(results.get("skipped_stations", [])),
                "timeout_reached": timeout_reached
            },
            stations=results["stations"],
            failed_stations=results["failed_stations"],
            skipped_stations=results.get("skipped_stations", []),
            processed_station_ids=results["processed_station_ids"]
        )

        # Atomic write: write to temp, then rename
        temp_path = os.path.join(self.output_dir, "stage2_incremental.json.tmp")
        final_path = os.path.join(self.output_dir, "stage2_incremental.json")

        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint.model_dump(), f, indent=2, ensure_ascii=False, default=str)

        os.replace(temp_path, final_path)

    def _prompt_for_resume(self, checkpoint: Stage2IncrementalOutput) -> bool:
        """Prompt user whether to resume or restart"""
        completed = len(checkpoint.processed_station_ids)
        total = checkpoint.metadata.get("total_stations", 187)

        print(f"\n📂 Found existing checkpoint with {completed}/{total} stations processed.")
        print(f"   Last updated: {checkpoint.metadata.get('timestamp', 'unknown')}")

        if checkpoint.metadata.get("timeout_reached"):
            print("   ⏰ Previous run stopped due to time limit")

        response = input("\nResume from checkpoint? [Y/n]: ").strip().lower()
        return response in ('', 'y', 'yes')

    def _print_resume_message(self, completed: int, total: int):
        """Print friendly resume message"""
        logger.section("Daily Limit Reached")
        logger.info(f"✅ Progress saved: {completed}/{total} stations processed")
        logger.info(f"⏱️  Time limit: {self.daily_timeout_minutes} minutes")
        logger.info("")
        if self.stage1_output_path:
            logger.info("📋 To resume tomorrow, run:")
            logger.info(f"   uv run python scripts/run_stage2.py --stage1-output {self.stage1_output_path} --resume")
        logger.info("")
        logger.info(f"📁 Checkpoint saved: {os.path.join(self.output_dir, 'stage2_incremental.json')}")

    def _finalize_checkpoint(self, results: dict) -> str:
        """Convert incremental checkpoint to final format"""
        # Build Stage2Output from incremental results
        final_output = Stage2Output(
            metadata={
                "timestamp": datetime.utcnow().isoformat(),
                "source": "stage2_enrichment",
                "total_stations": len(self.all_stations),
                "successful": len(results["stations"]),
                "failed": len([f for f in results["failed_stations"] if f.get("permanent")])
            },
            stations=results["stations"],
            failed_stations=results["failed_stations"],
            retry_queue=[]  # Empty since we're done
        )

        # Save as final checkpoint
        final_path = os.path.join(self.output_dir, "stage2_enrichment.json")
        with open(final_path, 'w', encoding='utf-8') as f:
            json.dump(final_output.model_dump(), f, indent=2, ensure_ascii=False, default=str)

        # Optionally archive incremental checkpoint
        incremental_path = os.path.join(self.output_dir, "stage2_incremental.json")
        archive_path = os.path.join(self.output_dir, "stage2_incremental.json.bak")
        if os.path.exists(incremental_path):
            os.replace(incremental_path, archive_path)

        logger.success(f"✅ Stage 2 complete! Final checkpoint: {final_path}")
        return final_path

    def save_checkpoint(self, output: Stage2Output, output_dir: str) -> str:
        """Save Stage 2 output to checkpoint file"""
        os.makedirs(output_dir, exist_ok=True)

        output_dict = output.model_dump()

        filepath = os.path.join(output_dir, "stage2_enrichment.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False, default=str)

        logger.success(f"Stage 2 checkpoint saved: {filepath}")
        return filepath