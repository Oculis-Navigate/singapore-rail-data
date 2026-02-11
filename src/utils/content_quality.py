"""
Content Quality Checker

Validates that extracted HTML content has sufficient information
for LLM processing.
"""

from typing import Dict, List
from ..utils.logger import logger


class ContentQualityChecker:
    """Check if extracted HTML content has sufficient information."""
    
    def __init__(self):
        self.min_content_length = 500
        self.required_indicators = ['exit', 'platform', 'line', 'station']
    
    def check_quality(self, html: str, station_name: str) -> Dict:
        """
        Check quality of extracted content.
        
        Args:
            html: Extracted HTML content
            station_name: Name of station for logging
            
        Returns:
            Dict with is_valid flag, list of issues, and content stats
        """
        issues = []
        
        # Check content length
        if len(html) < self.min_content_length:
            issues.append(f"Content too short ({len(html)} chars)")
        
        # Check for required indicators
        html_lower = html.lower()
        missing_indicators = [
            indicator for indicator in self.required_indicators
            if indicator not in html_lower
        ]
        if missing_indicators:
            issues.append(f"Missing key indicators: {missing_indicators}")
        
        # Check for tables (important for exit/bus stop data)
        has_tables = '<table' in html_lower
        if not has_tables:
            issues.append("No tables found")
        
        # Log quality issues
        if issues:
            logger.warning(f"Content quality issues for {station_name}: {', '.join(issues)}")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "content_stats": {
                "length": len(html),
                "has_tables": has_tables,
                "has_exits": 'exit' in html_lower,
                "has_platforms": 'platform' in html_lower,
            }
        }
    
    def validate_extraction_result(self, result: Dict, station_name: str) -> Dict:
        """
        Validate the result from LLM extraction.
        
        Args:
            result: Dict with extraction result (exits, confidence, etc.)
            station_name: Name of station for logging
            
        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []
        
        if not result:
            issues.append("No extraction result")
            return {"is_valid": False, "issues": issues, "warnings": warnings}
        
        # Check confidence level
        confidence = result.get("confidence", "low")
        if confidence == "low":
            warnings.append("Low confidence extraction")
        
        # Check for empty exits
        exits = result.get("exits", [])
        if not exits:
            issues.append("No exits extracted")
        
        # Validate exit structure
        for i, exit_data in enumerate(exits):
            if not isinstance(exit_data, dict):
                issues.append(f"Exit {i} is not a dict")
                continue
            
            if "exit_code" not in exit_data:
                issues.append(f"Exit {i} missing exit_code")
            
            # Validate bus stops if present
            if "bus_stops" in exit_data:
                bus_stops = exit_data["bus_stops"]
                if not isinstance(bus_stops, list):
                    issues.append(f"Exit {i} bus_stops is not a list")
                else:
                    for j, bus_stop in enumerate(bus_stops):
                        if not isinstance(bus_stop, dict):
                            issues.append(f"Exit {i} bus_stop {j} is not a dict")
                        elif "code" not in bus_stop:
                            issues.append(f"Exit {i} bus_stop {j} missing code")
        
        # Log validation results
        if issues:
            logger.warning(f"Validation issues for {station_name}: {', '.join(issues)}")
        if warnings:
            logger.info(f"Validation warnings for {station_name}: {', '.join(warnings)}")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "exit_count": len(exits),
            "confidence": confidence
        }
