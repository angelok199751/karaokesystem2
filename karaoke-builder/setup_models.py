#!/usr/bin/env python3
"""
Model Setup Script for Karaoke Builder

This script checks and downloads required ML models:
- Demucs model
- Whisper model
- Alignment model
- torchcrepe model

Models are stored separately from the Git repository.
"""

import os
import sys
import subprocess
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

def check_python_version():
    """Check Python version >= 3.9"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print(f"❌ Python 3.9+ required, found {version.major}.{version.minor}")
        return False
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_ffmpeg():
    """Check if FFmpeg is installed"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✓ FFmpeg installed")
            return True
        else:
            print("❌ FFmpeg not found or not working")
            return False
    except FileNotFoundError:
        print("❌ FFmpeg not found in PATH")
        print("\nInstall FFmpeg:")
        print("  Windows: https://ffmpeg.org/download.html")
        print("  macOS:   brew install ffmpeg")
        print("  Linux:   apt install ffmpeg  OR  yum install ffmpeg")
        return False

def check_torch():
    """Check PyTorch installation"""
    try:
        import torch
        print(f"✓ PyTorch {torch.__version__}")
        
        # Check CUDA
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            gpu_count = torch.cuda.device_count()
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            print(f"✓ CUDA available ({gpu_count} GPU(s))")
            print(f"  GPU: {gpu_name}")
            print(f"  VRAM: {gpu_memory:.1f} GB")
        else:
            print("⚠ CUDA not available (will use CPU)")
        
        return True
    except ImportError:
        print("❌ PyTorch not installed")
        print("  Run: pip install torch torchaudio")
        return False

def check_demucs():
    """Check Demucs installation"""
    try:
        import demucs
        print(f"✓ Demucs installed")
        return True
    except ImportError:
        print("❌ Demucs not installed")
        print("  Run: pip install demucs")
        return False

def check_whisperx():
    """Check WhisperX installation"""
    try:
        import whisperx
        print(f"✓ WhisperX installed")
        return True
    except ImportError:
        print("⚠ WhisperX not installed")
        print("  Install from: https://github.com/m-bain/whisperX")
        print("  Note: Requires additional dependencies (transformers, etc.)")
        return False

def check_torchcrepe():
    """Check torchcrepe installation"""
    try:
        import torchcrepe
        print(f"✓ torchcrepe installed")
        return True
    except ImportError:
        print("❌ torchcrepe not installed")
        print("  Run: pip install torchcrepe")
        return False

def check_models_directory():
    """Check/create models directory"""
    models_dir = Path(__file__).parent / "models"
    models_dir.mkdir(exist_ok=True)
    print(f"✓ Models directory: {models_dir.absolute()}")
    return models_dir

def download_demucs_model():
    """Download Demucs model (handled automatically by demucs library)"""
    print("\nℹ Demucs models will be downloaded on first use")
    print("  Location: ~/.cache/huggingface/hub/")
    return True

def download_whisper_model():
    """Download Whisper model (handled automatically by whisperx)"""
    print("\nℹ Whisper models will be downloaded on first use")
    print("  Location: ~/.cache/whisper/")
    return True

def main():
    print("=" * 60)
    print("Karaoke Builder — Model Setup")
    print("=" * 60)
    print()
    
    checks = []
    
    # System checks
    print("SYSTEM CHECKS")
    print("-" * 40)
    checks.append(check_python_version())
    checks.append(check_ffmpeg())
    checks.append(check_torch())
    print()
    
    # Library checks
    print("LIBRARY CHECKS")
    print("-" * 40)
    checks.append(check_demucs())
    checks.append(check_whisperx())
    checks.append(check_torchcrepe())
    print()
    
    # Directory setup
    print("DIRECTORY SETUP")
    print("-" * 40)
    check_models_directory()
    print()
    
    # Model downloads
    print("MODEL DOWNLOADS")
    print("-" * 40)
    download_demucs_model()
    download_whisper_model()
    print()
    
    # Summary
    print("=" * 60)
    if all(checks):
        print("✓ All checks passed!")
        print("\nNext steps:")
        print("  1. python backend/app.py")
        print("  2. Open http://localhost:5000 in browser")
        return 0
    else:
        print("⚠ Some checks failed. Please install missing components.")
        print("\nQuick install:")
        print("  pip install -r requirements.txt")
        print("  pip install git+https://github.com/m-bain/whisperx.git")
        return 1

if __name__ == "__main__":
    sys.exit(main())
