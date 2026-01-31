"""Shared logging configuration for the application.

This module provides a function to configure logging that can be used
by both the FastAPI app and standalone scripts.
"""

import logging
import sys
from pathlib import Path

from app.config import LOGS_DIR


def setup_logging(console_level=logging.INFO, file_level=logging.DEBUG):
    """Configure logging to output to both console and file.
    
    Args:
        console_level: Minimum log level for console output (default: INFO)
        file_level: Minimum log level for file output (default: DEBUG)
    """
    # Create logs directory if it doesn't exist
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Set to lowest level to capture all logs
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s - %(name)s - %(message)s'
    )
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler (logs to file)
    log_file = LOGS_DIR / "app.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(file_level)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
