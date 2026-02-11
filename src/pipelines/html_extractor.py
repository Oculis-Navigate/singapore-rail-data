"""
HTML Content Extractor for Fandom Wiki Pages

This module provides intelligent HTML extraction that removes navigation,
ads, and boilerplate while preserving station data sections.
"""

from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
import re
from ..utils.logger import logger


class FandomContentExtractor:
    """
    Extract relevant content sections from Fandom wiki HTML.
    Removes navigation, ads, and boilerplate; keeps only station data.
    """
    
    def __init__(self):
        # Section headers that indicate relevant content
        self.relevant_sections = {
            'exits': ['exits', 'exit', 'station exits'],
            'platforms': ['platforms', 'platform', 'platform layout'],
            'bus_stops': ['nearby bus stops', 'bus stops', 'bus interchanges', 'buses'],
            'lines': ['lines', 'line', 'line information'],
            'layout': ['layout', 'station layout'],
        }
        
        # HTML elements to always remove
        self.noise_selectors = [
            'nav', 'header', 'footer', 'aside',
            '.wds-global-navigation', '.wds-community-header',
            '.advertisement', '.ad-slot',
            '.rail-module', '.page-side-tools',
            '.categories', '.page-footer',
            'script', 'style', 'noscript',
        ]
    
    def extract_relevant_content(self, html: str, station_name: str) -> str:
        """
        Extract relevant content from Fandom HTML.
        
        Args:
            html: Raw HTML content from Fandom page
            station_name: Name of the station for logging
            
        Returns:
            Clean HTML string or empty string if extraction fails
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove noise elements
            self._remove_noise(soup)
            
            # Extract main content area
            content = self._extract_main_content(soup)
            if not content:
                logger.warning(f"Could not extract main content for {station_name}")
                return ""
            
            # Find and extract relevant sections
            sections = self._extract_sections(content)
            
            # Format for LLM
            formatted = self._format_for_llm(sections, station_name)
            
            return formatted
            
        except Exception as e:
            logger.error(f"Error extracting content for {station_name}: {e}")
            return ""
    
    def _remove_noise(self, soup: BeautifulSoup) -> None:
        """Remove navigation, ads, and other noise elements."""
        for selector in self.noise_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    element.decompose()
            except Exception:
                # Ignore errors for individual selectors
                pass
    
    def _extract_main_content(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """
        Extract the main content area from the page.
        
        Tries common content containers in order of preference.
        """
        # Try to find the main content area
        content_selectors = [
            'main#content',
            '.mw-parser-output',
            '.page-content',
            'article',
            'main',
            '#content',
            '.content',
            'body'
        ]
        
        for selector in content_selectors:
            content = soup.select_one(selector)
            if content:
                return content
        
        # Fallback: return the body if nothing else found
        return soup.find('body')
    
    def _extract_sections(self, content: BeautifulSoup) -> Dict[str, List[Any]]:
        """
        Extract relevant sections from the main content.
        
        Looks for sections with headers matching relevant keywords.
        """
        sections = {
            'exits': [],
            'platforms': [],
            'bus_stops': [],
            'lines': [],
            'layout': [],
            'other': []
        }
        
        # Find all headers (h2, h3, h4)
        headers = content.find_all(['h2', 'h3', 'h4'])
        
        for header in headers:
            header_text = header.get_text(strip=True).lower()
            
            # Determine which section this belongs to
            section_type = self._classify_section(header_text)
            
            # Extract content until next header
            section_content = []
            current = header.next_sibling
            
            while current and current.name not in ['h2', 'h3', 'h4']:
                if current.name:
                    section_content.append(current)
                current = current.next_sibling
            
            if section_content:
                if section_type == 'exits':
                    sections['exits'].extend(section_content)
                elif section_type == 'platforms':
                    sections['platforms'].extend(section_content)
                elif section_type == 'bus_stops':
                    sections['bus_stops'].extend(section_content)
                elif section_type == 'lines':
                    sections['lines'].extend(section_content)
                elif section_type == 'layout':
                    sections['layout'].extend(section_content)
                else:
                    sections['other'].extend(section_content)
        
        # Also look for tables that might contain exit/bus stop data
        tables = content.find_all('table')
        for table in tables:
            table_text = table.get_text(strip=True).lower()
            
            # Check if table contains exit-related data
            if any(keyword in table_text for keyword in ['exit', 'destination', 'location']):
                if table not in sections['exits']:
                    sections['exits'].append(table)
            
            # Check if table contains bus stop data
            if any(keyword in table_text for keyword in ['bus stop', 'bus service', 'bus no']):
                if table not in sections['bus_stops']:
                    sections['bus_stops'].append(table)
        
        return sections
    
    def _classify_section(self, header_text: str) -> Optional[str]:
        """
        Classify a section header into a known type.
        
        Returns None if not a relevant section.
        """
        header_lower = header_text.lower()
        
        for section_type, keywords in self.relevant_sections.items():
            for keyword in keywords:
                if keyword in header_lower:
                    return section_type
        
        return None
    
    def _format_for_llm(self, sections: Dict[str, List[Any]], station_name: str) -> str:
        """
        Format extracted sections into clean HTML for LLM processing.
        
        Preserves table structures which are crucial for extraction.
        """
        formatted_parts = []
        
        # Add station name as header
        formatted_parts.append(f"<h1>{station_name}</h1>")
        
        # Add exits section
        if sections['exits']:
            formatted_parts.append("<h2>Exits</h2>")
            for element in sections['exits']:
                formatted_parts.append(str(element))
        
        # Add platforms section
        if sections['platforms']:
            formatted_parts.append("<h2>Platforms</h2>")
            for element in sections['platforms']:
                formatted_parts.append(str(element))
        
        # Add bus stops section
        if sections['bus_stops']:
            formatted_parts.append("<h2>Bus Stops</h2>")
            for element in sections['bus_stops']:
                formatted_parts.append(str(element))
        
        # Add lines section
        if sections['lines']:
            formatted_parts.append("<h2>Lines</h2>")
            for element in sections['lines']:
                formatted_parts.append(str(element))
        
        # Add layout section
        if sections['layout']:
            formatted_parts.append("<h2>Layout</h2>")
            for element in sections['layout']:
                formatted_parts.append(str(element))
        
        # Join all parts
        result = "\n".join(formatted_parts)
        
        # Clean up whitespace
        result = re.sub(r'\n+', '\n', result)
        result = re.sub(r'\s+', ' ', result)
        
        return result.strip()
    
    def get_extraction_stats(self, original_html: str, extracted_html: str) -> Dict[str, Any]:
        """
        Get statistics about the extraction process.
        
        Returns:
            Dict with original_size, extracted_size, reduction_percentage
        """
        original_size = len(original_html)
        extracted_size = len(extracted_html)
        
        if original_size > 0:
            reduction_percentage = ((original_size - extracted_size) / original_size) * 100
        else:
            reduction_percentage = 0
        
        return {
            "original_size": original_size,
            "extracted_size": extracted_size,
            "reduction_percentage": round(reduction_percentage, 1),
            "reduction_ratio": round(original_size / max(extracted_size, 1), 1)
        }
