"""
Configuration management for the pipeline.
"""

import os
from typing import Any, Optional
import yaml

class PipelineConfig:
    """Configuration manager with dot notation access"""
    
    def __init__(self, config_path: str = "config/pipeline.yaml"):
        self._config = self._load_config(config_path)
    
    def _load_config(self, path: str) -> dict:
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot notation (e.g., 'stages.stage1.batch_size')"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value
    
    def __getitem__(self, key: str) -> Any:
        return self.get(key)
    
    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None
    
    @property
    def pipeline(self) -> dict:
        return self._config.get('pipeline', {})
    
    @property
    def stages(self) -> dict:
        return self._config.get('stages', {})
    
    @property
    def apis(self) -> dict:
        return self._config.get('apis', {})

# Singleton instance
_config_instance = None

def get_config(config_path: Optional[str] = None) -> PipelineConfig:
    """Get or create config singleton"""
    global _config_instance
    if _config_instance is None or config_path:
        path = config_path or os.getenv('PIPELINE_CONFIG') or 'config/pipeline.yaml'
        _config_instance = PipelineConfig(path)
    return _config_instance