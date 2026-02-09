"""
Pytest configuration and fixtures
"""

import pytest
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Ensure src is in path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.contracts.schemas import (
    StationType, Exit, Stage1Station, Stage1Output,
    EnrichedExit, Stage2Station, Stage2Output,
    FinalExit, FinalStation, FinalOutput
)


@pytest.fixture
def sample_stage1_output() -> Dict[str, Any]:
    """Sample Stage 1 output for testing"""
    return {
        "metadata": {"test": True},
        "stations": [
            {
                "station_id": "NS13",
                "official_name": "YISHUN MRT STATION",
                "display_name": "Yishun",
                "mrt_codes": ["NS13"],
                "lines": ["NSL"],
                "station_type": "mrt",
                "exits": [
                    {"exit_code": "A", "lat": 1.429, "lng": 103.835, "source": "onemap"}
                ],
                "fandom_url": "https://example.com"
            }
        ]
    }


@pytest.fixture
def sample_stage1_station() -> Stage1Station:
    """Sample Stage 1 station for testing"""
    exit_obj = Exit(exit_code="A", lat=1.429, lng=103.835, source="onemap")
    return Stage1Station(
        station_id="NS13",
        official_name="YISHUN MRT STATION",
        display_name="Yishun",
        mrt_codes=["NS13"],
        lines=["NSL"],
        station_type=StationType.MRT,
        exits=[exit_obj],
        fandom_url="https://example.com"
    )


@pytest.fixture
def sample_stage2_station() -> Stage2Station:
    """Sample Stage 2 station for testing"""
    return Stage2Station(
        station_id="NS13",
        official_name="YISHUN MRT STATION",
        extraction_result="success",
        extraction_confidence="high",
        exits=[EnrichedExit(exit_code="A")],
        extraction_timestamp=datetime.now(),
        source_url="https://example.com"
    )


@pytest.fixture
def sample_stage2_output(sample_stage2_station: Stage2Station) -> Stage2Output:
    """Sample Stage 2 output for testing"""
    return Stage2Output(
        metadata={"test": True},
        stations={"NS13": sample_stage2_station},
        failed_stations=[],
        retry_queue=[]
    )


@pytest.fixture
def sample_final_station() -> FinalStation:
    """Sample final station for testing"""
    exit_obj = FinalExit(exit_code="A", lat=1.429, lng=103.835)
    return FinalStation(
        official_name="YISHUN MRT STATION",
        mrt_codes=["NS13"],
        exits=[exit_obj]
    )


@pytest.fixture
def singapore_coords_valid() -> list:
    """Valid Singapore coordinates for testing"""
    return [
        (1.3521, 103.8198),  # Central Singapore
        (1.429, 103.835),    # Northern Singapore
        (1.30, 104.00),      # Eastern Singapore
        (1.44, 103.78),      # Northern
    ]


@pytest.fixture
def singapore_coords_invalid() -> list:
    """Invalid coordinates (outside Singapore) for testing"""
    return [
        (0.0, 103.0),      # Too far south
        (50.0, 103.0),     # Way too far north
        (1.35, 0.0),       # Too far west
        (1.35, 150.0),     # Way too far east
    ]
