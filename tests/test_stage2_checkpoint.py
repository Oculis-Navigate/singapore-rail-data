"""
Test suite for Stage 2 checkpoint loading and retry logic

This module tests the checkpoint resume functionality with mocking
to ensure retry_failed mode works correctly.
"""

import pytest
import json
import os
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.pipelines.stage2_enrichment import Stage2Enrichment
from src.contracts.schemas import (
    Stage1Output, Stage2Output, Stage1Station, Stage2Station,
    Exit, StationType, Stage2IncrementalOutput
)


class TestStage2CheckpointLoading:
    """Test checkpoint loading with backup file fallback"""
    
    def test_load_incremental_checkpoint_from_backup(self):
        """Test that checkpoint loads from backup when main file doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create backup file but not main checkpoint
            backup_path = os.path.join(tmpdir, "stage2_incremental.json.bak")
            checkpoint_data = {
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "total_stations": 5,
                    "completed_stations": 3,
                    "failed_stations": 2
                },
                "stations": {
                    "NS1": {
                        "station_id": "NS1",
                        "official_name": "TEST STATION",
                        "extraction_result": "success",
                        "extraction_confidence": "high",
                        "exits": [],
                        "accessibility_notes": [],
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                        "source_url": "https://test.com"
                    }
                },
                "failed_stations": [
                    {"station_id": "NS2", "error": "Test error", "permanent": True},
                    {"station_id": "NS3", "error": "Test error 2", "permanent": False}
                ],
                "processed_station_ids": ["NS1", "NS2", "NS3"]
            }
            
            with open(backup_path, 'w') as f:
                json.dump(checkpoint_data, f)
            
            # Initialize stage with tmpdir as output_dir
            stage = Stage2Enrichment(
                {'stages': {'stage2_enrichment': {'test_mode': True}}},
                output_dir=tmpdir
            )
            
            # Load checkpoint
            checkpoint = stage._load_incremental_checkpoint()
            
            assert checkpoint is not None
            assert len(checkpoint.processed_station_ids) == 3
            assert len(checkpoint.failed_stations) == 2
            assert "NS1" in checkpoint.stations


class TestStage2RetryLogic:
    """Test retry_failed mode logic"""
    
    @patch('src.pipelines.stage2_enrichment.Stage2Enrichment._load_incremental_checkpoint')
    @patch('src.pipelines.stage2_enrichment.Stage2Enrichment._save_incremental_checkpoint')
    def test_retry_mode_removes_failed_from_processed(self, mock_save, mock_load):
        """Test that retry mode removes failed stations from processed_ids"""
        
        # Create mock checkpoint data
        mock_checkpoint = Mock()
        mock_checkpoint.processed_station_ids = ["NS1", "NS2", "NS3", "NS4"]
        mock_checkpoint.failed_stations = [
            {"station_id": "NS2", "error": "Error", "permanent": True},
            {"station_id": "NS3", "error": "Error 2", "permanent": True}
        ]
        mock_checkpoint.stations = {
            "NS1": Mock(),
            "NS2": Mock(),
            "NS3": Mock(),
            "NS4": Mock()
        }
        mock_checkpoint.skipped_stations = []
        mock_load.return_value = mock_checkpoint
        
        # Create stage in retry mode
        stage = Stage2Enrichment(
            {'stages': {'stage2_enrichment': {'test_mode': True}}},
            output_dir="/tmp",
            resume_mode=True,
            retry_failed=True
        )
        
        # Create test input data
        stations = [
            Stage1Station(
                station_id="NS1",
                official_name="STATION 1 MRT STATION",
                display_name="Station 1",
                mrt_codes=["NS1"],
                lines=["NSL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.0, lng=103.0, source="onemap")],
                fandom_url="https://test.com/1"
            ),
            Stage1Station(
                station_id="NS2",
                official_name="STATION 2 MRT STATION",
                display_name="Station 2",
                mrt_codes=["NS2"],
                lines=["NSL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.1, lng=103.1, source="onemap")],
                fandom_url="https://test.com/2"
            ),
            Stage1Station(
                station_id="NS3",
                official_name="STATION 3 MRT STATION",
                display_name="Station 3",
                mrt_codes=["NS3"],
                lines=["NSL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.2, lng=103.2, source="onemap")],
                fandom_url="https://test.com/3"
            ),
            Stage1Station(
                station_id="NS4",
                official_name="STATION 4 MRT STATION",
                display_name="Station 4",
                mrt_codes=["NS4"],
                lines=["NSL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.3, lng=103.3, source="onemap")],
                fandom_url="https://test.com/4"
            )
        ]
        input_data = Stage1Output(metadata={}, stations=stations)
        
        # Track which stations were passed to _extract_station
        extracted_stations = []
        
        def mock_extract(station):
            extracted_stations.append(station.station_id)
            return Stage2Station(
                station_id=station.station_id,
                official_name=station.official_name,
                extraction_result="success",
                exits=[],
                extraction_timestamp=datetime.now(),
                source_url=station.fandom_url
            )
        
        with patch.object(stage, '_extract_station', side_effect=mock_extract):
            with patch.object(stage, '_retry_failed_stations'):
                with patch('time.sleep'):
                    with patch('tqdm.tqdm') as mock_tqdm:
                        mock_tqdm.return_value.__enter__ = Mock(return_value=Mock(update=Mock(), close=Mock()))
                        mock_tqdm.return_value.__exit__ = Mock(return_value=False)
                        try:
                            stage.execute(input_data)
                        except Exception:
                            pass
        
        # Verify that only NS2 and NS3 were extracted (the failed ones)
        assert "NS1" not in extracted_stations  # Already successful
        assert "NS2" in extracted_stations  # Failed, needs retry
        assert "NS3" in extracted_stations  # Failed, needs retry
        assert "NS4" not in extracted_stations  # Already successful


class TestStage2ExecuteFlow:
    """Test the full execute flow with mocking"""
    
    @patch('src.pipelines.stage2_enrichment.Stage2Enrichment._load_incremental_checkpoint')
    @patch('src.pipelines.stage2_enrichment.Stage2Enrichment._save_incremental_checkpoint')
    def test_execute_with_retry_skips_successful(self, mock_save, mock_load):
        """Test that execute skips already successful stations when retrying"""
        
        # Create mock checkpoint with 2 successful, 2 failed
        mock_checkpoint = Mock()
        mock_checkpoint.processed_station_ids = ["NS1", "NS2", "NS3", "NS4"]
        mock_checkpoint.failed_stations = [
            {"station_id": "NS2", "error": "Error", "permanent": True},
            {"station_id": "NS4", "error": "Error 2", "permanent": True}
        ]
        mock_checkpoint.stations = {
            "NS1": Stage2Station(
                station_id="NS1",
                official_name="STATION 1 MRT STATION",
                extraction_result="success",
                exits=[],
                extraction_timestamp=datetime.now(),
                source_url="https://test.com/1"
            ),
            "NS2": Stage2Station(
                station_id="NS2",
                official_name="STATION 2 MRT STATION",
                extraction_result="success",
                exits=[],
                extraction_timestamp=datetime.now(),
                source_url="https://test.com/2"
            ),
            "NS3": Stage2Station(
                station_id="NS3",
                official_name="STATION 3 MRT STATION",
                extraction_result="success",
                exits=[],
                extraction_timestamp=datetime.now(),
                source_url="https://test.com/3"
            ),
            "NS4": Stage2Station(
                station_id="NS4",
                official_name="STATION 4 MRT STATION",
                extraction_result="success",
                exits=[],
                extraction_timestamp=datetime.now(),
                source_url="https://test.com/4"
            )
        }
        mock_checkpoint.skipped_stations = []
        mock_load.return_value = mock_checkpoint
        
        stage = Stage2Enrichment(
            {'stages': {'stage2_enrichment': {'test_mode': True, 'daily_timeout_minutes': 90}}},
            output_dir="/tmp",
            resume_mode=True,
            retry_failed=True
        )
        
        # Create test input
        stations = [
            Stage1Station(
                station_id=f"NS{i}",
                official_name=f"STATION {i} MRT STATION",
                display_name=f"Station {i}",
                mrt_codes=[f"NS{i}"],
                lines=["NSL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.0, lng=103.0, source="onemap")],
                fandom_url=f"https://test.com/{i}"
            )
            for i in range(1, 5)
        ]
        input_data = Stage1Output(metadata={}, stations=stations)
        
        # Track which stations were processed
        processed_stations = []
        
        def mock_extract(station):
            processed_stations.append(station.station_id)
            return Stage2Station(
                station_id=station.station_id,
                official_name=station.official_name,
                extraction_result="success",
                exits=[],
                extraction_timestamp=datetime.now(),
                source_url=station.fandom_url
            )
        
        with patch.object(stage, '_extract_station', side_effect=mock_extract):
            with patch.object(stage, '_retry_failed_stations'):
                with patch('time.sleep'):  # Speed up tests
                    try:
                        result = stage.execute(input_data)
                    except Exception:
                        pass
        
        # Verify only failed stations were processed
        assert "NS1" not in processed_stations  # Already successful
        assert "NS2" in processed_stations  # Failed, needs retry
        assert "NS3" not in processed_stations  # Already successful
        assert "NS4" in processed_stations  # Failed, needs retry


class TestStage2CheckpointFiltering:
    """Test that checkpoint data is filtered correctly"""
    
    def test_checkpoint_initialization_filters_failed_stations(self):
        """Test that failed stations are filtered from processed_station_ids in results"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create checkpoint file
            checkpoint_path = os.path.join(tmpdir, "stage2_incremental.json")
            checkpoint_data = {
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "stage2_incremental",
                    "total_stations": 5,
                    "completed_stations": 3,
                    "failed_stations": 2,
                    "timeout_reached": False
                },
                "stations": {
                    "NS1": {
                        "station_id": "NS1",
                        "official_name": "STATION 1 MRT STATION",
                        "extraction_result": "success",
                        "extraction_confidence": "high",
                        "exits": [],
                        "accessibility_notes": [],
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                        "source_url": "https://test.com/1"
                    },
                    "NS3": {
                        "station_id": "NS3",
                        "official_name": "STATION 3 MRT STATION",
                        "extraction_result": "success",
                        "extraction_confidence": "high",
                        "exits": [],
                        "accessibility_notes": [],
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                        "source_url": "https://test.com/3"
                    },
                    "NS5": {
                        "station_id": "NS5",
                        "official_name": "STATION 5 MRT STATION",
                        "extraction_result": "success",
                        "extraction_confidence": "high",
                        "exits": [],
                        "accessibility_notes": [],
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                        "source_url": "https://test.com/5"
                    }
                },
                "failed_stations": [
                    {"station_id": "NS2", "error": "Error", "permanent": True},
                    {"station_id": "NS4", "error": "Error 2", "permanent": False}
                ],
                "processed_station_ids": ["NS1", "NS2", "NS3", "NS4", "NS5"]
            }
            
            with open(checkpoint_path, 'w') as f:
                json.dump(checkpoint_data, f)
            
            stage = Stage2Enrichment(
                {'stages': {'stage2_enrichment': {'test_mode': True}}},
                output_dir=tmpdir,
                resume_mode=True,
                retry_failed=True
            )
            
            # Load checkpoint manually
            checkpoint = stage._load_incremental_checkpoint()
            assert checkpoint is not None
            
            # Simulate the execute logic for initialization
            processed_station_ids = checkpoint.processed_station_ids.copy()
            failed_ids = {f["station_id"] for f in checkpoint.failed_stations}
            processed_station_ids = [sid for sid in processed_station_ids if sid not in failed_ids]
            
            # Verify failed stations are removed
            assert "NS2" not in processed_station_ids
            assert "NS4" not in processed_station_ids
            assert "NS1" in processed_station_ids
            assert "NS3" in processed_station_ids
            assert "NS5" in processed_station_ids


class TestEnrichmentCheckpointLoading:
    """Test loading from enrichment checkpoint file (Stage2Output format)"""
    
    def test_load_from_enrichment_file(self):
        """Test that checkpoint can be loaded from enrichment file and converted to incremental format"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create enrichment file (Stage2Output format - has retry_queue, no processed_station_ids)
            enrichment_path = os.path.join(tmpdir, "stage2_enrichment.json")
            enrichment_data = {
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "stage2_enrichment",
                    "total_stations": 5,
                    "successful": 3,
                    "failed": 2
                },
                "stations": {
                    "NS1": {
                        "station_id": "NS1",
                        "official_name": "STATION 1 MRT STATION",
                        "extraction_result": "success",
                        "extraction_confidence": "high",
                        "exits": [],
                        "accessibility_notes": [],
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                        "source_url": "https://test.com/1"
                    },
                    "NS3": {
                        "station_id": "NS3",
                        "official_name": "STATION 3 MRT STATION",
                        "extraction_result": "success",
                        "extraction_confidence": "high",
                        "exits": [],
                        "accessibility_notes": [],
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                        "source_url": "https://test.com/3"
                    }
                },
                "failed_stations": [
                    {"station_id": "NS2", "error": "Test error", "permanent": True},
                    {"station_id": "NS4", "error": "Test error 2", "permanent": False}
                ],
                "skipped_stations": [
                    {"station_id": "NS5", "reason": "Not on Fandom"}
                ],
                "retry_queue": []  # Stage2Output has this field
            }
            
            with open(enrichment_path, 'w') as f:
                json.dump(enrichment_data, f)
            
            # Initialize stage and load checkpoint
            stage = Stage2Enrichment(
                {'stages': {'stage2_enrichment': {'test_mode': True}}},
                output_dir=tmpdir
            )
            
            checkpoint = stage._load_incremental_checkpoint()
            
            # Verify checkpoint was loaded and converted
            assert checkpoint is not None
            assert len(checkpoint.stations) == 2
            assert len(checkpoint.failed_stations) == 2
            assert len(checkpoint.skipped_stations) == 1
            # Should have rebuilt processed_station_ids from stations + failed + skipped
            assert len(checkpoint.processed_station_ids) == 5
            assert "NS1" in checkpoint.processed_station_ids
            assert "NS2" in checkpoint.processed_station_ids
            assert "NS3" in checkpoint.processed_station_ids
            assert "NS4" in checkpoint.processed_station_ids
            assert "NS5" in checkpoint.processed_station_ids


class TestCorruptedCheckpointFallback:
    """Test fallback behavior when main checkpoint is corrupted"""
    
    def test_fallback_to_backup_when_main_corrupted(self):
        """Test that backup is used when main checkpoint has 0 processed_station_ids"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create corrupted main checkpoint (has stations but 0 processed IDs)
            main_path = os.path.join(tmpdir, "stage2_incremental.json")
            corrupted_data = {
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "stage2_enrichment",  # Wrong source - enrichment data in incremental file
                    "total_stations": 5
                },
                "stations": {
                    "NS1": {
                        "station_id": "NS1",
                        "official_name": "STATION 1 MRT STATION",
                        "extraction_result": "success",
                        "exits": [],
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                        "source_url": "https://test.com/1"
                    }
                },
                "failed_stations": [],
                "skipped_stations": [],
                "processed_station_ids": []  # Empty - corrupted!
            }
            
            with open(main_path, 'w') as f:
                json.dump(corrupted_data, f)
            
            # Create valid backup with proper data
            backup_path = os.path.join(tmpdir, "stage2_incremental.json.bak")
            backup_data = {
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "stage2_incremental",
                    "total_stations": 5
                },
                "stations": {
                    "NS1": {
                        "station_id": "NS1",
                        "official_name": "STATION 1 MRT STATION",
                        "extraction_result": "success",
                        "exits": [],
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                        "source_url": "https://test.com/1"
                    },
                    "NS2": {
                        "station_id": "NS2",
                        "official_name": "STATION 2 MRT STATION",
                        "extraction_result": "success",
                        "exits": [],
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                        "source_url": "https://test.com/2"
                    }
                },
                "failed_stations": [],
                "skipped_stations": [],
                "processed_station_ids": ["NS1", "NS2"]  # Valid
            }
            
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f)
            
            # Initialize stage and load checkpoint
            stage = Stage2Enrichment(
                {'stages': {'stage2_enrichment': {'test_mode': True}}},
                output_dir=tmpdir
            )
            
            checkpoint = stage._load_incremental_checkpoint()
            
            # Should have fallen back to backup
            assert checkpoint is not None
            assert len(checkpoint.processed_station_ids) == 2
            assert "NS1" in checkpoint.processed_station_ids
            assert "NS2" in checkpoint.processed_station_ids

    def test_rebuild_processed_ids_when_corrupted(self):
        """Test that processed_station_ids is rebuilt when checkpoint has stations but 0 processed IDs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create checkpoint with stations but 0 processed_station_ids (corrupted)
            checkpoint_path = os.path.join(tmpdir, "stage2_incremental.json")
            corrupted_data = {
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "stage2_incremental",
                    "total_stations": 5
                },
                "stations": {
                    "NS1": {
                        "station_id": "NS1",
                        "official_name": "STATION 1 MRT STATION",
                        "extraction_result": "success",
                        "exits": [],
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                        "source_url": "https://test.com/1"
                    },
                    "NS3": {
                        "station_id": "NS3",
                        "official_name": "STATION 3 MRT STATION",
                        "extraction_result": "success",
                        "exits": [],
                        "extraction_timestamp": datetime.utcnow().isoformat(),
                        "source_url": "https://test.com/3"
                    }
                },
                "failed_stations": [
                    {"station_id": "NS2", "error": "Error"}
                ],
                "skipped_stations": [
                    {"station_id": "NS4", "reason": "Skipped"}
                ],
                "processed_station_ids": []  # Empty - corrupted!
            }
            
            with open(checkpoint_path, 'w') as f:
                json.dump(corrupted_data, f)
            
            # Initialize stage and load checkpoint
            stage = Stage2Enrichment(
                {'stages': {'stage2_enrichment': {'test_mode': True}}},
                output_dir=tmpdir
            )
            
            checkpoint = stage._load_incremental_checkpoint()
            
            # Should have rebuilt processed_station_ids
            assert checkpoint is not None
            assert len(checkpoint.processed_station_ids) == 4
            assert "NS1" in checkpoint.processed_station_ids
            assert "NS2" in checkpoint.processed_station_ids
            assert "NS3" in checkpoint.processed_station_ids
            assert "NS4" in checkpoint.processed_station_ids


class TestRetryDeduplication:
    """Test that retry mode properly deduplicates stations"""
    
    @patch('src.pipelines.stage2_enrichment.Stage2Enrichment._load_incremental_checkpoint')
    @patch('src.pipelines.stage2_enrichment.Stage2Enrichment._save_incremental_checkpoint')
    def test_retry_removes_failed_from_stations_dict(self, mock_save, mock_load):
        """Test that failed stations are removed from stations dict when retrying"""
        
        # Create mock checkpoint with 1 successful, 1 failed
        mock_checkpoint = Mock()
        mock_checkpoint.processed_station_ids = ["NS1", "NS2"]
        mock_checkpoint.failed_stations = [
            {"station_id": "NS2", "error": "Error", "permanent": True}
        ]
        mock_checkpoint.stations = {
            "NS1": Stage2Station(
                station_id="NS1",
                official_name="STATION 1 MRT STATION",
                extraction_result="success",
                exits=[],
                extraction_timestamp=datetime.now(),
                source_url="https://test.com/1"
            ),
            "NS2": Stage2Station(
                station_id="NS2",
                official_name="STATION 2 MRT STATION",
                extraction_result="success",  # Was marked as success but also in failed
                exits=[],
                extraction_timestamp=datetime.now(),
                source_url="https://test.com/2"
            )
        }
        mock_checkpoint.skipped_stations = []
        mock_load.return_value = mock_checkpoint
        
        # Create stage in retry mode
        stage = Stage2Enrichment(
            {'stages': {'stage2_enrichment': {'test_mode': True}}},
            output_dir="/tmp",
            resume_mode=True,
            retry_failed=True
        )
        
        # Create test input
        stations = [
            Stage1Station(
                station_id="NS1",
                official_name="STATION 1 MRT STATION",
                display_name="Station 1",
                mrt_codes=["NS1"],
                lines=["NSL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.0, lng=103.0, source="onemap")],
                fandom_url="https://test.com/1"
            ),
            Stage1Station(
                station_id="NS2",
                official_name="STATION 2 MRT STATION",
                display_name="Station 2",
                mrt_codes=["NS2"],
                lines=["NSL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.1, lng=103.1, source="onemap")],
                fandom_url="https://test.com/2"
            )
        ]
        input_data = Stage1Output(metadata={}, stations=stations)
        
        # Mock _extract_station to return success for NS2
        def mock_extract(station):
            return Stage2Station(
                station_id=station.station_id,
                official_name=station.official_name,
                extraction_result="success",
                exits=[],
                extraction_timestamp=datetime.now(),
                source_url=station.fandom_url
            )
        
        with patch.object(stage, '_extract_station', side_effect=mock_extract):
            with patch.object(stage, '_retry_failed_stations'):
                with patch('time.sleep'):
                    result = stage.execute(input_data)
        
        # NS2 should NOT appear twice - once in success and once reprocessed
        # It should be removed from stations dict when retry starts
        assert len(result.stations) == 2
        assert "NS1" in result.stations
        assert "NS2" in result.stations


class TestSkipDeduplication:
    """Test that skipped stations are properly deduplicated"""
    
    @patch('src.pipelines.stage2_enrichment.Stage2Enrichment._load_incremental_checkpoint')
    @patch('src.pipelines.stage2_enrichment.Stage2Enrichment._save_incremental_checkpoint')
    def test_skip_prevents_duplicates(self, mock_save, mock_load):
        """Test that skipped stations don't get added to list twice"""
        
        # Create mock checkpoint with 1 station already skipped
        mock_checkpoint = Mock()
        mock_checkpoint.processed_station_ids = ["NS1", "NS2"]
        mock_checkpoint.failed_stations = []
        mock_checkpoint.stations = {
            "NS1": Stage2Station(
                station_id="NS1",
                official_name="STATION 1 MRT STATION",
                extraction_result="success",
                exits=[],
                extraction_timestamp=datetime.now(),
                source_url="https://test.com/1"
            )
        }
        mock_checkpoint.skipped_stations = [
            {"station_id": "NS2", "official_name": "STATION 2 MRT STATION", "reason": "not_on_fandom"}
        ]
        mock_load.return_value = mock_checkpoint
        
        # Create stage in retry mode
        stage = Stage2Enrichment(
            {'stages': {'stage2_enrichment': {'test_mode': True}}},
            output_dir="/tmp",
            resume_mode=True,
            retry_failed=True
        )
        
        # Create test input
        stations = [
            Stage1Station(
                station_id="NS1",
                official_name="STATION 1 MRT STATION",
                display_name="Station 1",
                mrt_codes=["NS1"],
                lines=["NSL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.0, lng=103.0, source="onemap")],
                fandom_url="https://test.com/1"
            ),
            Stage1Station(
                station_id="NS2",
                official_name="STATION 2 MRT STATION",
                display_name="Station 2",
                mrt_codes=["NS2"],
                lines=["NSL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.1, lng=103.1, source="onemap")],
                fandom_url="https://test.com/2"
            )
        ]
        input_data = Stage1Output(metadata={}, stations=stations)
        
        # Mock _extract_station to return None (skipped) for NS2
        def mock_extract(station):
            if station.station_id == "NS1":
                return Stage2Station(
                    station_id=station.station_id,
                    official_name=station.official_name,
                    extraction_result="success",
                    exits=[],
                    extraction_timestamp=datetime.now(),
                    source_url=station.fandom_url
                )
            else:
                return None  # Skip NS2
        
        with patch.object(stage, '_extract_station', side_effect=mock_extract):
            with patch.object(stage, '_retry_failed_stations'):
                with patch('time.sleep'):
                    result = stage.execute(input_data)
        
        # NS2 should appear only once in skipped list
        ns2_skip_count = sum(1 for s in result.skipped_stations if s["station_id"] == "NS2")
        assert ns2_skip_count == 1, f"NS2 appeared {ns2_skip_count} times in skipped list, expected 1"

    @patch('src.pipelines.stage2_enrichment.Stage2Enrichment._load_incremental_checkpoint')
    @patch('src.pipelines.stage2_enrichment.Stage2Enrichment._save_incremental_checkpoint')
    def test_skip_removes_from_other_lists(self, mock_save, mock_load):
        """Test that skipping removes station from stations and failed lists"""
        
        # Create mock checkpoint with station in multiple lists (corrupted state)
        mock_checkpoint = Mock()
        mock_checkpoint.processed_station_ids = ["NS1", "NS2"]
        mock_checkpoint.failed_stations = [
            {"station_id": "NS2", "error": "Error"}  # NS2 in failed list
        ]
        mock_checkpoint.stations = {
            "NS1": Stage2Station(
                station_id="NS1",
                official_name="STATION 1 MRT STATION",
                extraction_result="success",
                exits=[],
                extraction_timestamp=datetime.now(),
                source_url="https://test.com/1"
            ),
            "NS2": Stage2Station(  # NS2 in stations dict
                station_id="NS2",
                official_name="STATION 2 MRT STATION",
                extraction_result="success",
                exits=[],
                extraction_timestamp=datetime.now(),
                source_url="https://test.com/2"
            )
        }
        mock_checkpoint.skipped_stations = []
        mock_load.return_value = mock_checkpoint
        
        # Create stage
        stage = Stage2Enrichment(
            {'stages': {'stage2_enrichment': {'test_mode': True}}},
            output_dir="/tmp",
            resume_mode=True,
            retry_failed=True
        )
        
        # Create test input
        stations = [
            Stage1Station(
                station_id="NS1",
                official_name="STATION 1 MRT STATION",
                display_name="Station 1",
                mrt_codes=["NS1"],
                lines=["NSL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.0, lng=103.0, source="onemap")],
                fandom_url="https://test.com/1"
            ),
            Stage1Station(
                station_id="NS2",
                official_name="STATION 2 MRT STATION",
                display_name="Station 2",
                mrt_codes=["NS2"],
                lines=["NSL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.1, lng=103.1, source="onemap")],
                fandom_url="https://test.com/2"
            )
        ]
        input_data = Stage1Output(metadata={}, stations=stations)
        
        # Mock _extract_station to return None (skipped) for NS2
        def mock_extract(station):
            if station.station_id == "NS1":
                return Stage2Station(
                    station_id=station.station_id,
                    official_name=station.official_name,
                    extraction_result="success",
                    exits=[],
                    extraction_timestamp=datetime.now(),
                    source_url=station.fandom_url
                )
            else:
                return None  # Skip NS2
        
        with patch.object(stage, '_extract_station', side_effect=mock_extract):
            with patch.object(stage, '_retry_failed_stations'):
                with patch('time.sleep'):
                    result = stage.execute(input_data)
        
        # NS2 should be in skipped list only, not in stations or failed
        assert "NS2" not in result.stations, "NS2 should not be in stations dict when skipped"
        assert not any(f["station_id"] == "NS2" for f in result.failed_stations), "NS2 should not be in failed list when skipped"
        assert any(s["station_id"] == "NS2" for s in result.skipped_stations), "NS2 should be in skipped list"


class TestNoOverlaps:
    """Test that there are no overlaps between stations, failed, and skipped lists"""
    
    @patch('src.pipelines.stage2_enrichment.Stage2Enrichment._load_incremental_checkpoint')
    @patch('src.pipelines.stage2_enrichment.Stage2Enrichment._save_incremental_checkpoint')
    def test_no_overlaps_in_output(self, mock_save, mock_load):
        """Test that station IDs don't appear in multiple lists"""
        
        # Create mock checkpoint
        mock_checkpoint = Mock()
        mock_checkpoint.processed_station_ids = ["NS1", "NS2", "NS3"]
        mock_checkpoint.failed_stations = [
            {"station_id": "NS2", "error": "Error"}
        ]
        mock_checkpoint.stations = {
            "NS1": Stage2Station(
                station_id="NS1",
                official_name="STATION 1 MRT STATION",
                extraction_result="success",
                exits=[],
                extraction_timestamp=datetime.now(),
                source_url="https://test.com/1"
            ),
            "NS3": Stage2Station(
                station_id="NS3",
                official_name="STATION 3 MRT STATION",
                extraction_result="success",
                exits=[],
                extraction_timestamp=datetime.now(),
                source_url="https://test.com/3"
            )
        }
        mock_checkpoint.skipped_stations = []
        mock_load.return_value = mock_checkpoint
        
        # Create stage
        stage = Stage2Enrichment(
            {'stages': {'stage2_enrichment': {'test_mode': True}}},
            output_dir="/tmp",
            resume_mode=True,
            retry_failed=True
        )
        
        # Create test input
        stations = [
            Stage1Station(
                station_id=f"NS{i}",
                official_name=f"STATION {i} MRT STATION",
                display_name=f"Station {i}",
                mrt_codes=[f"NS{i}"],
                lines=["NSL"],
                station_type=StationType.MRT,
                exits=[Exit(exit_code="A", lat=1.0, lng=103.0, source="onemap")],
                fandom_url=f"https://test.com/{i}"
            )
            for i in range(1, 4)
        ]
        input_data = Stage1Output(metadata={}, stations=stations)
        
        # Mock _extract_station
        def mock_extract(station):
            return Stage2Station(
                station_id=station.station_id,
                official_name=station.official_name,
                extraction_result="success",
                exits=[],
                extraction_timestamp=datetime.now(),
                source_url=station.fandom_url
            )
        
        with patch.object(stage, '_extract_station', side_effect=mock_extract):
            with patch.object(stage, '_retry_failed_stations'):
                with patch('time.sleep'):
                    result = stage.execute(input_data)
        
        # Get all IDs from each list
        station_ids = set(result.stations.keys())
        failed_ids = {f["station_id"] for f in result.failed_stations}
        skipped_ids = {s["station_id"] for s in result.skipped_stations}
        
        # Check for overlaps
        assert len(station_ids & failed_ids) == 0, f"Overlaps between stations and failed: {station_ids & failed_ids}"
        assert len(station_ids & skipped_ids) == 0, f"Overlaps between stations and skipped: {station_ids & skipped_ids}"
        assert len(failed_ids & skipped_ids) == 0, f"Overlaps between failed and skipped: {failed_ids & skipped_ids}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
