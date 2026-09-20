"""
Audio Utilities for Karaoke Builder

Provides audio processing utilities:
- Duration extraction
- Format validation
- Audio info
"""

import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any


def get_audio_duration(file_path: Path) -> Optional[float]:
    """
    Get audio duration using FFmpeg
    
    Args:
        file_path: Path to audio file
        
    Returns:
        Duration in seconds, or None if failed
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(file_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            return None
        
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        
        return duration
        
    except Exception:
        return None


def validate_audio_file(file_path: Path) -> Dict[str, Any]:
    """
    Validate an audio file
    
    Returns:
        Dict with validation results
    """
    result = {
        "valid": False,
        "exists": False,
        "readable": False,
        "duration": None,
        "error": None
    }
    
    # Check existence
    if not file_path.exists():
        result["error"] = "File does not exist"
        return result
    
    result["exists"] = True
    
    # Check if readable
    if not file_path.is_file():
        result["error"] = "Not a file"
        return result
    
    try:
        file_size = file_path.stat().st_size
        if file_size == 0:
            result["error"] = "File is empty"
            return result
            
        result["size_bytes"] = file_size
        
    except Exception as e:
        result["error"] = f"Cannot read file: {e}"
        return result
    
    # Get duration via FFmpeg
    duration = get_audio_duration(file_path)
    
    if duration is None:
        result["error"] = "Cannot read audio (FFprobe failed)"
        return result
    
    if duration <= 0:
        result["error"] = "Invalid duration"
        return result
    
    result["readable"] = True
    result["duration"] = duration
    result["valid"] = True
    
    return result


def format_duration(seconds: float) -> str:
    """Format duration as MM:SS or HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def format_size(bytes_size: int) -> str:
    """Format file size in human-readable form"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"
