"""
Pipeline registry module for the video ingest tool.

Manages the registration and discovery of pipeline steps.
"""

from typing import Callable, Dict, List, Any, Optional
import structlog
from functools import wraps

from .base import ProcessingPipeline, ProcessingStep

# Global pipeline registry
_pipelines: Dict[str, ProcessingPipeline] = {}
_default_pipeline: Optional[ProcessingPipeline] = None

# Logger
logger = structlog.get_logger(__name__)

def get_pipeline(name: str = "default") -> Optional[ProcessingPipeline]:
    """
    Get a registered pipeline by name.
    
    Args:
        name: Name of the pipeline to get
        
    Returns:
        The pipeline or None if not found
    """
    return _pipelines.get(name)

def get_default_pipeline() -> ProcessingPipeline:
    """
    Get the default pipeline, creating it if it doesn't exist.
    
    Returns:
        The default pipeline
    """
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = ProcessingPipeline(logger=logger)
        _pipelines["default"] = _default_pipeline
    return _default_pipeline

def register_pipeline(name: str, pipeline: ProcessingPipeline) -> None:
    """
    Register a pipeline with a name.
    
    Args:
        name: Name to register the pipeline under
        pipeline: The pipeline to register
    """
    global _default_pipeline
    _pipelines[name] = pipeline
    logger.info(f"Registered pipeline: {name}")
    
    # If this is the first pipeline, also set it as default
    if _default_pipeline is None:
        _default_pipeline = pipeline

def register_step(name: str, enabled: bool = True, description: str = "", pipeline_name: str = "default") -> Callable:
    """
    Decorator to register a function as a pipeline step.
    
    Args:
        name: Name of the step
        enabled: Whether this step is enabled by default
        description: Description of what this step does
        pipeline_name: Name of the pipeline to register with
            
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        # Get or create the pipeline
        pipeline = get_pipeline(pipeline_name)
        if pipeline is None:
            pipeline = ProcessingPipeline(logger=logger)
            register_pipeline(pipeline_name, pipeline)
            
        # Create and add the step
        step = ProcessingStep(name, func, enabled, description)
        pipeline.add_step(step)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
            
        return wrapper
    return decorator

def get_all_steps(pipeline_name: str = "default") -> List[Dict[str, Any]]:
    """
    Get information about all registered steps in a pipeline.
    
    Args:
        pipeline_name: Name of the pipeline to get steps from
        
    Returns:
        List of dictionaries with step information
    """
    pipeline = get_pipeline(pipeline_name)
    if pipeline is None:
        return []
        
    steps = []
    for step in pipeline.steps:
        steps.append({
            "name": step.name,
            "enabled": step.enabled,
            "description": step.description
        })
    return steps

def get_enabled_steps(pipeline_name: str = "default") -> List[Dict[str, Any]]:
    """
    Get information about all enabled steps in a pipeline.
    
    Args:
        pipeline_name: Name of the pipeline to get steps from
        
    Returns:
        List of dictionaries with step information
    """
    pipeline = get_pipeline(pipeline_name)
    if pipeline is None:
        return []
        
    steps = []
    for step in pipeline.get_enabled_steps():
        steps.append({
            "name": step.name,
            "enabled": True,
            "description": step.description
        })
    return steps

def get_disabled_steps(pipeline_name: str = "default") -> List[Dict[str, Any]]:
    """
    Get information about all disabled steps in a pipeline.
    
    Args:
        pipeline_name: Name of the pipeline to get steps from
        
    Returns:
        List of dictionaries with step information
    """
    pipeline = get_pipeline(pipeline_name)
    if pipeline is None:
        return []
        
    steps = []
    for step in pipeline.get_disabled_steps():
        steps.append({
            "name": step.name,
            "enabled": False,
            "description": step.description
        })
    return steps

def get_available_pipeline_steps() -> List[Dict[str, Any]]:
    """
    Get information about all available pipeline steps.
    
    Returns:
        List of dictionaries with step information
    """
    return get_all_steps("default") 