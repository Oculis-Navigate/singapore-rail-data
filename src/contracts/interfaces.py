"""
Abstract interfaces and base classes for MRT Data Pipeline

This module defines the contracts that all pipeline stages must implement,
ensuring consistent behavior and validation across the pipeline.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from .schemas import Stage1Output, Stage2Output, FinalOutput


class PipelineStage(ABC):
    """Abstract base class for all pipeline stages"""
    
    @property
    @abstractmethod
    def stage_name(self) -> str:
        """Return stage name"""
        pass
    
    @abstractmethod
    def execute(self, input_data: Any) -> Any:
        """Execute stage and return output"""
        pass
    
    @abstractmethod
    def validate_input(self, input_data: Any) -> bool:
        """Validate input data before processing"""
        pass
    
    @abstractmethod
    def validate_output(self, output_data: Any) -> bool:
        """Validate output data after processing"""
        pass
    
    @abstractmethod
    def save_checkpoint(self, output: Any, output_dir: str) -> str:
        """Save checkpoint to output directory"""
        pass


class Stage1Interface(PipelineStage):
    """Interface for Stage 1: Deterministic Data Ingestion"""
    
    @property
    def stage_name(self) -> str:
        return "stage1_ingestion"
    
    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Stage1Output:
        """Execute Stage 1 and return Stage1Output"""
        pass
    
    @abstractmethod
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate Stage 1 input configuration"""
        pass
    
    @abstractmethod
    def validate_output(self, output_data: Stage1Output) -> bool:
        """Validate Stage 1 output conforms to schema"""
        pass


class Stage2Interface(PipelineStage):
    """Interface for Stage 2: Enrichment Extraction"""
    
    @property
    def stage_name(self) -> str:
        return "stage2_enrichment"
    
    @abstractmethod
    def execute(self, input_data: Stage1Output) -> Stage2Output:
        """Execute Stage 2 and return Stage2Output"""
        pass
    
    @abstractmethod
    def validate_input(self, input_data: Stage1Output) -> bool:
        """Validate Stage 2 input is valid Stage1Output"""
        pass
    
    @abstractmethod
    def validate_output(self, output_data: Stage2Output) -> bool:
        """Validate Stage 2 output conforms to schema"""
        pass


class Stage3Interface(PipelineStage):
    """Interface for Stage 3: Data Merging & Validation"""

    @property
    def stage_name(self) -> str:
        return "stage3_merger"

    @abstractmethod
    def execute(self, input_data: Tuple[Stage1Output, Stage2Output]) -> FinalOutput:
        """Execute Stage 3 and return FinalOutput"""
        pass

    @abstractmethod
    def validate_input(self, input_data: Tuple[Stage1Output, Stage2Output]) -> bool:
        """Validate Stage 3 input contains required data"""
        pass

    @abstractmethod
    def validate_output(self, output_data: FinalOutput) -> bool:
        """Validate Stage 3 output conforms to schema"""
        pass


class DataFetcher(ABC):
    """Abstract base class for data fetchers"""
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the data source name"""
        pass
    
    @abstractmethod
    def fetch(self, **kwargs) -> Any:
        """Fetch data from the source"""
        pass
    
    @abstractmethod
    def validate_response(self, response: Any) -> bool:
        """Validate the response from the source"""
        pass


class DataProcessor(ABC):
    """Abstract base class for data processors"""
    
    @property
    @abstractmethod
    def processor_name(self) -> str:
        """Return the processor name"""
        pass
    
    @abstractmethod
    def process(self, data: Any) -> Any:
        """Process the data"""
        pass
    
    @abstractmethod
    def validate_result(self, result: Any) -> bool:
        """Validate the processing result"""
        pass