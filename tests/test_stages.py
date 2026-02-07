"""
Test suite for pipeline stage interfaces

This module tests the abstract interfaces and ensures that
pipeline stage implementations follow the required contracts.
"""

import pytest
import sys
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, patch

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.contracts.interfaces import (
    PipelineStage, Stage1Interface, Stage2Interface, Stage3Interface,
    DataFetcher, DataProcessor
)
from src.contracts.schemas import (
    Stage1Output, Stage2Output, FinalOutput,
    Stage1Station, Stage2Station, FinalStation, Exit
)
from src.pipelines.stage1_ingestion import Stage1Ingestion
from src.pipelines.stage2_enrichment import Stage2Enrichment
from src.pipelines.stage3_merger import Stage3Merger
from datetime import datetime


class TestPipelineStage:
    """Test abstract PipelineStage interface"""
    
    def test_abstract_methods(self):
        """Test that PipelineStage cannot be instantiated directly"""
        with pytest.raises(TypeError):
            PipelineStage()
    
    def test_concrete_implementation(self):
        """Test that concrete implementation works"""
        class TestStage(PipelineStage):
            @property
            def stage_name(self) -> str:
                return "test_stage"
            
            def execute(self, input_data: Any) -> Any:
                return input_data
            
            def validate_input(self, input_data: Any) -> bool:
                return True
            
            def validate_output(self, output_data: Any) -> bool:
                return True
        
        stage = TestStage()
        assert stage.stage_name == "test_stage"
        assert stage.execute("test") == "test"
        assert stage.validate_input("test") is True
        assert stage.validate_output("test") is True


class TestStage1Interface:
    """Test Stage1Interface abstract class"""
    
    def test_stage_name(self):
        """Test that stage name is correct"""
        assert Stage1Interface.stage_name == "stage1_ingestion"
    
    def test_abstract_methods(self):
        """Test that Stage1Interface cannot be instantiated directly"""
        with pytest.raises(TypeError):
            Stage1Interface()


class TestStage2Interface:
    """Test Stage2Interface abstract class"""
    
    def test_stage_name(self):
        """Test that stage name is correct"""
        assert Stage2Interface.stage_name == "stage2_enrichment"
    
    def test_abstract_methods(self):
        """Test that Stage2Interface cannot be instantiated directly"""
        with pytest.raises(TypeError):
            Stage2Interface()


class TestStage3Interface:
    """Test Stage3Interface abstract class"""
    
    def test_stage_name(self):
        """Test that stage name is correct"""
        assert Stage3Interface.stage_name == "stage3_merger"
    
    def test_abstract_methods(self):
        """Test that Stage3Interface cannot be instantiated directly"""
        with pytest.raises(TypeError):
            Stage3Interface()


class TestDataFetcher:
    """Test DataFetcher abstract class"""
    
    def test_abstract_methods(self):
        """Test that DataFetcher cannot be instantiated directly"""
        with pytest.raises(TypeError):
            DataFetcher()
    
    def test_concrete_implementation(self):
        """Test that concrete implementation works"""
        class TestFetcher(DataFetcher):
            @property
            def source_name(self) -> str:
                return "test_source"
            
            def fetch(self, **kwargs) -> Any:
                return {"data": "test"}
            
            def validate_response(self, response: Any) -> bool:
                return "data" in response
        
        fetcher = TestFetcher()
        assert fetcher.source_name == "test_source"
        assert fetcher.fetch() == {"data": "test"}
        assert fetcher.validate_response({"data": "test"}) is True


class TestDataProcessor:
    """Test DataProcessor abstract class"""
    
    def test_abstract_methods(self):
        """Test that DataProcessor cannot be instantiated directly"""
        with pytest.raises(TypeError):
            DataProcessor()
    
    def test_concrete_implementation(self):
        """Test that concrete implementation works"""
        class TestProcessor(DataProcessor):
            @property
            def processor_name(self) -> str:
                return "test_processor"
            
            def process(self, data: Any) -> Any:
                return {"processed": data}
            
            def validate_result(self, result: Any) -> bool:
                return "processed" in result
        
        processor = TestProcessor()
        assert processor.processor_name == "test_processor"
        assert processor.process("test") == {"processed": "test"}
        assert processor.validate_result({"processed": "test"}) is True


class TestStage1Ingestion:
    """Test Stage1Ingestion implementation"""
    
    def test_stage_name(self):
        """Test that stage name is correct"""
        stage = Stage1Ingestion()
        assert stage.stage_name == "stage1_ingestion"
    
    def test_validate_input_default(self):
        """Test default input validation"""
        stage = Stage1Ingestion()
        # Default implementation should return True
        assert stage.validate_input({}) is True
    
    def test_validate_output_default(self):
        """Test default output validation"""
        stage = Stage1Ingestion()
        # Create a valid Stage1Output
        exit = Exit(exit_code="A", lat=1.3521, lng=103.8198, source="onemap")
        station = Stage1Station(
            station_id="NS13",
            official_name="YISHUN MRT STATION",
            display_name="Yishun",
            mrt_codes=["NS13"],
            lines=["NSL"],
            station_type="mrt",
            exits=[exit],
            fandom_url="https://example.com"
        )
        output = Stage1Output(metadata={}, stations=[station])
        
        # Default implementation should return True
        assert stage.validate_output(output) is True


class TestStage2Enrichment:
    """Test Stage2Enrichment implementation"""
    
    def test_stage_name(self):
        """Test that stage name is correct"""
        stage = Stage2Enrichment()
        assert stage.stage_name == "stage2_enrichment"
    
    def test_validate_input_default(self):
        """Test default input validation"""
        stage = Stage2Enrichment()
        # Create a valid Stage1Output
        exit = Exit(exit_code="A", lat=1.3521, lng=103.8198, source="onemap")
        station = Stage1Station(
            station_id="NS13",
            official_name="YISHUN MRT STATION",
            display_name="Yishun",
            mrt_codes=["NS13"],
            lines=["NSL"],
            station_type="mrt",
            exits=[exit],
            fandom_url="https://example.com"
        )
        input_data = Stage1Output(metadata={}, stations=[station])
        
        # Default implementation should return True
        assert stage.validate_input(input_data) is True
    
    def test_validate_output_default(self):
        """Test default output validation"""
        stage = Stage2Enrichment()
        # Create a valid Stage2Output
        station = Stage2Station(
            station_id="NS13",
            official_name="YISHUN MRT STATION",
            extraction_result="success",
            exits=[],
            extraction_timestamp=datetime.now(),
            source_url="https://example.com"
        )
        output = Stage2Output(
            metadata={},
            stations={"NS13": station},
            failed_stations=[],
            retry_queue=[]
        )
        
        # Default implementation should return True
        assert stage.validate_output(output) is True


class TestStage3Merger:
    """Test Stage3Merger implementation"""
    
    def test_stage_name(self):
        """Test that stage name is correct"""
        stage = Stage3Merger()
        assert stage.stage_name == "stage3_merger"
    
    def test_validate_input_default(self):
        """Test default input validation"""
        stage = Stage3Merger()
        # Default implementation should return True
        assert stage.validate_input({}) is True
    
    def test_validate_output_default(self):
        """Test default output validation"""
        stage = Stage3Merger()
        # Create a valid FinalOutput
        exit = FinalExit(exit_code="A", lat=1.3521, lng=103.8198)
        station = FinalStation(
            official_name="YISHUN MRT STATION",
            mrt_codes=["NS13"],
            exits=[exit]
        )
        output = FinalOutput(metadata={}, stations=[station])
        
        # Default implementation should return True
        assert stage.validate_output(output) is True


class TestInterfaceContracts:
    """Test that interfaces enforce proper contracts"""
    
    def test_stage1_interface_contract(self):
        """Test that Stage1Interface enforces proper input/output types"""
        class TestStage1(Stage1Interface):
            @property
            def stage_name(self) -> str:
                return "test_stage1"
            
            def execute(self, input_data: Dict[str, Any]) -> Stage1Output:
                # Should return Stage1Output
                exit = Exit(exit_code="A", lat=1.3521, lng=103.8198, source="onemap")
                station = Stage1Station(
                    station_id="NS13",
                    official_name="YISHUN MRT STATION",
                    display_name="Yishun",
                    mrt_codes=["NS13"],
                    lines=["NSL"],
                    station_type="mrt",
                    exits=[exit],
                    fandom_url="https://example.com"
                )
                return Stage1Output(metadata={}, stations=[station])
            
            def validate_input(self, input_data: Dict[str, Any]) -> bool:
                return isinstance(input_data, dict)
            
            def validate_output(self, output_data: Stage1Output) -> bool:
                return isinstance(output_data, Stage1Output)
        
        stage = TestStage1()
        assert stage.validate_input({}) is True
        assert stage.validate_input("invalid") is False
        
        output = stage.execute({})
        assert stage.validate_output(output) is True
    
    def test_stage2_interface_contract(self):
        """Test that Stage2Interface enforces proper input/output types"""
        class TestStage2(Stage2Interface):
            @property
            def stage_name(self) -> str:
                return "test_stage2"
            
            def execute(self, input_data: Stage1Output) -> Stage2Output:
                # Should return Stage2Output
                station = Stage2Station(
                    station_id="NS13",
                    official_name="YISHUN MRT STATION",
                    extraction_result="success",
                    exits=[],
                    extraction_timestamp=datetime.now(),
                    source_url="https://example.com"
                )
                return Stage2Output(
                    metadata={},
                    stations={"NS13": station},
                    failed_stations=[],
                    retry_queue=[]
                )
            
            def validate_input(self, input_data: Stage1Output) -> bool:
                return isinstance(input_data, Stage1Output)
            
            def validate_output(self, output_data: Stage2Output) -> bool:
                return isinstance(output_data, Stage2Output)
        
        stage = TestStage2()
        
        # Create valid input
        exit = Exit(exit_code="A", lat=1.3521, lng=103.8198, source="onemap")
        station = Stage1Station(
            station_id="NS13",
            official_name="YISHUN MRT STATION",
            display_name="Yishun",
            mrt_codes=["NS13"],
            lines=["NSL"],
            station_type="mrt",
            exits=[exit],
            fandom_url="https://example.com"
        )
        valid_input = Stage1Output(metadata={}, stations=[station])
        
        assert stage.validate_input(valid_input) is True
        assert stage.validate_input("invalid") is False
        
        output = stage.execute(valid_input)
        assert stage.validate_output(output) is True


if __name__ == "__main__":
    # Run tests when executed directly
    pytest.main([__file__, "-v"])