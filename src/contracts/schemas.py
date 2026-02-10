"""
Data contracts and Pydantic schemas for MRT Data Pipeline

This module defines all data structures used throughout the pipeline stages,
ensuring type safety and validation between components.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime
from enum import Enum


class StationType(str, Enum):
    """Station type enumeration"""
    MRT = "mrt"
    LRT = "lrt"


class Exit(BaseModel):
    """Exit information from Stage 1"""
    exit_code: str = Field(..., description="Exit identifier (A, B, 1, 2, etc.)")
    lat: float = Field(..., ge=1.0, le=2.0, description="Latitude in Singapore")
    lng: float = Field(..., ge=103.0, le=105.0, description="Longitude in Singapore")
    source: Literal["onemap", "datagov"] = Field(..., description="Data source")


class Stage1Station(BaseModel):
    """Station information from Stage 1 (deterministic ingestion)"""
    station_id: str = Field(..., pattern=r"^[A-Z]{1,3}\d+$", description="Primary station code (NS13)")
    official_name: str = Field(..., pattern=r".*MRT STATION$|.*LRT STATION$", description="Full station name in CAPS")
    display_name: str = Field(..., description="Human-readable name (Yishun)")
    mrt_codes: List[str] = Field(..., min_length=1, description="All station codes for this station")
    lines: List[str] = Field(..., min_length=1, description="Line codes (NSL, EWL, etc.)")
    station_type: StationType
    exits: List[Exit] = Field(..., min_length=1)
    fandom_url: str = Field(..., description="Pre-computed Fandom wiki URL")
    extraction_status: Literal["pending", "completed", "failed"] = "pending"


class Stage1Output(BaseModel):
    """Output structure for Stage 1"""
    metadata: Dict[str, Any] = Field(..., description="Run metadata")
    stations: List[Stage1Station] = Field(..., min_length=1)


class Platform(BaseModel):
    """Platform information for enriched exits"""
    platform_code: str
    towards_code: str = Field(..., pattern=r"^[A-Z]{1,3}\d+$")
    line_code: str = Field(..., pattern=r"^[A-Z]{2,3}$")


class BusStop(BaseModel):
    """Bus stop information"""
    code: str = Field(..., pattern=r"^\d{5}$", description="5-digit bus stop code")
    services: List[str] = Field(default_factory=list)


class EnrichedExit(BaseModel):
    """Enriched exit information from Stage 2"""
    exit_code: str
    platforms: Optional[List[Platform]] = None
    accessibility: Optional[List[str]] = None
    bus_stops: Optional[List[BusStop]] = None
    nearby_landmarks: Optional[List[str]] = None


class Stage2Station(BaseModel):
    """Station information from Stage 2 (enrichment extraction)"""
    station_id: str
    official_name: str
    extraction_result: Literal["success", "failed"]
    extraction_confidence: Optional[Literal["high", "medium", "low"]] = None
    exits: List[EnrichedExit]
    accessibility_notes: List[str] = Field(default_factory=list)
    extraction_timestamp: datetime
    source_url: str
    error_message: Optional[str] = None


class Stage2Output(BaseModel):
    """Output structure for Stage 2"""
    metadata: Dict[str, Any]
    stations: Dict[str, Stage2Station]  # Keyed by station_id
    failed_stations: List[Dict[str, Any]]
    retry_queue: List[str]


class Stage2IncrementalOutput(BaseModel):
    """Incremental checkpoint for Stage 2 (allows resume)"""
    metadata: Dict[str, Any] = Field(..., description="Checkpoint metadata")
    stations: Dict[str, Stage2Station] = Field(default_factory=dict, description="Successfully processed stations")
    failed_stations: List[Dict[str, Any]] = Field(default_factory=list, description="Failed station records")
    processed_station_ids: List[str] = Field(default_factory=list, description="All processed station IDs (success + failed)")


class FinalExit(BaseModel):
    """Final merged exit information"""
    exit_code: str
    lat: float
    lng: float
    platforms: Optional[List[Platform]] = None
    accessibility: Optional[List[str]] = None
    bus_stops: Optional[List[BusStop]] = None
    nearby_landmarks: Optional[List[str]] = None


class FinalStation(BaseModel):
    """Final merged station information"""
    official_name: str
    mrt_codes: List[str]
    exits: List[FinalExit]
    lines_served: Optional[List[str]] = None
    accessibility_notes: Optional[List[str]] = None
    enrichment_last_updated: Optional[datetime] = None
    data_quality: Optional[Dict[str, Any]] = None


class FinalOutput(BaseModel):
    """Final output structure for the complete pipeline"""
    metadata: Dict[str, Any]
    stations: List[FinalStation]