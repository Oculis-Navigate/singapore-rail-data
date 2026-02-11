"""
Extraction Metrics

Tracks metrics for Stage 2 extraction quality and performance.
"""

from typing import Dict, Any, Optional
from ..utils.logger import logger


class ExtractionMetrics:
    """Track metrics for Stage 2 extraction quality."""
    
    def __init__(self):
        self.stats = {
            "total_processed": 0,
            "content_extraction_success": 0,
            "content_extraction_failed": 0,
            "llm_extraction_success": 0,
            "llm_extraction_failed": 0,
            "empty_exits": 0,
            "low_confidence": 0,
            "high_confidence": 0,
            "medium_confidence": 0,
            "content_size_before": [],
            "content_size_after": [],
        }
        self.station_details = {}
    
    def record_extraction(
        self, 
        station_name: str, 
        station_id: str,
        html_size_before: int,
        html_size_after: int,
        result: Optional[Dict]
    ):
        """
        Record metrics for a single extraction.
        
        Args:
            station_name: Display name of the station
            station_id: ID of the station (e.g., "NS13")
            html_size_before: Size of original HTML
            html_size_after: Size of extracted content
            result: LLM extraction result or None if failed
        """
        self.stats["total_processed"] += 1
        self.stats["content_size_before"].append(html_size_before)
        self.stats["content_size_after"].append(html_size_after)
        
        # Track content extraction success
        if html_size_after > 0:
            self.stats["content_extraction_success"] += 1
        else:
            self.stats["content_extraction_failed"] += 1
        
        # Track LLM extraction success
        if result:
            self.stats["llm_extraction_success"] += 1
            
            # Track confidence levels
            confidence = result.get("confidence", "low")
            if confidence == "high":
                self.stats["high_confidence"] += 1
            elif confidence == "medium":
                self.stats["medium_confidence"] += 1
            else:
                self.stats["low_confidence"] += 1
            
            # Track empty exits
            if not result.get("exits", []):
                self.stats["empty_exits"] += 1
        else:
            self.stats["llm_extraction_failed"] += 1
        
        # Store details for this station
        self.station_details[station_id] = {
            "station_name": station_name,
            "html_size_before": html_size_before,
            html_size_after: html_size_after,
            "has_result": result is not None,
            "confidence": result.get("confidence", "none") if result else "none",
            "exit_count": len(result.get("exits", [])) if result else 0
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all metrics.
        
        Returns:
            Dict with summary statistics
        """
        total = self.stats["total_processed"]
        if total == 0:
            return {"message": "No stations processed yet"}
        
        # Calculate averages
        avg_before = sum(self.stats["content_size_before"]) / len(self.stats["content_size_before"]) if self.stats["content_size_before"] else 0
        avg_after = sum(self.stats["content_size_after"]) / len(self.stats["content_size_after"]) if self.stats["content_size_after"] else 0
        
        reduction_pct = 0
        if avg_before > 0:
            reduction_pct = ((avg_before - avg_after) / avg_before) * 100
        
        return {
            "total_stations": total,
            "content_extraction": {
                "success": self.stats["content_extraction_success"],
                "failed": self.stats["content_extraction_failed"],
                "success_rate": round(self.stats["content_extraction_success"] / total * 100, 1)
            },
            "llm_extraction": {
                "success": self.stats["llm_extraction_success"],
                "failed": self.stats["llm_extraction_failed"],
                "success_rate": round(self.stats["llm_extraction_success"] / total * 100, 1)
            },
            "confidence_distribution": {
                "high": self.stats["high_confidence"],
                "medium": self.stats["medium_confidence"],
                "low": self.stats["low_confidence"]
            },
            "data_quality": {
                "empty_exits": self.stats["empty_exits"],
                "empty_exit_rate": round(self.stats["empty_exits"] / total * 100, 1)
            },
            "content_size": {
                "avg_before": round(avg_before, 0),
                "avg_after": round(avg_after, 0),
                "avg_reduction_pct": round(reduction_pct, 1)
            }
        }
    
    def print_report(self):
        """Print a formatted report of the metrics."""
        summary = self.get_summary()
        
        if "message" in summary:
            logger.info(summary["message"])
            return
        
        logger.section("Stage 2 Extraction Metrics")
        
        logger.subsection("Processing Summary")
        logger.info(f"Total stations processed: {summary['total_stations']}")
        logger.info(f"Content extraction success: {summary['content_extraction']['success']} ({summary['content_extraction']['success_rate']}%)")
        logger.info(f"LLM extraction success: {summary['llm_extraction']['success']} ({summary['llm_extraction']['success_rate']}%)")
        
        logger.subsection("Confidence Distribution")
        logger.info(f"High: {summary['confidence_distribution']['high']}")
        logger.info(f"Medium: {summary['confidence_distribution']['medium']}")
        logger.info(f"Low: {summary['confidence_distribution']['low']}")
        
        logger.subsection("Data Quality")
        logger.info(f"Stations with empty exits: {summary['data_quality']['empty_exits']} ({summary['data_quality']['empty_exit_rate']}%)")
        
        logger.subsection("Content Size Optimization")
        logger.info(f"Average original size: {summary['content_size']['avg_before']:.0f} chars")
        logger.info(f"Average extracted size: {summary['content_size']['avg_after']:.0f} chars")
        logger.info(f"Average reduction: {summary['content_size']['avg_reduction_pct']:.1f}%")
    
    def get_failed_stations(self) -> Dict[str, Dict]:
        """
        Get details of stations with extraction failures.
        
        Returns:
            Dict mapping station_id to failure details
        """
        failed = {}
        for station_id, details in self.station_details.items():
            if not details["has_result"] or details["exit_count"] == 0:
                failed[station_id] = details
        return failed
    
    def reset(self):
        """Reset all metrics."""
        self.__init__()
