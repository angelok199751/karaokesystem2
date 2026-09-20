"""
FFmpeg Helper for Karaoke Builder

Provides unified FFmpeg path resolution:
1. First check bundled FFmpeg in tools/ffmpeg/bin/
2. Fallback to system PATH
3. Return path and status information
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional


def get_project_root() -> Path:
    """Get project root directory"""
    return Path(__file__).parent.parent.parent


def get_ffmpeg_path() -> Optional[Path]:
    """
    Get FFmpeg executable path
    
    Priority:
    1. Bundled FFmpeg in tools/ffmpeg/bin/
    2. System PATH
    
    Returns:
        Path to ffmpeg executable or None if not found
    """
    project_root = get_project_root()
    
    # Check bundled FFmpeg first
    bundled_paths = [
        project_root / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",  # Windows
        project_root / "tools" / "ffmpeg" / "bin" / "ffmpeg",      # Linux/Mac
        project_root / ".." / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
        project_root / ".." / "tools" / "ffmpeg" / "bin" / "ffmpeg",
    ]
    
    for bundled_path in bundled_paths:
        if bundled_path.exists():
            return bundled_path
    
    # Fallback to system PATH
    ffmpeg_in_path = _find_ffmpeg_in_path()
    if ffmpeg_in_path:
        return ffmpeg_in_path
    
    return None


def _find_ffmpeg_in_path() -> Optional[Path]:
    """Find FFmpeg in system PATH"""
    try:
        result = subprocess.run(
            ["which", "ffmpeg"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except Exception:
        pass
    
    # Windows fallback
    try:
        result = subprocess.run(
            ["where", "ffmpeg"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip().split('\n')[0])
    except Exception:
        pass
    
    return None


def check_ffmpeg() -> Dict[str, Any]:
    """
    Check FFmpeg installation and return detailed status
    
    Returns:
        Dict with availability status, path, version, and error info
    """
    ffmpeg_path = get_ffmpeg_path()
    
    if not ffmpeg_path:
        return {
            "available": False,
            "path": None,
            "bundled": False,
            "error": "FFmpeg not found. Please install FFmpeg or add it to tools/ffmpeg/bin/"
        }
    
    # Check if it's the bundled version
    is_bundled = "tools" in str(ffmpeg_path) and "ffmpeg" in str(ffmpeg_path)
    
    # Verify it actually works
    try:
        result = subprocess.run(
            [str(ffmpeg_path), "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            return {
                "available": True,
                "path": str(ffmpeg_path),
                "bundled": is_bundled,
                "version": version_line,
                "error": None
            }
        else:
            return {
                "available": False,
                "path": str(ffmpeg_path),
                "bundled": is_bundled,
                "error": f"FFmpeg returned non-zero exit code: {result.returncode}"
            }
            
    except subprocess.TimeoutExpired:
        return {
            "available": False,
            "path": str(ffmpeg_path),
            "bundled": is_bundled,
            "error": "FFmpeg version check timed out"
        }
    except Exception as e:
        return {
            "available": False,
            "path": str(ffmpeg_path),
            "bundled": is_bundled,
            "error": str(e)
        }


def run_ffmpeg_command(command: list, **kwargs) -> subprocess.CompletedProcess:
    """
    Run FFmpeg command using the resolved FFmpeg path
    
    Args:
        command: List of arguments (without 'ffmpeg' at the start)
        **kwargs: Additional arguments for subprocess.run
    
    Returns:
        CompletedProcess instance
    """
    ffmpeg_path = get_ffmpeg_path()
    
    if not ffmpeg_path:
        raise RuntimeError("FFmpeg not found. Please install FFmpeg or add it to tools/ffmpeg/bin/")
    
    full_command = [str(ffmpeg_path)] + command
    
    return subprocess.run(full_command, **kwargs)
