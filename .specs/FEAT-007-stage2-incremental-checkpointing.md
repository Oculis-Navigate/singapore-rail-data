# Feature: Stage 2 Incremental Checkpointing & Resume

## Feature ID: FEAT-007
**Priority:** P1 (Critical for Free Tier Usage)
**Estimated Effort:** 2-3 hours
**Dependencies:** FEAT-003 (Stage 2 implementation)

---

## Context

### Problem
- 187 stations need enrichment via OpenRouter API
- Free OpenRouter tier: 50 requests/day limit
- Current implementation is all-or-nothing (no resume capability)
- Risk of losing progress after hitting daily limits or timeouts
- No visibility into processing progress

### Goal
Enable **incremental processing** of Stage 2 enrichment:
- Process stations over multiple days (4 days for 187 stations at 50/day)
- Resume from where we left off without reprocessing
- Gracefully handle daily limits with 45-minute timeout
- Clear progress visibility with progress bar
- Failed stations tracked and skipped on subsequent runs

---

## Requirements

### 1. Incremental Checkpoint File

Create `stage2_incremental.json` in the output directory:

```json
{
  "metadata": {
    "timestamp": "2026-02-09T10:00:00Z",
    "source": "stage2_incremental",
    "total_stations": 187,
    "completed_stations": 47,
    "failed_stations": 2,
    "timeout_reached": false
  },
  "stations": {
    "NS13": {
      "station_id": "NS13",
      "official_name": "YISHUN MRT STATION",
      "extraction_result": "success",
      "extraction_confidence": "high",
      "exits": [...],
      "accessibility_notes": [...],
      "extraction_timestamp": "2026-02-09T10:05:23Z",
      "source_url": "https://singapore-mrt-lines.fandom.com/wiki/Yishun_MRT_Station"
    }
  },
  "failed_stations": [
    {
      "station_id": "EW1",
      "error": "API timeout after 3 retries",
      "permanent": true,
      "timestamp": "2026-02-09T10:12:45Z"
    }
  ],
  "processed_station_ids": ["NS13", "NS14", "EW1", ...]
}
```

**Key fields:**
- `processed_station_ids`: List of all station IDs that have been attempted (success or failure)
- `timeout_reached`: Boolean flag to indicate if run stopped due to time limit
- `failed_stations[].permanent`: Boolean indicating station should be skipped on resume

### 2. Checkpoint After Every Station

Modify `Stage2Enrichment._extract_station()` and `execute()`:

```python
def _save_incremental_checkpoint(self, results: dict, timeout_reached: bool = False):
    """Save incremental checkpoint after each station"""
    checkpoint = Stage2IncrementalOutput(
        metadata={
            "timestamp": datetime.utcnow().isoformat(),
            "source": "stage2_incremental",
            "total_stations": len(self.all_stations),
            "completed_stations": len(results["stations"]),
            "failed_stations": len(results["failed_stations"]),
            "timeout_reached": timeout_reached
        },
        stations=results["stations"],
        failed_stations=results["failed_stations"],
        processed_station_ids=results["processed_station_ids"]
    )
    
    # Atomic write: write to temp, then rename
    temp_path = os.path.join(self.output_dir, "stage2_incremental.json.tmp")
    final_path = os.path.join(self.output_dir, "stage2_incremental.json")
    
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(checkpoint.model_dump(), f, indent=2, ensure_ascii=False, default=str)
    
    os.replace(temp_path, final_path)
```

### 3. Progress Bar with tqdm

Add tqdm progress bar to the execution loop:

```python
from tqdm import tqdm

def execute(self, input_data: Stage1Output) -> Stage2Output:
    # ... validation code ...
    
    # Check for existing checkpoint
    checkpoint = self._load_incremental_checkpoint()
    if checkpoint and self.resume_mode:
        processed_ids = set(checkpoint.processed_station_ids)
        logger.info(f"Resuming from checkpoint: {len(processed_ids)}/{len(stations)} stations already processed")
    else:
        processed_ids = set()
    
    # Filter stations to process
    stations_to_process = [s for s in stations if s.station_id not in processed_ids]
    
    # Setup progress bar
    pbar = tqdm(
        total=len(stations),
        initial=len(processed_ids),
        desc="Processing stations",
        unit="station",
        bar_format="{desc}: {n_fmt}/{total_fmt} [{percentage:3.0f}%] {elapsed}<{remaining}, {rate_fmt}"
    )
    
    start_time = time.time()
    timeout_seconds = self.daily_timeout_minutes * 60
    
    for station in stations_to_process:
        # Check timeout before processing
        elapsed = time.time() - start_time
        if elapsed >= timeout_seconds:
            logger.info(f"⏰ Daily limit timer reached ({self.daily_timeout_minutes} min)")
            self._save_incremental_checkpoint(results, timeout_reached=True)
            pbar.close()
            self._print_resume_message(len(processed_ids), len(stations))
            break
        
        try:
            enriched = self._extract_station(station)
            results["stations"][station.station_id] = enriched
            results["processed_station_ids"].append(station.station_id)
            logger.item(f"✓ {station.official_name}")
        except Exception as e:
            logger.warning(f"✗ {station.official_name}: {e}")
            results["failed_stations"].append({
                "station_id": station.station_id,
                "error": str(e),
                "permanent": True,  # Mark as permanent after retries fail
                "timestamp": datetime.utcnow().isoformat()
            })
            results["processed_station_ids"].append(station.station_id)
        
        # Save checkpoint after every station
        self._save_incremental_checkpoint(results)
        pbar.update(1)
    
    pbar.close()
```

**Progress bar features:**
- Shows `47/187 [25%]` format
- Displays elapsed time and ETA
- Updates after each station
- When resuming, starts from checkpointed count
- Shows processing rate (e.g., `45.2s/it`)

### 4. 45-Minute Timeout Handler

Add timeout configuration and handling:

```python
def __init__(self, config: dict, output_dir: str = "outputs/latest", resume_mode: bool = False):
    self.config = config
    self.stage_config = config.get('stages', {}).get('stage2_enrichment', {})
    self.batch_size = self.stage_config.get('batch_size', 8)
    self.delay_seconds = self.stage_config.get('delay_seconds', 2)
    self.max_retries = self.stage_config.get('max_retries', 3)
    self.retry_delay = self.stage_config.get('retry_delay_seconds', 5)
    self.daily_timeout_minutes = self.stage_config.get('daily_timeout_minutes', 45)  # NEW
    self.output_dir = output_dir
    self.resume_mode = resume_mode
    self.all_stations = []  # Store for checkpoint metadata
    
    # ... existing initialization ...

def _print_resume_message(self, completed: int, total: int):
    """Print friendly resume message"""
    logger.section("Daily Limit Reached")
    logger.info(f"✅ Progress saved: {completed}/{total} stations processed")
    logger.info(f"⏱️  Time limit: {self.daily_timeout_minutes} minutes")
    logger.info("")
    logger.info("📋 To resume tomorrow, run:")
    logger.info(f"   uv run python scripts/run_stage2.py --stage1-output {self.stage1_output_path} --resume")
    logger.info("")
    logger.info(f"📁 Checkpoint saved: {os.path.join(self.output_dir, 'stage2_incremental.json')}")
```

**Timeout behavior:**
- Check elapsed time before processing each station
- Never interrupt a station mid-processing
- Set `timeout_reached: true` in checkpoint metadata
- Exit with code 0 (graceful success, not error)
- Display clear message with resume instructions

### 5. Resume Capability

**Automatic detection and prompt:**

```python
def _load_incremental_checkpoint(self) -> Optional[Stage2IncrementalOutput]:
    """Load incremental checkpoint if it exists"""
    checkpoint_path = os.path.join(self.output_dir, "stage2_incremental.json")
    
    if not os.path.exists(checkpoint_path):
        return None
    
    try:
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return Stage2IncrementalOutput.model_validate(data)
    except Exception as e:
        logger.warning(f"Failed to load checkpoint: {e}. Starting fresh.")
        return None

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
```

**Validation on resume:**
- Verify checkpoint file is valid JSON
- Verify checkpoint matches expected schema
- Verify `processed_station_ids` length matches `len(stations) + len(failed_stations)`
- If validation fails: log warning and start fresh (don't crash)

**Skip logic:**
```python
# In execute() method
processed_ids = set(checkpoint.processed_station_ids) if checkpoint else set()

for station in stations:
    if station.station_id in processed_ids:
        logger.info(f"⏭️  Skipping {station.official_name} (already processed)")
        continue
    
    # Process station...
```

### 6. Failed Station Handling

Modify retry logic to mark permanent failures:

```python
def _retry_failed_stations(self, results: dict, batch: List[Stage1Station]):
    """Retry failed stations from current batch"""
    if not results["retry_queue"]:
        return
    
    logger.subsection(f"Retrying {len(results['retry_queue'])} failed stations")
    
    station_map = {s.station_id: s for s in batch}
    to_retry = [station_map[sid] for sid in results["retry_queue"] if sid in station_map]
    
    for station in to_retry:
        success = False
        for attempt in range(self.max_retries):
            try:
                time.sleep(self.retry_delay * (2 ** attempt))
                enriched = self._extract_station(station)
                results["stations"][station.station_id] = enriched
                results["retry_queue"].remove(station.station_id)
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
```

**On resume:**
- Check `permanent` flag in failed_stations
- Skip stations with `permanent: true`
- Log: `⏭️  Skipping {name} (permanently failed)`

### 7. Final Checkpoint Creation

When all stations complete successfully:

```python
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
```

### 8. Command Interface Updates

Update `scripts/run_stage2.py`:

```python
def main():
    parser = argparse.ArgumentParser(description='Run Stage 2: Enrichment Extraction')
    parser.add_argument('--stage1-output', required=True, help='Path to Stage 1 output JSON')
    parser.add_argument('--output-dir', default='outputs/latest', help='Output directory')
    parser.add_argument('--config', default='config/pipeline.yaml', help='Config file path')
    parser.add_argument('--resume', action='store_true', help='Resume from existing checkpoint')
    parser.add_argument('--restart', action='store_true', help='Restart and ignore existing checkpoint')
    args = parser.parse_args()
    
    # Load config and Stage 1 output
    config = load_config(args.config)
    stage1_output = load_stage1_output(args.stage1_output)
    
    # Check for existing checkpoint
    checkpoint_path = os.path.join(args.output_dir, "stage2_incremental.json")
    resume_mode = False
    
    if os.path.exists(checkpoint_path) and not args.restart:
        if args.resume:
            resume_mode = True
            logger.info("Resuming from checkpoint (--resume flag provided)")
        else:
            # Prompt user
            from src.pipelines.stage2_enrichment import Stage2Enrichment
            stage = Stage2Enrichment(config, args.output_dir, resume_mode=False)
            checkpoint = stage._load_incremental_checkpoint()
            if checkpoint and stage._prompt_for_resume(checkpoint):
                resume_mode = True
    
    # Initialize and run
    stage = Stage2Enrichment(config, args.output_dir, resume_mode)
    stage.stage1_output_path = args.stage1_output  # Store for resume message
    output = stage.execute(stage1_output)
    
    # Save final checkpoint
    checkpoint_path = stage.save_checkpoint(output, args.output_dir)
    
    # Print summary
    logger.result("Stage 2 Complete")
    logger.stats("Successful", str(len(output.stations)))
    logger.stats("Failed", str(len(output.failed_stations)))
    logger.stats("Checkpoint", checkpoint_path)
```

---

## Configuration Updates

Add to `config/pipeline.yaml`:

```yaml
stages:
  stage2_enrichment:
    enabled: true
    batch_size: 8
    delay_seconds: 2
    max_retries: 3
    retry_delay_seconds: 5
    daily_timeout_minutes: 45  # NEW: Stop after 45 minutes
    checkpoint_interval: 1     # NEW: Save after every N stations (1 = every station)
```

---

## New Data Schema

Add to `src/contracts/schemas.py`:

```python
class Stage2IncrementalOutput(BaseModel):
    """Incremental checkpoint for Stage 2 (allows resume)"""
    metadata: Dict[str, Any] = Field(..., description="Checkpoint metadata")
    stations: Dict[str, Stage2Station] = Field(default_factory=dict, description="Successfully processed stations")
    failed_stations: List[Dict[str, Any]] = Field(default_factory=list, description="Failed station records")
    processed_station_ids: List[str] = Field(default_factory=list, description="All processed station IDs (success + failed)")
```

---

## Success Criteria

1. [ ] Incremental checkpoint saved to `stage2_incremental.json` after every station
2. [ ] Progress bar shows `n/187` stations with ETA using tqdm
3. [ ] At 45 minutes, gracefully saves checkpoint and exits with resume message
4. [ ] `--resume` flag skips already processed stations
5. [ ] Without flag, prompts user when checkpoint detected (Y/n)
6. [ ] Failed stations marked `permanent: true` and skipped on resume
7. [ ] Simple validation ensures checkpoint integrity before resuming
8. [ ] Final `stage2_enrichment.json` created after all 187 stations complete
9. [ ] Atomic writes prevent checkpoint corruption
10. [ ] Test: Run 5 stations, Ctrl+C, resume - should start at #6
11. [ ] Test: 45-minute timeout triggers and saves progress correctly
12. [ ] Test: Permanently failed stations are skipped on resume

---

## Dependencies

**Requires:**
- FEAT-003: Stage 2 - Enrichment Extraction Pipeline (existing implementation)
- tqdm package (add to dependencies)

**Required By:**
- None (this is a usability enhancement)

---

## Implementation Notes

### Dependencies to Add
```bash
uv add tqdm
```

### Key Design Decisions

1. **Atomic Writes**: Use temp file + rename pattern to prevent corruption if process crashes mid-write
2. **Simple Validation**: Just verify JSON is valid and has expected fields - don't validate every station ID matches
3. **User Experience**: Clear messages showing progress and resume instructions
4. **Safety First**: Never lose progress - checkpoint after every single station
5. **Flexibility**: Support both `--resume` flag and interactive prompt

### Testing Strategy

1. **Happy Path**: Process all 187 stations in one run (if using paid tier)
2. **Resume Flow**: Process 10, stop, resume, verify starts at 11
3. **Timeout**: Set timeout to 2 minutes, verify it stops gracefully
4. **Failed Stations**: Force a failure, verify it's marked permanent and skipped on resume
5. **Corruption Recovery**: Corrupt checkpoint file, verify it starts fresh with warning

---

## User Workflow Example

**Day 1 - Starting Fresh:**
```bash
$ uv run python scripts/run_stage2.py --stage1-output outputs/latest/stage1_deterministic.json

📂 Found existing checkpoint with 0/187 stations processed.

Resume from checkpoint? [Y/n]: n
Starting fresh...

Processing stations:  47/187 [25%] 12:34<33:12, 45.2s/it
⏰ Daily limit timer reached (45 min). Saved 47/187 stations.

📋 To resume tomorrow, run:
   uv run python scripts/run_stage2.py --stage1-output outputs/latest/stage1_deterministic.json --resume

📁 Checkpoint saved: outputs/latest/stage2_incremental.json
```

**Day 2 - Resuming:**
```bash
$ uv run python scripts/run_stage2.py --stage1-output outputs/latest/stage1_deterministic.json

📂 Found existing checkpoint with 47/187 stations processed.
   Last updated: 2026-02-09T10:45:00Z
   ⏰ Previous run stopped due to time limit

Resume from checkpoint? [Y/n]: Y
Resuming from checkpoint...

Processing stations:  47/187 [25%] 00:00<35:45, 45.2s/it
⏭️  Skipping YISHUN MRT STATION (already processed)
⏭️  Skipping KHATIB MRT STATION (already processed)
...
⏰ Daily limit timer reached (45 min). Saved 94/187 stations.
```

**Day 4 - Completion:**
```bash
$ uv run python scripts/run_stage2.py --resume

Processing stations:  187/187 [100%] 12:34<00:00, 45.2s/it
✅ Stage 2 complete! All 187 stations processed.
📄 Final checkpoint saved: outputs/latest/stage2_enrichment.json
```

---

## Known Limitations

1. **Station Order**: Stations are processed in the order provided by Stage 1. If Stage 1 output changes order between runs, resume may behave unexpectedly.
2. **No Parallel Processing**: Checkpoint system assumes single-process execution. Don't run multiple instances simultaneously.
3. **Disk Space**: Incremental checkpoint (~500KB) + final checkpoint (~500KB) = ~1MB per run. Negligible but worth noting.
4. **API Costs Still Apply**: Each station still costs API credits. This feature just enables spreading costs over multiple days.

---

## Future Enhancements (Out of Scope)

- Parallel processing with thread-safe checkpoints
- Retry permanently failed stations with different parameters
- Compress checkpoint files for long-term storage
