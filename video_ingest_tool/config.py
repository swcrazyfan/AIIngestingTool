"""
Configuration for the video ingest tool.

Contains constants, settings, and logging setup.
"""

import os
import datetime
import logging
import structlog
from rich.console import Console
from rich.logging import RichHandler
from logging import FileHandler

# Initialize console for rich output
console = Console()

# Focal length category ranges (in mm, for full-frame equivalent)
FOCAL_LENGTH_RANGES = {
    "ULTRA-WIDE": (8, 18),    # Ultra wide-angle: 8-18mm
    "WIDE": (18, 35),         # Wide-angle: 18-35mm
    "MEDIUM": (35, 70),       # Standard/Normal: 35-70mm
    "LONG-LENS": (70, 200),   # Short telephoto: 70-200mm
    "TELEPHOTO": (200, 800)   # Telephoto: 200-800mm
}

def setup_logging():
    """
    Setup logging configurations for both file and console output.
    Returns the logger and timestamp for current run.
    """
    # Get the package directory
    package_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(package_dir)
    
    # Configure logging
    log_dir = os.path.join(parent_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Create a timestamp for current run
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"ingestor_{timestamp}.log")
    
    # Ensure JSON output directory exists
    json_dir = os.path.join(parent_dir, "json_output")
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

# Check if required modules are available
try:
    from polyfile.magic import MagicMatcher
    HAS_POLYFILE = True
except ImportError:
    HAS_POLYFILE = False

try:
    from transformers import pipeline
    import torch
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
