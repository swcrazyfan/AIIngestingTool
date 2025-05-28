"""
Logging configuration for the video ingest tool.

Sets up structured logging with both console and file output.
"""

import os
import datetime
import logging
import structlog
from rich.console import Console
from rich.logging import RichHandler
from logging import FileHandler
from typing import Tuple, Any

# Initialize console for rich output
console = Console()

def setup_logging() -> Tuple[Any, str, str, str]:
    """
    Setup logging configurations for both file and console output.
    
    Returns:
        Tuple containing:
            - logger: The configured logger
            - timestamp: Timestamp for the current run
            - json_dir: Directory for JSON output files
            - log_file: Path to the log file
    """
    # Get the package directory
    package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parent_dir = os.path.dirname(package_dir)
    
    # Configure logging
    log_dir = os.path.join(parent_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Create a timestamp for current run
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create consolidated output directory structure
    output_dir = os.path.join(parent_dir, "output")
    runs_dir = os.path.join(output_dir, "runs")
    current_run_dir = os.path.join(runs_dir, f"run_{timestamp}")
    
    # Create run-specific directories
    os.makedirs(current_run_dir, exist_ok=True)
    run_logs_dir = os.path.join(current_run_dir, "logs")
    os.makedirs(run_logs_dir, exist_ok=True)
    
    # Log file in run directory
    log_file = os.path.join(run_logs_dir, f"ingestor_{timestamp}.log")
    
    # Create JSON directory in run structure  
    json_dir = os.path.join(current_run_dir, "json")
    os.makedirs(json_dir, exist_ok=True)
    
    # Configure structlog to integrate with standard logging
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S.%f", utc=False),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(min_level=logging.INFO),
        context_class=dict,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard Python logging handlers
    log_format = "%(message)s"
    
    # Console Handler (using Rich for pretty output)
    rich_console_handler = RichHandler(console=console, rich_tracebacks=True, markup=True, show_path=False)
    rich_console_handler.setFormatter(logging.Formatter(log_format))
    rich_console_handler.setLevel(logging.INFO)
    
    # File Handler (plain text)
    file_log_handler = FileHandler(log_file, mode='w', encoding='utf-8')
    file_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)-5.5s] [%(name)s] %(message)s"))
    file_log_handler.setLevel(logging.INFO)
    
    # Get the root logger and add handlers
    std_root_logger = logging.getLogger()
    std_root_logger.addHandler(rich_console_handler)
    std_root_logger.addHandler(file_log_handler)
    std_root_logger.setLevel(logging.INFO)
    
    # Create a logger instance using structlog
    logger = structlog.get_logger(__name__)
    logger.info("Logging configured successfully for console and file.")
    
    return logger, timestamp, json_dir, log_file 