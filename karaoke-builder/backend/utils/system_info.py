"""
System Information Utility for Karaoke Builder

Provides system diagnostics:
- OS information
- Python version
- PyTorch and CUDA status
- GPU information
- Tool availability (FFmpeg, Demucs, etc.)
"""

import sys
import platform
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional


def get_system_info() -> Dict[str, Any]:
    """Get comprehensive system information"""
    
    info = {
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "python": {
            "version": sys.version,
            "version_info": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        },
    }
    
    # PyTorch info
    try:
        import torch
        
        info["pytorch"] = {
            "version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
        }
        
        if torch.cuda.is_available():
            info["cuda"] = {
                "version": torch.version.cuda,
                "gpu_count": torch.cuda.device_count(),
                "gpus": []
            }
            
            for i in range(torch.cuda.device_count()):
                gpu_info = {
                    "name": torch.cuda.get_device_name(i),
                    "vram_gb": round(torch.cuda.get_device_properties(i).total_memory / (1024**3), 1),
                }
                info["cuda"]["gpus"].append(gpu_info)
                
    except ImportError:
        info["pytorch"] = None
    
    return info


def check_ffmpeg() -> Dict[str, Any]:
    """Check FFmpeg installation"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            return {
                "installed": True,
                "version": version_line,
                "available": True
            }
        else:
            return {
                "installed": False,
                "available": False,
                "error": "FFmpeg returned non-zero exit code"
            }
            
    except FileNotFoundError:
        return {
            "installed": False,
            "available": False,
            "error": "FFmpeg not found in PATH"
        }
    except Exception as e:
        return {
            "installed": False,
            "available": False,
            "error": str(e)
        }


def check_demucs() -> Dict[str, Any]:
    """Check Demucs installation"""
    try:
        import demucs
        
        return {
            "installed": True,
            "available": True,
            "module": "demucs"
        }
    except ImportError:
        return {
            "installed": False,
            "available": False,
            "error": "Demucs not installed"
        }


def check_whisperx() -> Dict[str, Any]:
    """Check WhisperX installation"""
    try:
        import whisperx
        
        return {
            "installed": True,
            "available": True,
            "module": "whisperx"
        }
    except ImportError:
        return {
            "installed": False,
            "available": False,
            "error": "WhisperX not installed"
        }


def check_torchcrepe() -> Dict[str, Any]:
    """Check torchcrepe installation"""
    try:
        import torchcrepe
        
        return {
            "installed": True,
            "available": True,
            "module": "torchcrepe"
        }
    except ImportError:
        return {
            "installed": False,
            "available": False,
            "error": "torchcrepe not installed"
        }


def check_libraries() -> Dict[str, Dict[str, Any]]:
    """Check all required libraries"""
    return {
        "ffmpeg": check_ffmpeg(),
        "demucs": check_demucs(),
        "whisperx": check_whisperx(),
        "torchcrepe": check_torchcrepe(),
    }


def print_diagnostics():
    """Print formatted diagnostic information"""
    
    print("=" * 60)
    print("Karaoke Builder — System Diagnostics")
    print("=" * 60)
    print()
    
    # System info
    info = get_system_info()
    
    print("SYSTEM")
    print("-" * 40)
    print(f"OS: {info['os']['system']} {info['os']['release']}")
    print(f"Python: {info['python']['version_info']}")
    
    if info["pytorch"]:
        print(f"PyTorch: {info['pytorch']['version']}")
        print(f"CUDA Available: {info['pytorch']['cuda_available']}")
        
        if info.get("cuda"):
            print(f"CUDA Version: {info['cuda']['version']}")
            print(f"GPU Count: {info['cuda']['gpu_count']}")
            for gpu in info["cuda"]["gpus"]:
                print(f"  GPU: {gpu['name']} ({gpu['vram_gb']} GB)")
    else:
        print("PyTorch: Not installed")
    
    print()
    
    # Tools
    print("TOOLS")
    print("-" * 40)
    libs = check_libraries()
    
    for name, status in libs.items():
        symbol = "✓" if status.get("available") else "✗"
        print(f"{symbol} {name.capitalize()}: {status.get('version', status.get('module', 'N/A'))}")
        
        if not status.get("available"):
            print(f"   Error: {status.get('error', 'Unknown')}")
    
    print()
    print("=" * 60)


if __name__ == "__main__":
    print_diagnostics()
