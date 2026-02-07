# Feature: Stage 2 - Enrichment Extraction Pipeline

## Feature ID: FEAT-003
**Priority:** P1 (Core Pipeline Stage)
**Estimated Effort:** 3-4 hours
**Dependencies:** FEAT-001, FEAT-002

---

## Context

### Current State
- `enrichment_scraper.py` exists but is standalone and disconnected from the pipeline
- It doesn't use station data from Stage 1 to guide extraction
- Uses OpenRouter LLM to extract from Fandom wiki pages
- Batch extraction files exist in `tmp/extraction_scripts/` from initial data gathering
- No retry logic for failed extractions
- No structured output format matching the data contract

### Goal
Create a robust Stage 2 pipeline that:
1. Consumes Stage 1 output to get the station list and Fandom URLs
2. Extracts enrichment data from Fandom wiki using OpenRouter LLM
3. Implements retry logic with exponential backoff
4. Processes stations in configurable batches
5. Handles failures gracefully with a retry queue
6. Produces structured Stage2Output following the data contract

---

## Requirements

### 1. Stage 2 Implementation (src/pipelines/stage2_enrichment.py)

Create a `Stage2Enrichment` class:

```python
import time
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from src.contracts.interfaces import PipelineStage
from src.contracts.schemas import (
    Stage1Output, Stage2Output, Stage2Station, EnrichedExit,
    Platform, BusStop, Stage1Station
)
from src.utils.logger import logger

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
        
        # Initialize OpenRouter client
        self.llm_client = OpenRouterClient(config)
        self.scraper = FandomScraper()
    
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
        
        # Build Stage2Station
        return Stage2Station(
            station_id=station.station_id,
            official_name=station.official_name,
            extraction_result="success",
            extraction_confidence=extraction_result.get("confidence", "medium"),
            exits=extraction_result.get("exits", []),
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
    
    def save_checkpoint(self, output: Stage2Output, output_dir: str):
        """Save Stage 2 output to checkpoint file"""
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        
        output_dict = output.model_dump()
        
        filepath = os.path.join(output_dir, "stage2_enrichment.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False, default=str)
        
        logger.success(f"Stage 2 checkpoint saved: {filepath}")
        return filepath
```

### 2. OpenRouter Client (src/pipelines/openrouter_client.py)

Create a dedicated OpenRouter client:

```python
import os
import re
import json
import requests
from typing import Optional, Dict, Any
from src.utils.logger import logger

class OpenRouterClient:
    """Client for OpenRouter API to extract station data from HTML"""
    
    def __init__(self, config: dict):
        api_config = config.get('apis', {}).get('openrouter', {})
        self.api_url = api_config.get('base_url', 'https://openrouter.ai/api/v1') + "/chat/completions"
        self.model = api_config.get('model', 'anthropic/claude-3.5-sonnet')
        self.timeout = api_config.get('timeout', 120)
        self.max_tokens = api_config.get('max_tokens', 4000)
        self.temperature = api_config.get('temperature', 0.1)
        
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/yourusername/mrt-data",
            "X-Title": "MRT Data Pipeline"
        }
    
    def extract_station_data(self, station_name: str, html_content: str) -> Optional[Dict]:
        """
        Send HTML to OpenRouter and extract structured station data.
        
        Returns dict with:
        - confidence: "high", "medium", or "low"
        - exits: list of exit objects
        - accessibility_notes: list of strings
        """
        system_prompt = self._get_system_prompt()
        user_prompt = self._get_user_prompt(station_name, html_content)
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # Clean up response
            content = self._clean_response(content)
            
            # Parse JSON
            data = json.loads(content)
            
            # Validate required fields
            if "exits" not in data:
                raise ValueError("Response missing 'exits' field")
            
            return {
                "confidence": data.get("extraction_confidence", "medium"),
                "exits": data.get("exits", []),
                "accessibility_notes": data.get("accessibility_notes", [])
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return None
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for LLM"""
        return """You are a data extraction specialist. Extract structured information about Singapore MRT stations from Fandom wiki pages.

Extract in JSON format:
1. Station code (e.g., "NS13")
2. Lines served (e.g., ["NSL"])
3. For each exit:
   - Exit code (e.g., "A", "B", "1", "2")
   - Platforms/directions with station codes (e.g., Platform A → NS1)
   - Accessibility features
   - Bus stops with 5-digit codes
   - Nearby landmarks

CRITICAL RULES:
- Use STATION CODES (NS1, CC29) not names
- Bus stop codes must be exactly 5 digits
- Note ANY accessibility limitations
- Return ONLY valid JSON, no markdown

Expected format:
{
    "station_code": "NS13",
    "lines": ["NSL"],
    "exits": [
        {
            "exit_code": "A",
            "platforms": [{"platform_code": "A", "towards_code": "NS1", "line_code": "NS"}],
            "accessibility": ["wheelchair_accessible", "lift"],
            "bus_stops": [{"code": "12345", "services": ["123"]}],
            "nearby_landmarks": ["Landmark Name"]
        }
    ],
    "accessibility_notes": ["All exits accessible"],
    "extraction_confidence": "high"
}"""
    
    def _get_user_prompt(self, station_name: str, html_content: str) -> str:
        """Get user prompt with HTML content"""
        # Truncate HTML to avoid token limits
        truncated_html = html_content[:15000]
        
        return f"""Extract data for: {station_name}

HTML Content:
{truncated_html}

Return only the JSON object."""
    
    def _clean_response(self, content: str) -> str:
        """Clean up LLM response"""
        # Remove markdown code blocks
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        return content.strip()
```

### 3. Fandom Scraper (src/pipelines/fandom_scraper.py)

Create or reuse Fandom scraper:

```python
import requests
from typing import Optional
from src.utils.logger import logger

class FandomScraper:
    """Scraper for Singapore MRT Fandom pages"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
    
    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch HTML content from Fandom page"""
        try:
            logger.info(f"Fetching: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None
```

### 4. Execution Script (scripts/run_stage2.py)

```python
#!/usr/bin/env python3
"""
Standalone script to run Stage 2: Enrichment Extraction

Usage:
    python scripts/run_stage2.py --stage1-output outputs/2026-02-07/stage1_deterministic.json
    python scripts/run_stage2.py --output-dir outputs/2026-02-07
"""

import argparse
import json
import os
import sys
import yaml
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from contracts.schemas import Stage1Output
from pipelines.stage2_enrichment import Stage2Enrichment
from utils.logger import logger

def main():
    parser = argparse.ArgumentParser(description='Run Stage 2: Enrichment Extraction')
    parser.add_argument('--stage1-output', required=True, help='Path to Stage 1 output JSON')
    parser.add_argument('--output-dir', default='outputs/latest', help='Output directory')
    parser.add_argument('--config', default='config/pipeline.yaml', help='Config file path')
    args = parser.parse_args()
    
    # Load config
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)
    
    # Load Stage 1 output
    with open(args.stage1_output, 'r') as f:
        stage1_data = json.load(f)
    
    stage1_output = Stage1Output.model_validate(stage1_data)
    
    # Load environment
    load_dotenv()
    
    # Run stage
    stage = Stage2Enrichment(config)
    output = stage.execute(stage1_output)
    
    # Save checkpoint
    checkpoint_path = stage.save_checkpoint(output, args.output_dir)
    
    # Print summary
    logger.result("Stage 2 Complete")
    logger.stats("Successful", str(len(output.stations)))
    logger.stats("Failed", str(len(output.failed_stations)))
    logger.stats("Checkpoint", checkpoint_path)

if __name__ == "__main__":
    main()
```

---

## Success Criteria

1. [ ] `Stage2Enrichment` class implemented in `src/pipelines/stage2_enrichment.py`
2. [ ] `OpenRouterClient` implemented in `src/pipelines/openrouter_client.py`
3. [ ] `FandomScraper` implemented/reused in `src/pipelines/fandom_scraper.py`
4. [ ] Class implements `PipelineStage` interface
5. [ ] Batch processing with configurable size
6. [ ] Retry logic with exponential backoff for failed stations
7. [ ] Respects delay between API calls (rate limiting)
8. [ ] Validates input/output against Pydantic schemas
9. [ ] Saves checkpoint to JSON
10. [ ] `python scripts/run_stage2.py --stage1-output ...` runs successfully
11. [ ] Handles API errors gracefully (404, 500, timeouts)

---

## Configuration Requirements

Ensure `config/pipeline.yaml` has:

```yaml
stages:
  stage2_enrichment:
    enabled: true
    batch_size: 8
    delay_seconds: 2
    max_retries: 3
    retry_delay_seconds: 5
    sources:
      - fandom_wiki
      - openrouter_llm

apis:
  openrouter:
    base_url: "https://openrouter.ai/api/v1"
    model: "anthropic/claude-3.5-sonnet"
    timeout: 120
    max_tokens: 4000
    temperature: 0.1
```

---

## Environment Variables Required

```bash
OPENROUTER_API_KEY=your_api_key_here
```

---

## Dependencies

**Requires:**
- FEAT-001: Project Restructure & Data Contracts
- FEAT-002: Stage 1 - Deterministic Data Ingestion

**Required By:**
- FEAT-004: Stage 3 - Data Merging & Validation
- FEAT-005: Pipeline Orchestrator & Configuration

---

## Known Limitations

1. **API Rate Limits**: OpenRouter has rate limits; the 2-second delay helps but large extractions may take ~30-40 minutes for 187 stations
2. **Token Limits**: HTML is truncated to 15000 chars to fit in context window
3. **LLM Consistency**: Results may vary slightly between runs; extraction_confidence field helps identify uncertain data
4. **Cost**: OpenRouter API calls cost money; ~187 stations × ~$0.01-0.02 = ~$2-4 per full run

These are acceptable for quarterly runs with 187 stations.
