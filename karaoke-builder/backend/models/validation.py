"""
Input Validation for Karaoke Builder

Validates user input before pipeline execution:
- MP3 file validation
- TXT file validation
- System readiness check
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from .audio_utils import validate_audio_file, format_duration, format_size


def validate_mp3_file(file_path: Path) -> Dict[str, Any]:
    """
    Validate MP3/audio input file
    
    Returns:
        Validation result dict
    """
    result = {
        "valid": False,
        "file": str(file_path),
        "error": None
    }
    
    # Check extension
    valid_extensions = ['.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac']
    if file_path.suffix.lower() not in valid_extensions:
        result["error"] = f"Unsupported file format: {file_path.suffix}"
        return result
    
    # Validate audio file
    audio_result = validate_audio_file(file_path)
    
    if not audio_result["valid"]:
        result["error"] = audio_result["error"]
        return result
    
    result["valid"] = True
    result["duration"] = audio_result["duration"]
    result["duration_formatted"] = format_duration(audio_result["duration"])
    result["size_bytes"] = audio_result.get("size_bytes", 0)
    result["size_formatted"] = format_size(audio_result.get("size_bytes", 0))
    
    return result


def validate_txt_file(file_path: Path) -> Dict[str, Any]:
    """
    Validate lyrics TXT file
    
    Returns:
        Validation result dict
    """
    result = {
        "valid": False,
        "file": str(file_path),
        "error": None
    }
    
    # Check extension
    if file_path.suffix.lower() not in ['.txt', '.lyrics']:
        result["error"] = f"Unsupported file format: {file_path.suffix}"
        return result
    
    # Check existence
    if not file_path.exists():
        result["error"] = "File does not exist"
        return result
    
    # Check if readable
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        if not content:
            result["error"] = "File is empty"
            return result
        
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        if len(lines) == 0:
            result["error"] = "No text lines found"
            return result
        
        result["valid"] = True
        result["lines_count"] = len(lines)
        result["characters_count"] = len(content)
        result["preview"] = content[:200] + ("..." if len(content) > 200 else "")
        
    except UnicodeDecodeError:
        result["error"] = "File is not valid UTF-8 text"
        return result
    except Exception as e:
        result["error"] = f"Cannot read file: {e}"
        return result
    
    return result


def validate_project_inputs(mp3_path: Path, txt_path: Path, 
                            title: str = "") -> Tuple[bool, Dict[str, Any]]:
    """
    Validate all project inputs
    
    Args:
        mp3_path: Path to MP3 file
        txt_path: Path to TXT file
        title: Song title (optional)
        
    Returns:
        Tuple of (success, details_dict)
    """
    details = {
        "mp3": None,
        "txt": None,
        "title": title or "Untitled",
        "ready": False
    }
    
    # Validate MP3
    mp3_result = validate_mp3_file(mp3_path)
    details["mp3"] = mp3_result
    
    if not mp3_result["valid"]:
        details["error"] = f"MP3 validation failed: {mp3_result['error']}"
        return False, details
    
    # Validate TXT
    txt_result = validate_txt_file(txt_path)
    details["txt"] = txt_result
    
    if not txt_result["valid"]:
        details["error"] = f"TXT validation failed: {txt_result['error']}"
        return False, details
    
    # Check title
    if not title or not title.strip():
        # Use filename as title
        details["title"] = mp3_path.stem
    
    details["ready"] = True
    details["summary"] = {
        "title": details["title"],
        "audio_duration": mp3_result["duration_formatted"],
        "audio_size": mp3_result["size_formatted"],
        "lyrics_lines": txt_result["lines_count"]
    }
    
    return True, details


def check_system_readiness() -> Dict[str, Any]:
    """
    Check if system is ready for pipeline execution
    
    Returns:
        Readiness status dict
    """
    from .system_info import check_libraries
    
    result = {
        "ready": False,
        "components": {}
    }
    
    libs = check_libraries()
    
    required = ["ffmpeg", "demucs"]
    optional = ["whisperx", "torchcrepe"]
    
    all_required_ok = True
    
    for name in required + optional:
        status = libs.get(name, {})
        is_available = status.get("available", False)
        
        result["components"][name] = {
            "available": is_available,
            "required": name in required
        }
        
        if name in required and not is_available:
            all_required_ok = False
    
    result["ready"] = all_required_ok
    result["missing_required"] = [
        name for name in required 
        if not result["components"][name]["available"]
    ]
    result["missing_optional"] = [
        name for name in optional 
        if not result["components"][name]["available"]
    ]
    
    return result
