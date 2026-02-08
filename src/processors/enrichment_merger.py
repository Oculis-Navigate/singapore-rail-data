"""
Enrichment Data Merger

This module merges enrichment data (extracted via LLM or manually maintained)
into the main MRT transit graph output.

The enrichment data is kept separate from the deterministic data sources
(data.gov.sg, OneMap) to maintain clear provenance and allow independent updates.
"""

import warnings
warnings.warn(
    "enrichment_merger is deprecated. Use pipelines.stage3_merger instead.",
    DeprecationWarning,
    stacklevel=2
)

import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from ..utils.logger import logger


@dataclass
class MergedExit:
    """Exit data merged from deterministic + enrichment sources"""
    exit_code: str
    lat: float
    lng: float
    # Enrichment fields (optional)
    platforms: Optional[List[Dict[str, str]]] = None
    accessibility: Optional[List[str]] = None
    bus_stops: Optional[List[Dict[str, Any]]] = None
    nearby_landmarks: Optional[List[str]] = None


class EnrichmentMerger:
    """Merges enrichment data into the main transit graph"""
    
    def __init__(self, enrichment_file: str = "output/mrt_enrichment_data.json"):
        self.enrichment_file = enrichment_file
        self.enrichment_data = self._load_enrichment_data()
    
    def _load_enrichment_data(self) -> Dict[str, Any]:
        """Load enrichment data from file if it exists"""
        if not os.path.exists(self.enrichment_file):
            logger.info(f"No enrichment data file found at {self.enrichment_file}")
            return {}
        
        try:
            with open(self.enrichment_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                stations = data.get("stations", {})
                logger.info(f"Loaded enrichment data for {len(stations)} stations")
                return stations
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load enrichment data: {e}")
            return {}
    
    def merge_station(self, station: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge enrichment data into a single station record.
        
        Args:
            station: Station data from deterministic sources
            
        Returns:
            Station data with enrichment fields merged in
        """
        station_name = station.get("official_name", "")
        
        # Find matching enrichment data
        enrichment = self.enrichment_data.get(station_name)
        
        if not enrichment:
            # No enrichment data available, return as-is
            return station
        
        # Create a copy to avoid mutating original
        merged = station.copy()
        
        # Add station-level enrichment fields
        if enrichment.get("lines"):
            merged["lines_served"] = enrichment["lines"]
        
        if enrichment.get("accessibility_notes"):
            merged["accessibility_notes"] = enrichment["accessibility_notes"]
        
        if enrichment.get("last_updated"):
            merged["enrichment_last_updated"] = enrichment["last_updated"]
        
        # Merge exit-level data
        if enrichment.get("exits") and station.get("exits"):
            merged["exits"] = self._merge_exits(
                station["exits"],
                enrichment["exits"]
            )
        
        # Add confidence indicator
        if enrichment.get("extraction_confidence"):
            merged["data_quality"] = {
                "extraction_confidence": enrichment["extraction_confidence"],
                "source": "enrichment_data"
            }
        
        return merged
    
    def _merge_exits(
        self,
        deterministic_exits: List[Dict],
        enrichment_exits: List[Dict]
    ) -> List[Dict]:
        """
        Merge exit data from both sources.
        
        Matches exits by exit code (case-insensitive, normalizes formats).
        """
        # Create lookup by normalized exit code
        enrichment_by_code = {}
        for exit_data in enrichment_exits:
            code = exit_data.get("exit_code", "").upper().strip()
            # Normalize: "Exit A" -> "A", "Exit 1" -> "1"
            code = code.replace("EXIT ", "").replace("EXIT", "")
            enrichment_by_code[code] = exit_data
        
        merged_exits = []
        for det_exit in deterministic_exits:
            exit_code = det_exit.get("exit_code", "").upper().strip()
            # Normalize the deterministic exit code too
            norm_code = exit_code.replace("EXIT ", "").replace("EXIT", "")
            
            # Start with deterministic data
            merged_exit = det_exit.copy()
            
            # Add enrichment data if available
            if norm_code in enrichment_by_code:
                enrichment = enrichment_by_code[norm_code]
                
                # Add enrichment fields only if they exist and are not empty
                if enrichment.get("platforms"):
                    merged_exit["platforms"] = enrichment["platforms"]
                
                if enrichment.get("accessibility"):
                    merged_exit["accessibility"] = enrichment["accessibility"]
                
                if enrichment.get("bus_stops"):
                    merged_exit["bus_stops"] = enrichment["bus_stops"]
                
                if enrichment.get("nearby_landmarks"):
                    merged_exit["nearby_landmarks"] = enrichment["nearby_landmarks"]
            
            merged_exits.append(merged_exit)
        
        return merged_exits
    
    def merge_all(self, stations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge enrichment data into all stations.
        
        Args:
            stations: List of station data from deterministic sources
            
        Returns:
            List of stations with enrichment data merged where available
        """
        if not self.enrichment_data:
            logger.info("No enrichment data available, returning deterministic data only")
            return stations
        
        logger.subsection("Merging Enrichment Data")
        
        merged_stations = []
        enriched_count = 0
        
        for station in stations:
            merged = self.merge_station(station)
            merged_stations.append(merged)
            
            if merged != station:  # Was enriched
                enriched_count += 1
        
        logger.success(f"Enriched {enriched_count}/{len(stations)} stations with additional data")
        
        # Report which stations have enrichment data
        enriched_names = [
            s["official_name"] 
            for s in merged_stations 
            if s.get("enrichment_last_updated")
        ]
        
        if enriched_names:
            logger.info(f"Stations with enrichment: {', '.join(enriched_names[:5])}")
            if len(enriched_names) > 5:
                logger.info(f"  ... and {len(enriched_names) - 5} more")
        
        return merged_stations
    
    def get_enrichment_stats(self) -> Dict[str, Any]:
        """Get statistics about the enrichment data"""
        if not self.enrichment_data:
            return {"status": "no_data"}
        
        stats = {
            "total_stations": len(self.enrichment_data),
            "status": "available"
        }
        
        # Count exits with various enrichment types
        exits_with_platforms = 0
        exits_with_accessibility = 0
        exits_with_bus_stops = 0
        total_exits = 0
        
        for station_name, station_data in self.enrichment_data.items():
            for exit_data in station_data.get("exits", []):
                total_exits += 1
                if exit_data.get("platforms"):
                    exits_with_platforms += 1
                if exit_data.get("accessibility"):
                    exits_with_accessibility += 1
                if exit_data.get("bus_stops"):
                    exits_with_bus_stops += 1
        
        stats["total_exits"] = total_exits
        stats["exits_with_platforms"] = exits_with_platforms
        stats["exits_with_accessibility"] = exits_with_accessibility
        stats["exits_with_bus_stops"] = exits_with_bus_stops
        
        return stats


def merge_enrichment_data(stations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convenience function to merge enrichment data into station list.
    
    Usage:
        from enrichment_merger import merge_enrichment_data
        final_stations = merge_enrichment_data(stations)
    """
    merger = EnrichmentMerger()
    
    # Log stats if enrichment data exists
    stats = merger.get_enrichment_stats()
    if stats["status"] == "available":
        logger.info(f"Enrichment data: {stats['total_stations']} stations, "
                   f"{stats['total_exits']} exits")
        logger.info(f"  - {stats['exits_with_platforms']} exits with platform data")
        logger.info(f"  - {stats['exits_with_accessibility']} exits with accessibility data")
        logger.info(f"  - {stats['exits_with_bus_stops']} exits with bus stop data")
    
    return merger.merge_all(stations)
