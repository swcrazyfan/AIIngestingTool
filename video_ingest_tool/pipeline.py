"""
Pipeline manager for the video ingest tool.

Defines the processing pipeline with configurable steps.
"""

from typing import List, Dict, Any, Callable, Optional, Union
import structlog
import inspect

class ProcessingStep:
    """
    Represents a single step in the video processing pipeline.
    
    Each step has a name, function to execute, and can be enabled/disabled.
    """
    
    def __init__(self, name: str, func: Callable, enabled: bool = True, description: str = ""):
        """
        Initialize a processing step.
        
        Args:
            name: Name of the step
            func: Function to execute for this step
            enabled: Whether this step is enabled by default
            description: Description of what this step does
        """
        self.name = name
        self.func = func
        self.enabled = enabled
        self.description = description
        # Store the parameter names this function accepts
        self.param_names = set(inspect.signature(func).parameters.keys())
    
    def execute(self, *args, **kwargs):
        """
        Execute this step if it's enabled.
        
        Args:
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            The result of the function or None if the step is disabled
        """
        if not self.enabled:
            return None
        
        # Filter kwargs to only include those the function accepts
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in self.param_names}
        
        return self.func(*args, **filtered_kwargs)
    
    def __repr__(self):
        return f"<ProcessingStep name={self.name} enabled={self.enabled}>"

class ProcessingPipeline:
    """
    Manages a pipeline of processing steps for video files.
    
    Allows for configurable steps that can be enabled/disabled.
    """
    
    def __init__(self, logger=None):
        """
        Initialize the processing pipeline.
        
        Args:
            logger: Logger instance
        """
        self.steps: List[ProcessingStep] = []
        self.logger = logger or structlog.get_logger(__name__)
    
    def add_step(self, step: ProcessingStep) -> None:
        """
        Add a step to the pipeline.
        
        Args:
            step: The step to add
        """
        self.steps.append(step)
        self.logger.info(f"Added step to pipeline: {step.name}", enabled=step.enabled)
    
    def add_steps(self, steps: List[ProcessingStep]) -> None:
        """
        Add multiple steps to the pipeline.
        
        Args:
            steps: List of steps to add
        """
        for step in steps:
            self.add_step(step)
    
    def register_step(self, name: str, enabled: bool = True, description: str = "") -> Callable:
        """
        Decorator to register a function as a pipeline step.
        
        Args:
            name: Name of the step
            enabled: Whether this step is enabled by default
            description: Description of what this step does
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            self.add_step(ProcessingStep(name, func, enabled, description))
            return func
        return decorator
    
    def enable_step(self, name: str) -> None:
        """
        Enable a step by name.
        
        Args:
            name: Name of the step to enable
        """
        for step in self.steps:
            if step.name == name:
                step.enabled = True
                self.logger.info(f"Enabled step: {name}")
                return
        self.logger.warning(f"Step not found: {name}")
    
    def disable_step(self, name: str) -> None:
        """
        Disable a step by name.
        
        Args:
            name: Name of the step to disable
        """
        for step in self.steps:
            if step.name == name:
                step.enabled = False
                self.logger.info(f"Disabled step: {name}")
                return
        self.logger.warning(f"Step not found: {name}")
    
    def configure_steps(self, config: Dict[str, bool]) -> None:
        """
        Configure multiple steps at once.
        
        Args:
            config: Dictionary mapping step names to enabled status
        """
        for name, enabled in config.items():
            found = False
            for step in self.steps:
                if step.name == name:
                    step.enabled = enabled
                    found = True
                    break
            if not found:
                self.logger.warning(f"Step not found: {name}")
    
    def get_step(self, name: str) -> Optional[ProcessingStep]:
        """
        Get a step by name.
        
        Args:
            name: Name of the step to get
            
        Returns:
            The step or None if not found
        """
        for step in self.steps:
            if step.name == name:
                return step
        return None
    
    def get_enabled_steps(self) -> List[ProcessingStep]:
        """
        Get all enabled steps.
        
        Returns:
            List of enabled steps
        """
        return [step for step in self.steps if step.enabled]
    
    def get_disabled_steps(self) -> List[ProcessingStep]:
        """
        Get all disabled steps.
        
        Returns:
            List of disabled steps
        """
        return [step for step in self.steps if not step.enabled]
    
    def execute_pipeline(self, initial_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Execute all enabled steps in the pipeline.
        
        Args:
            initial_data: Initial data to pass to the first step
            **kwargs: Additional keyword arguments to pass to steps that accept them
            
        Returns:
            Dictionary with the results of all steps
        """
        result = initial_data.copy()
        
        for step in self.steps:
            if not step.enabled:
                self.logger.info(f"Skipping disabled step: {step.name}")
                continue
            
            self.logger.info(f"Executing step: {step.name}")
            try:
                # Execute the step with the current result and kwargs
                # The step itself will filter kwargs to only those it accepts
                step_result = step.execute(result, **kwargs)
                
                # If the step returns None, we continue with the current result
                # If it returns a dict, we update our result with it
                # Otherwise, we store the result with the step name as the key
                if step_result is None:
                    pass
                elif isinstance(step_result, dict):
                    result.update(step_result)
                else:
                    result[step.name] = step_result
                    
            except Exception as e:
                self.logger.error(f"Error in step {step.name}: {str(e)}")
                result[f"{step.name}_error"] = str(e)
        
        return result
