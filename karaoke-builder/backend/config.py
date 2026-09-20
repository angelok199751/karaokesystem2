"""
Configuration for Karaoke Builder Backend
"""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).parent.parent
TEMP_DIR = BASE_DIR / "temp"
LOGS_DIR = BASE_DIR / "logs"
MODELS_DIR = BASE_DIR / "models"
FRONTEND_DIR = BASE_DIR / "frontend"

# Create directories if they don't exist
TEMP_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)

# Server configuration
HOST = "0.0.0.0"
PORT = 5000
DEBUG = True

# Pipeline configuration
DEMUCS_MODEL = "htdemucs"  # Default Demucs model
WHISPER_MODEL = "medium"   # Default Whisper model
WHISPER_DEVICE = "auto"    # auto, cuda, cpu
PITCH_MODEL = "full"       # torchcrepe model: full, tiny

# Audio settings
SAMPLE_RATE = 44100
HOP_LENGTH = 512  # For pitch analysis

# Temporary file settings
KEEP_TEMP_ON_SUCCESS = False  # Delete temp files on success
KEEP_TEMP_ON_FAILURE = True   # Always keep temp files on failure

# Timeout settings (seconds)
DEMUCS_TIMEOUT = 600      # 10 minutes
WHISPERX_TIMEOUT = 1800   # 30 minutes
PITCH_TIMEOUT = 600       # 10 minutes
