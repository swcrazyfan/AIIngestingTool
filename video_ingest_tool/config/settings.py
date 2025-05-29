"""
Settings management for the video ingest tool.

Provides configuration handling and management.
"""

from typing import Dict, Any, Optional, List

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


# Single source of truth for all pipeline step definitions
PIPELINE_STEP_DEFINITIONS = [
    # Processing steps (first in pipeline)
    {
        'name': 'generate_checksum_step',
        'category': 'Processing',
        'description': 'Generate file checksum for deduplication',
        'enabled_by_default': True
    },
    {
        'name': 'check_duplicate_step', 
        'category': 'Processing',
        'description': 'Check for duplicate files in database',
        'enabled_by_default': True
    },
    {
        'name': 'video_compression_step',
        'category': 'Processing', 
        'description': 'Compress video for AI analysis',
        'enabled_by_default': True
    },
    
    # Extraction steps (parallel)
    {
        'name': 'extract_mediainfo_step',
        'category': 'Extraction',
        'description': 'Extract metadata using MediaInfo library',
        'enabled_by_default': True
    },
    {
        'name': 'extract_ffprobe_step',
        'category': 'Extraction',
        'description': 'Extract metadata using FFprobe/PyAV',
        'enabled_by_default': True
    },
    {
        'name': 'extract_exiftool_step',
        'category': 'Extraction',
        'description': 'Extract basic EXIF metadata using ExifTool',
        'enabled_by_default': True
    },
    {
        'name': 'extract_extended_exif_step',
        'category': 'Extraction',
        'description': 'Extract extended EXIF metadata',
        'enabled_by_default': True
    },
    {
        'name': 'extract_codec_step',
        'category': 'Extraction',
        'description': 'Extract detailed codec parameters',
        'enabled_by_default': True
    },
    {
        'name': 'extract_hdr_step',
        'category': 'Extraction',
        'description': 'Extract HDR metadata from video files',
        'enabled_by_default': True
    },
    {
        'name': 'extract_audio_step',
        'category': 'Extraction',
        'description': 'Extract audio track information',
        'enabled_by_default': True
    },
    {
        'name': 'extract_subtitle_step',
        'category': 'Extraction',
        'description': 'Extract subtitle track information',
        'enabled_by_default': True
    },
    
    # Analysis steps
    {
        'name': 'generate_thumbnails_step',
        'category': 'Analysis',
        'description': 'Generate thumbnails from video file',
        'enabled_by_default': True
    },
    {
        'name': 'analyze_exposure_step',
        'category': 'Analysis',
        'description': 'Analyze exposure in thumbnails',
        'enabled_by_default': True
    },
    {
        'name': 'detect_focal_length_step',
        'category': 'Analysis',
        'description': 'Detect focal length using AI when EXIF unavailable',
        'enabled_by_default': True
    },
    {
        'name': 'ai_video_analysis_step',
        'category': 'Analysis',
        'description': 'Perform AI analysis of video content',
        'enabled_by_default': True
    },
    {
        'name': 'ai_thumbnail_selection_step',
        'category': 'Analysis',
        'description': 'Select best thumbnails using AI analysis',
        'enabled_by_default': True
    },
    
    # Final processing steps
    {
        'name': 'consolidate_metadata_step',
        'category': 'Processing',
        'description': 'Consolidate metadata from all sources',
        'enabled_by_default': True
    },
    
    # Storage steps
    {
        'name': 'create_model_step',
        'category': 'Storage',
        'description': 'Create Pydantic models from processed data',
        'enabled_by_default': True
    },
    {
        'name': 'database_storage_step',
        'category': 'Storage',
        'description': 'Store video data in Supabase database',
        'enabled_by_default': True
    },
    {
        'name': 'generate_embeddings_step',
        'category': 'Storage',
        'description': 'Generate vector embeddings for semantic search',
        'enabled_by_default': True
    },
    {
        'name': 'upload_thumbnails_step',
        'category': 'Storage',
        'description': 'Upload thumbnails to Supabase storage',
        'enabled_by_default': True
    }
]


def get_default_pipeline_config() -> Dict[str, Any]:
    """
    Get the default configuration for all pipeline steps.
    
    Returns:
        Dict[str, Any]: Dictionary of step names and their enabled state
    """
    return {
        step_def['name']: step_def['enabled_by_default'] 
        for step_def in PIPELINE_STEP_DEFINITIONS
    }


def get_available_pipeline_steps() -> List[Dict[str, Any]]:
    """
    Get information about all available pipeline steps from the current Prefect tasks.
    
    Returns:
        List[Dict[str, Any]]: List of step information with name, enabled status, and description
    """
    # Get default config to determine enabled status
    default_config = get_default_pipeline_config()
    
    # Build the step list with enabled status from our single source of truth
    available_steps = []
    for step_def in PIPELINE_STEP_DEFINITIONS:
        step_name = step_def['name']
        enabled = default_config.get(step_name, True)  # Default to enabled
        
        available_steps.append({
            'name': step_name,
            'enabled': enabled,
            'description': f"[{step_def['category']}] {step_def['description']}",
            'category': step_def['category']
        })
    
    return available_steps 