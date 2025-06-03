"""
Centralized Search Configuration System

Provides a single source of truth for all search parameters with proper
override hierarchy: Code Defaults → Config File → Environment → CLI → API
"""

import os
import json
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import structlog

logger = structlog.get_logger(__name__)

@dataclass
class SearchConfig:
    """
    Complete search configuration with all parameters in one place.
    All search functions should use this instead of hardcoded defaults.
    """
    
    # === CORE SEARCH PARAMETERS ===
    
    # Result limits
    default_match_count: int = 10
    max_match_count: int = 100
    
    # === SEMANTIC SEARCH ===
    summary_weight: float = 1.0          # Summary embedding weight
    keyword_weight: float = 0.8          # Keyword embedding weight  
    similarity_threshold: float = 0.3    # Minimum similarity for semantic search
    
    # === HYBRID SEARCH ===
    fulltext_weight: float = 2.5         # Full-text search weight in hybrid
    rrf_k: int = 50                      # Reciprocal Rank Fusion constant
    
    # === SIMILAR SEARCH ===
    similar_threshold: float = 0.3       # Minimum similarity for similar search
    
    # Similar search text weights
    text_summary_weight: float = 0.5
    text_keyword_weight: float = 0.5
    
    # Similar search visual weights (cross-slot comparison)
    visual_thumb1_weight: float = 0.4
    visual_thumb2_weight: float = 0.3
    visual_thumb3_weight: float = 0.3
    
    # Combined mode factors
    combined_mode_text_factor: float = 0.6
    combined_mode_visual_factor: float = 0.4
    
    # Multi-modal embedding weights for find_similar
    visual_embedding_weight: float = 0.5    # Overall visual weight
    summary_embedding_weight: float = 0.3   # Overall summary weight  
    keyword_embedding_weight: float = 0.2   # Overall keyword weight
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SearchConfig':
        """Create from dictionary, ignoring unknown keys."""
        # Filter to only known fields
        known_fields = set(field.name for field in cls.__dataclass_fields__.values())
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered_data)
    
    def validate(self) -> bool:
        """Validate configuration values are reasonable."""
        errors = []
        
        # Check weights are positive
        weight_fields = [
            'summary_weight', 'keyword_weight', 'fulltext_weight',
            'text_summary_weight', 'text_keyword_weight',
            'visual_thumb1_weight', 'visual_thumb2_weight', 'visual_thumb3_weight',
            'combined_mode_text_factor', 'combined_mode_visual_factor',
            'visual_embedding_weight', 'summary_embedding_weight', 'keyword_embedding_weight'
        ]
        
        for field in weight_fields:
            value = getattr(self, field)
            if value < 0:
                errors.append(f"{field} must be non-negative, got {value}")
        
        # Check thresholds are in valid range
        threshold_fields = ['similarity_threshold', 'similar_threshold']
        for field in threshold_fields:
            value = getattr(self, field)
            if not (0 <= value <= 1):
                errors.append(f"{field} must be between 0 and 1, got {value}")
        
        # Check counts are positive
        if self.default_match_count <= 0:
            errors.append(f"default_match_count must be positive, got {self.default_match_count}")
        if self.max_match_count <= 0:
            errors.append(f"max_match_count must be positive, got {self.max_match_count}")
        if self.default_match_count > self.max_match_count:
            errors.append(f"default_match_count ({self.default_match_count}) cannot exceed max_match_count ({self.max_match_count})")
        
        # Check combined mode factors sum appropriately
        if abs(self.combined_mode_text_factor + self.combined_mode_visual_factor - 1.0) > 0.01:
            logger.warning(
                "Combined mode factors don't sum to 1.0",
                text_factor=self.combined_mode_text_factor,
                visual_factor=self.combined_mode_visual_factor,
                total=self.combined_mode_text_factor + self.combined_mode_visual_factor
            )
        
        if errors:
            for error in errors:
                logger.error("Search config validation error", error=error)
            return False
        
        return True


class SearchConfigManager:
    """
    Manages search configuration with proper override hierarchy.
    
    Priority Order (highest to lowest):
    5. Runtime overrides (API/CLI parameters)
    4. Environment variables  
    3. Config file
    2. Code defaults
    """
    
    def __init__(self, config_file_path: Optional[str] = None):
        self.config_file_path = config_file_path or self._get_default_config_path()
        self._base_config = SearchConfig()  # Code defaults
        self._file_config = self._load_file_config()
        self._env_config = self._load_env_config()
        
        # Build effective config by layering overrides
        self._effective_config = self._build_effective_config()
        
        # Validate the final configuration
        if not self._effective_config.validate():
            logger.warning("Search configuration has validation errors, proceeding with caution")
    
    def _get_default_config_path(self) -> str:
        """Get the default config file path."""
        # Use the root config directory (consolidate to one location)
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'config',
            'search_params.json'
        )
    
    def _load_file_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        if not os.path.exists(self.config_file_path):
            logger.info("Search config file not found, using defaults", path=self.config_file_path)
            return {}
        
        try:
            with open(self.config_file_path, 'r') as f:
                data = json.load(f)
                logger.info("Loaded search config from file", path=self.config_file_path, params=len(data))
                return data
        except Exception as e:
            logger.error("Failed to load search config file", path=self.config_file_path, error=str(e))
            return {}
    
    def _load_env_config(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        env_config = {}
        
        # Map environment variables to config field names
        env_mapping = {
            'SEARCH_DEFAULT_MATCH_COUNT': ('default_match_count', int),
            'SEARCH_MAX_MATCH_COUNT': ('max_match_count', int),
            'SEARCH_SUMMARY_WEIGHT': ('summary_weight', float),
            'SEARCH_KEYWORD_WEIGHT': ('keyword_weight', float),
            'SEARCH_SIMILARITY_THRESHOLD': ('similarity_threshold', float),
            'SEARCH_FULLTEXT_WEIGHT': ('fulltext_weight', float),
            'SEARCH_RRF_K': ('rrf_k', int),
            'SEARCH_SIMILAR_THRESHOLD': ('similar_threshold', float),
            'SEARCH_TEXT_SUMMARY_WEIGHT': ('text_summary_weight', float),
            'SEARCH_TEXT_KEYWORD_WEIGHT': ('text_keyword_weight', float),
            'SEARCH_VISUAL_THUMB1_WEIGHT': ('visual_thumb1_weight', float),
            'SEARCH_VISUAL_THUMB2_WEIGHT': ('visual_thumb2_weight', float),
            'SEARCH_VISUAL_THUMB3_WEIGHT': ('visual_thumb3_weight', float),
            'SEARCH_COMBINED_TEXT_FACTOR': ('combined_mode_text_factor', float),
            'SEARCH_COMBINED_VISUAL_FACTOR': ('combined_mode_visual_factor', float),
            'SEARCH_VISUAL_EMBEDDING_WEIGHT': ('visual_embedding_weight', float),
            'SEARCH_SUMMARY_EMBEDDING_WEIGHT': ('summary_embedding_weight', float),
            'SEARCH_KEYWORD_EMBEDDING_WEIGHT': ('keyword_embedding_weight', float),
        }
        
        for env_var, (field_name, field_type) in env_mapping.items():
            if env_var in os.environ:
                try:
                    value = field_type(os.environ[env_var])
                    env_config[field_name] = value
                    logger.info("Using environment override", field=field_name, value=value, source=env_var)
                except (ValueError, TypeError) as e:
                    logger.warning("Invalid environment variable value", var=env_var, value=os.environ[env_var], error=str(e))
        
        return env_config
    
    def _build_effective_config(self) -> SearchConfig:
        """Build the effective configuration by layering overrides."""
        # Start with base defaults
        config_dict = self._base_config.to_dict()
        
        # Apply file overrides
        config_dict.update(self._file_config)
        
        # Apply environment overrides  
        config_dict.update(self._env_config)
        
        return SearchConfig.from_dict(config_dict)
    
    def get_config(self, overrides: Optional[Dict[str, Any]] = None) -> SearchConfig:
        """
        Get search configuration with optional runtime overrides.
        
        Args:
            overrides: Optional dictionary of parameter overrides (from CLI/API)
            
        Returns:
            SearchConfig with all overrides applied
        """
        if not overrides:
            return self._effective_config
        
        # Apply runtime overrides
        config_dict = self._effective_config.to_dict()
        config_dict.update(overrides)
        
        runtime_config = SearchConfig.from_dict(config_dict)
        
        # Validate runtime config
        if not runtime_config.validate():
            logger.warning("Runtime search config has validation errors", overrides=overrides)
        
        return runtime_config
    
    def save_config(self, config: Union[SearchConfig, Dict[str, Any]]) -> bool:
        """
        Save configuration to file.
        
        Args:
            config: SearchConfig instance or dictionary of parameters
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_file_path), exist_ok=True)
            
            # Convert to dict if needed
            if isinstance(config, SearchConfig):
                config_dict = config.to_dict()
            else:
                config_dict = config
            
            # Write to file
            with open(self.config_file_path, 'w') as f:
                json.dump(config_dict, f, indent=2, sort_keys=True)
            
            logger.info("Saved search configuration", path=self.config_file_path)
            
            # Reload the configuration
            self._file_config = self._load_file_config()
            self._effective_config = self._build_effective_config()
            
            return True
        except Exception as e:
            logger.error("Failed to save search configuration", error=str(e))
            return False
    
    def get_parameter_source(self, parameter_name: str) -> str:
        """
        Get the source of a specific parameter value.
        
        Returns: 'code_default', 'file', 'environment', or 'unknown'
        """
        if parameter_name in self._env_config:
            return 'environment'
        elif parameter_name in self._file_config:
            return 'file'
        elif hasattr(self._base_config, parameter_name):
            return 'code_default'
        else:
            return 'unknown'
    
    def print_config_summary(self):
        """Print a summary of the current configuration and sources."""
        config = self._effective_config
        
        print("🔍 Search Configuration Summary")
        print("=" * 50)
        
        for field_name, field_value in config.to_dict().items():
            source = self.get_parameter_source(field_name)
            print(f"{field_name:30} = {field_value:10} ({source})")
        
        print(f"\nConfig file: {self.config_file_path}")
        print(f"File exists: {os.path.exists(self.config_file_path)}")


# Global instance - import this in other modules
_config_manager = None

def get_search_config_manager() -> SearchConfigManager:
    """Get the global search configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = SearchConfigManager()
    return _config_manager

def get_search_config(overrides: Optional[Dict[str, Any]] = None) -> SearchConfig:
    """
    Convenience function to get search configuration.
    
    Args:
        overrides: Optional runtime overrides (from CLI/API)
        
    Returns:
        SearchConfig with all appropriate overrides applied
    """
    return get_search_config_manager().get_config(overrides)

# Legacy compatibility function
def get_search_params(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Legacy compatibility function for existing code.
    Returns dict instead of SearchConfig object.
    """
    return get_search_config(overrides).to_dict() 