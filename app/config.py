"""Configuration management for environment variables and constants.

This module loads configuration from environment variables, with optional
support for .env files. All paths are resolved relative to the project root
and work correctly on both Windows and WSL environments.
"""

import os
from pathlib import Path
from typing import Literal

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    _env_file = Path(__file__).parent.parent / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)
except ImportError:
    # python-dotenv not installed, continue without .env support
    pass

# Project root directory (resolved to absolute path for WSL/Windows compatibility)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Database configuration
DATABASE_URL = "mysql+pymysql://mentor:mentor@localhost:3306/mvpipeline"
"""MySQL database connection URL."""

# Output directories (created as Path objects, resolved to absolute)
OUTPUT_DIR = PROJECT_ROOT / "output"
"""Directory for generated quote images.
    
Defaults to `output/` in the project root. Directory will be created
automatically when needed.
"""

LOGS_DIR = PROJECT_ROOT / "logs"
"""Directory for application logs.
    
Defaults to `logs/` in the project root. Directory will be created
automatically when needed.
"""

TEMPLATES_DIR = PROJECT_ROOT / "templates"
"""Directory for image templates.
    
Defaults to `templates/` in the project root. Contains base images
or templates used for quote rendering.
"""

FONTS_DIR = PROJECT_ROOT / "fonts"
"""Directory for font files.
    
Defaults to `fonts/` in the project root. Contains font files (.ttf, .otf)
used for rendering quote text on images.
"""

# Pipeline mode configuration
PipelineMode = Literal["once", "continuous", "batch"]
"""Pipeline execution mode type hint."""

PIPELINE_MODE: PipelineMode = os.getenv("PIPELINE_MODE", "once").lower()  # type: ignore
"""Pipeline execution mode.
    
Valid values:
    - "once": Run pipeline once and exit (default)
    - "continuous": Run pipeline continuously (polling/event-driven)
    - "batch": Process multiple tasks in batch
    
Can be set via PIPELINE_MODE environment variable. Defaults to "once".
"""

# Validate pipeline mode
if PIPELINE_MODE not in ("once", "continuous", "batch"):
    PIPELINE_MODE = "once"  # Fallback to safe default

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
"""OpenAI API key for DALL-E image generation.

Get your API key from: https://platform.openai.com/api-keys
Set via OPENAI_API_KEY environment variable or .env file.
"""

# Image generator configuration
DEFAULT_IMAGE_GENERATOR = os.getenv("DEFAULT_IMAGE_GENERATOR", "pillow").lower()
"""Default image generator to use.

Valid values:
    - "pillow": Render quote on template (default)
    - "dalle": Generate image using DALL-E API
    
Set via DEFAULT_IMAGE_GENERATOR environment variable or .env file.
Defaults to "pillow".
"""

# Instagram API configuration
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
"""Instagram Graph API access token (long-lived).

Required for publishing posts to Instagram.
Get from: https://developers.facebook.com/docs/instagram-api/getting-started
Set via INSTAGRAM_ACCESS_TOKEN environment variable or .env file.
"""

INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")
"""Instagram Business Account ID.

Required for publishing posts to Instagram.
Get from: https://developers.facebook.com/docs/instagram-api/getting-started
Set via INSTAGRAM_ACCOUNT_ID environment variable or .env file.
"""

# Background worker configuration
WORKER_CHECK_INTERVAL_SECONDS = int(os.getenv("WORKER_CHECK_INTERVAL_SECONDS", "30"))
"""Interval in seconds between checks for processable jobs.

The worker processes READY jobs whose parent task is PROCESSING.
Set via WORKER_CHECK_INTERVAL_SECONDS environment variable or .env file.
Defaults to 30.
"""
