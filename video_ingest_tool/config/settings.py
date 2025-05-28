"""
Settings management for the video ingest tool.

Provides configuration handling and management.
"""

from typing import Dict, Any, Optional
from ..pipeline.registry import get_default_pipeline

class Config:
    """
    A simple configuration class to hold and provide settings.
    """
    def __init__(self, config_data: Dict[str, Any] = None):
        """
        Initialize the configuration.
        
        Args:
            config_data: Initial configuration data
        """
        self._config = config_data if config_data is not None else {}

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Retrieves a setting value by key.
        Uses dot notation for nested keys (e.g., 'processors.video.enabled').
        
        Args:
            key: The key to retrieve
            default: Default value if key is not found
            
        Returns:
            The setting value or default
        """
        keys = key.split('.')
        value = self._config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set_setting(self, key: str, value: Any) -> None:
        """
        Sets a setting value by key.
        Uses dot notation for nested keys.
        
        Args:
            key: The key to set
            value: The value to set
        """
        keys = key.split('.')
        d = self._config
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value

    def update_config(self, new_config_data: Dict[str, Any]) -> None:
        """
        Merges new configuration data into the existing configuration.
        
        Args:
            new_config_data: New configuration data to merge
        """
        def _deep_update(source: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
            for key, value in overrides.items():
                if isinstance(value, dict) and key in source and isinstance(source[key], dict):
                    _deep_update(source[key], value)
                else:
                    source[key] = value
            return source
        self._config = _deep_update(self._config, new_config_data)

    def __repr__(self) -> str:
        return f"Config(config_data={self._config})"

def get_default_pipeline_config() -> Dict[str, bool]:
    """
    Get the default configuration for all pipeline steps.
    
    Returns:
        Dict[str, bool]: Dictionary of step names and their enabled state
    """
    pipeline = get_default_pipeline()
    
    # Create a configuration dictionary based on the current pipeline state
    config = {}
    for step in pipeline.steps:
        config[step.name] = step.enabled
    # If AI analysis is enabled, also enable video_compression
    if config.get('ai_video_analysis'):
        config['video_compression'] = True
    return config 