"""
Configuration management CLI commands.

Provides commands to view, edit, and validate search configuration.
"""

from typing import Optional, Dict, Any
import structlog
from ..config.search_config import get_search_config_manager, get_search_config, SearchConfig

logger = structlog.get_logger(__name__)


class ConfigCommand:
    """Command for managing search configuration."""
    
    def execute(self, action: str, **kwargs) -> Dict[str, Any]:
        """
        Execute configuration management action.
        
        Args:
            action: Action to perform ('show', 'set', 'reset', 'validate')
            **kwargs: Action-specific parameters
            
        Returns:
            Dict with execution results
        """
        try:
            if action == 'show':
                return self.show_config(**kwargs)
            elif action == 'set':
                return self.set_parameter(**kwargs)
            elif action == 'reset':
                return self.reset_config(**kwargs)
            elif action == 'validate':
                return self.validate_config(**kwargs)
            else:
                return {
                    'success': False,
                    'error': f"Unknown action: {action}. Available: show, set, reset, validate"
                }
        except Exception as e:
            logger.error("Config command failed", action=action, error=str(e))
            return {
                'success': False,
                'error': f"Command failed: {str(e)}"
            }
    
    def show_config(self, parameter: Optional[str] = None, sources: bool = False) -> Dict[str, Any]:
        """
        Show current search configuration.
        
        Args:
            parameter: Specific parameter to show (optional)
            sources: Whether to show parameter sources
            
        Returns:
            Dict with configuration data
        """
        try:
            config_manager = get_search_config_manager()
            config = config_manager.get_config()
            
            if parameter:
                # Show specific parameter
                if hasattr(config, parameter):
                    value = getattr(config, parameter)
                    result = {
                        'success': True,
                        'data': {
                            'parameter': parameter,
                            'value': value
                        }
                    }
                    
                    if sources:
                        source = config_manager.get_parameter_source(parameter)
                        result['data']['source'] = source
                    
                    return result
                else:
                    return {
                        'success': False,
                        'error': f"Unknown parameter: {parameter}"
                    }
            else:
                # Show all configuration
                config_dict = config.to_dict()
                result = {
                    'success': True,
                    'data': {
                        'config': config_dict,
                        'config_file': config_manager.config_file_path,
                        'file_exists': config_manager._load_file_config() != {}
                    }
                }
                
                if sources:
                    sources_dict = {}
                    for param_name in config_dict.keys():
                        sources_dict[param_name] = config_manager.get_parameter_source(param_name)
                    result['data']['sources'] = sources_dict
                
                return result
                
        except Exception as e:
            logger.error("Failed to show config", parameter=parameter, error=str(e))
            return {
                'success': False,
                'error': f"Failed to show config: {str(e)}"
            }
    
    def set_parameter(self, parameter: str, value: Any, save: bool = True) -> Dict[str, Any]:
        """
        Set a configuration parameter.
        
        Args:
            parameter: Parameter name to set
            value: Value to set
            save: Whether to save to file
            
        Returns:
            Dict with execution results
        """
        try:
            config_manager = get_search_config_manager()
            current_config = config_manager.get_config()
            
            # Validate parameter exists
            if not hasattr(current_config, parameter):
                available_params = list(current_config.to_dict().keys())
                return {
                    'success': False,
                    'error': f"Unknown parameter: {parameter}. Available: {', '.join(available_params)}"
                }
            
            # Convert value to appropriate type
            current_value = getattr(current_config, parameter)
            if isinstance(current_value, float):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    return {
                        'success': False,
                        'error': f"Parameter {parameter} requires a float value, got: {value}"
                    }
            elif isinstance(current_value, int):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    return {
                        'success': False,
                        'error': f"Parameter {parameter} requires an integer value, got: {value}"
                    }
            
            # Create new config with updated parameter
            config_dict = current_config.to_dict()
            config_dict[parameter] = value
            
            new_config = SearchConfig.from_dict(config_dict)
            
            # Validate new configuration
            if not new_config.validate():
                return {
                    'success': False,
                    'error': f"New configuration is invalid. Check parameter value: {parameter}={value}"
                }
            
            result = {
                'success': True,
                'data': {
                    'parameter': parameter,
                    'old_value': current_value,
                    'new_value': value,
                    'saved_to_file': False
                }
            }
            
            # Save to file if requested
            if save:
                if config_manager.save_config(new_config):
                    result['data']['saved_to_file'] = True
                    logger.info("Updated search configuration parameter", 
                               parameter=parameter, 
                               old_value=current_value, 
                               new_value=value)
                else:
                    result['success'] = False
                    result['error'] = "Failed to save configuration to file"
            
            return result
            
        except Exception as e:
            logger.error("Failed to set parameter", parameter=parameter, value=value, error=str(e))
            return {
                'success': False,
                'error': f"Failed to set parameter: {str(e)}"
            }
    
    def reset_config(self, confirm: bool = False) -> Dict[str, Any]:
        """
        Reset configuration to defaults.
        
        Args:
            confirm: Whether user confirmed the reset
            
        Returns:
            Dict with execution results
        """
        try:
            if not confirm:
                return {
                    'success': False,
                    'error': "Reset requires confirmation. Use --confirm flag."
                }
            
            config_manager = get_search_config_manager()
            default_config = SearchConfig()  # Create fresh default config
            
            if config_manager.save_config(default_config):
                logger.info("Reset search configuration to defaults")
                return {
                    'success': True,
                    'data': {
                        'message': "Configuration reset to defaults",
                        'config': default_config.to_dict()
                    }
                }
            else:
                return {
                    'success': False,
                    'error': "Failed to save default configuration"
                }
                
        except Exception as e:
            logger.error("Failed to reset config", error=str(e))
            return {
                'success': False,
                'error': f"Failed to reset config: {str(e)}"
            }
    
    def validate_config(self) -> Dict[str, Any]:
        """
        Validate current configuration.
        
        Returns:
            Dict with validation results
        """
        try:
            config = get_search_config()
            is_valid = config.validate()
            
            return {
                'success': True,
                'data': {
                    'valid': is_valid,
                    'config': config.to_dict()
                }
            }
            
        except Exception as e:
            logger.error("Failed to validate config", error=str(e))
            return {
                'success': False,
                'error': f"Failed to validate config: {str(e)}"
            } 