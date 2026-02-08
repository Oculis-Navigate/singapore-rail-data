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
from ..contracts.interfaces import PipelineStage
from ..contracts.schemas import (
    Stage1Output, Stage2Output, Stage2Station, EnrichedExit,
    Platform, BusStop, Stage1Station
)
from ..utils.logger import logger
from .openrouter_client import OpenRouterClient
from .fandom_scraper import FandomScraper


class Stage2Enrichment(PipelineStage):
    """
    Stage 2: Extract enrichment data from Fandom wiki using OpenRouter LLM.
    
    Input: Stage1Output (stations with Fandom URLs)
    Output: Stage2Output (enrichment data for each station)
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.stage_config = config.get('stages', {}).get('stage2_enrichment', {})
        self.batch_size = self.stage_config.get('batch_size', 8)
        self.delay_seconds = self.stage_config.get('delay_seconds', 2)
        self.max_retries = self.stage_config.get('max_retries', 3)
        self.retry_delay = self.stage_config.get('retry_delay_seconds', 5)
        
        # Initialize OpenRouter client and scraper
        self.llm_client = OpenRouterClient(config)
        self.scraper = FandomScraper(config)
    
    @property
    def stage_name(self) -> str:
        return "stage2_enrichment"
    
    def execute(self, input_data: Stage1Output) -> Stage2Output:
        """
        Execute Stage 2 enrichment pipeline.
        
        Steps:
        1. Validate input
        2. Process stations in batches
        3. For each station: fetch HTML, extract with LLM
        4. Retry failed stations
        5. Compile results into Stage2Output
        6. Save partial checkpoint on failures
        """
        logger.section("Stage 2: Enrichment Data Extraction")
        
        if not self.validate_input(input_data):
            raise ValueError("Invalid input for Stage 2")
        
        stations = input_data.stations
        results = {
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "source": "stage2_enrichment",
                "total_stations": len(stations),
                "batch_size": self.batch_size
            },
            "stations": {},
            "failed_stations": [],
            "retry_queue": []
        }
        
        # Process in batches
        total_batches = (len(stations) + self.batch_size - 1) // self.batch_size
        
        try:
            for batch_idx, batch in enumerate(self._batch_stations(stations), 1):
                logger.subsection(f"Processing Batch {batch_idx}/{total_batches}")
                
                for station in batch:
                    try:
                        enriched = self._extract_station(station)
                        results["stations"][station.station_id] = enriched
                        logger.item(f"✓ {station.official_name}")
                    except Exception as e:
                        logger.warning(f"✗ {station.official_name}: {e}")
                        results["failed_stations"].append({
                            "station_id": station.station_id,
                            "error": str(e),
                            "retryable": True
                        })
                        results["retry_queue"].append(station.station_id)
                
                # Retry failed stations in this batch
                if results["retry_queue"]:
                    self._retry_failed_stations(results, batch)
                
                # Delay between batches
                if batch_idx < total_batches:
                    time.sleep(self.delay_seconds)
                    
        except Exception as pipeline_error:
            # Save partial checkpoint on pipeline failure
            logger.error(f"Pipeline failed: {pipeline_error}")
            logger.info("Saving partial checkpoint...")
            
            try:
                partial_output = Stage2Output(
                    metadata=results["metadata"],
                    stations=results["stations"],
                    failed_stations=results["failed_stations"],
                    retry_queue=results["retry_queue"]
                )
                partial_output.metadata["error"] = str(pipeline_error)
                partial_output.metadata["successful"] = len(results["stations"])
                partial_output.metadata["failed"] = len(results["failed_stations"])
                
                checkpoint_path = self.save_checkpoint(partial_output, "outputs/partial")
                logger.success(f"Partial checkpoint saved: {checkpoint_path}")
            except Exception as checkpoint_error:
                logger.error(f"Failed to save partial checkpoint: {checkpoint_error}")
            
            raise pipeline_error
        
        # Build final output
        output = Stage2Output(
            metadata=results["metadata"],
            stations=results["stations"],
            failed_stations=results["failed_stations"],
            retry_queue=results["retry_queue"]
        )
        
        # Update metadata with final counts
        output.metadata["successful"] = len(output.stations)
        output.metadata["failed"] = len(output.failed_stations)
        
        if not self.validate_output(output):
            raise ValueError("Stage 2 output validation failed")
        
        logger.success(f"Stage 2 complete: {len(output.stations)} successful, {len(output.failed_stations)} failed")
        return output
    
    def _batch_stations(self, stations: List[Stage1Station]):
        """Yield stations in batches"""
        for i in range(0, len(stations), self.batch_size):
            yield stations[i:i + self.batch_size]
    
    def _extract_station(self, station: Stage1Station) -> Stage2Station:
        """
        Extract enrichment data for a single station.
        
        Steps:
        1. Fetch Fandom page HTML
        2. Send to OpenRouter for extraction
        3. Parse response
        4. Return structured data
        """
        # Fetch HTML
        html = self.scraper.fetch_page(station.fandom_url)
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
        """Retry failed stations from current batch"""
        if not results["retry_queue"]:
            return
        
        logger.subsection(f"Retrying {len(results['retry_queue'])} failed stations")
        
        # Find failed stations in current batch
        station_map = {s.station_id: s for s in batch}
        to_retry = [station_map[sid] for sid in results["retry_queue"] if sid in station_map]
        
        for station in to_retry:
            for attempt in range(self.max_retries):
                try:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                    enriched = self._extract_station(station)
                    results["stations"][station.station_id] = enriched
                    results["retry_queue"].remove(station.station_id)
                    # Remove from failed list
                    results["failed_stations"] = [
                        f for f in results["failed_stations"] 
                        if f["station_id"] != station.station_id
                    ]
                    logger.item(f"✓ {station.official_name} (retry successful)")
                    break
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        logger.warning(f"✗ {station.official_name}: Retry failed after {self.max_retries} attempts")
    
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
    
    def save_checkpoint(self, output: Stage2Output, output_dir: str) -> str:
        """Save Stage 2 output to checkpoint file"""
        os.makedirs(output_dir, exist_ok=True)
        
        output_dict = output.model_dump()
        
        filepath = os.path.join(output_dir, "stage2_enrichment.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False, default=str)
        
        logger.success(f"Stage 2 checkpoint saved: {filepath}")
        return filepath