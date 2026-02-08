"""
OpenRouter API Client for MRT Station Data Extraction

This module provides a client for interacting with the OpenRouter API
to extract structured station data from HTML content using LLM.
"""

import os
import re
import json
import requests
from typing import Optional, Dict, Any
from ..utils.logger import logger


class OpenRouterClient:
    """Client for OpenRouter API to extract station data from HTML"""
    
    def __init__(self, config: dict):
        """Initialize OpenRouter client with configuration"""
        api_config = config.get('apis', {}).get('openrouter', {})
        self.api_url = api_config.get('base_url', 'https://openrouter.ai/api/v1') + "/chat/completions"
        self.model = api_config.get('model', 'openai/gpt-oss-120b:free')
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
            logger.info(f"Extracting data for {station_name} using {self.model}")
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
            
            # Validate LLM response structure before processing
            if not self._validate_llm_response(data):
                logger.warning(f"Invalid LLM response structure for {station_name}")
                return None
            
            return {
                "confidence": data.get("extraction_confidence", "medium"),
                "exits": data.get("exits", []),
                "accessibility_notes": data.get("accessibility_notes", [])
            }
            
        except requests.exceptions.RequestException as e:
            # Log specific HTTP status codes for better debugging
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                if status_code == 401:
                    logger.error(f"API authentication failed (401): Invalid API key")
                elif status_code == 429:
                    logger.error(f"API rate limited (429): Too many requests")
                elif status_code == 500:
                    logger.error(f"API server error (500): Internal server error")
                else:
                    logger.error(f"API request failed ({status_code}): {e}")
            else:
                logger.error(f"API request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in extraction: {e}")
            return None
    
    def _validate_llm_response(self, data: Dict) -> bool:
        """Validate LLM response structure before creating objects"""
        try:
            # Check basic structure
            if not isinstance(data, dict):
                return False
            
            # Must have exits field
            if "exits" not in data:
                return False
            
            # Check exits is a list
            exits = data.get("exits", [])
            if not isinstance(exits, list):
                return False
            
            # If no exits, still valid but empty
            if len(exits) == 0:
                return True
            
            # Validate each exit structure
            for exit_data in exits:
                if not isinstance(exit_data, dict):
                    return False
                
                # Check required fields
                if "exit_code" not in exit_data:
                    return False
                
                # Validate optional fields if present
                if "platforms" in exit_data and not isinstance(exit_data["platforms"], list):
                    return False
                
                if "bus_stops" in exit_data:
                    bus_stops = exit_data["bus_stops"]
                    if not isinstance(bus_stops, list):
                        return False
                    for bus_stop in bus_stops:
                        if not isinstance(bus_stop, dict) or "code" not in bus_stop:
                            return False
                
                if "accessibility" in exit_data and not isinstance(exit_data["accessibility"], list):
                    return False
                
                if "nearby_landmarks" in exit_data and not isinstance(exit_data["nearby_landmarks"], list):
                    return False
            
            return True
        except Exception as e:
            logger.error(f"LLM response validation error: {e}")
            return False
    
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