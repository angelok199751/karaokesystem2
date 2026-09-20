"""
Packaging Processor for Karaoke Builder

Stage 4: Build Final Karaoke JSON and MP3
Combines all results into the internal karaoke format
"""

import json
import shutil
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from .base_processor import BaseProcessor, ProcessorContext
from ..stage_runner import StageResult
from ..debug_logger import debug_logger
from ..config import KEEP_TEMP_ON_SUCCESS


class PackagingProcessor(BaseProcessor):
    """Processor for building final karaoke JSON and minus MP3"""
    
    @property
    def name(self) -> str:
        return "Packaging"
    
    def execute(self) -> StageResult:
        """
        Build final karaoke JSON and convert instrumental to MP3
        
        Returns:
            StageResult with karaoke.json and minus.mp3 paths
        """
        from ..stage_runner import StageRunner
        
        # Validate inputs
        required_files = []
        
        if self.context.words_json:
            required_files.append(self.context.words_json)
        else:
            error = "Words JSON not found (WhisperX may have failed)"
            debug_logger.log_error(self.name, error)
            return self._failure_result(error)
        
        if self.context.pitch_json:
            required_files.append(self.context.pitch_json)
        else:
            error = "Pitch JSON not found (Pitch extraction may have failed)"
            debug_logger.log_error(self.name, error)
            return self._failure_result(error)
        
        if self.context.instrumental_file:
            required_files.append(self.context.instrumental_file)
        else:
            error = "Instrumental file not found (Demucs may have failed)"
            debug_logger.log_error(self.name, error)
            return self._failure_result(error)
        
        error = self.validate_inputs(required_files)
        if error:
            debug_logger.log_error(self.name, error)
            return self._failure_result(error)
        
        # Create output directory
        output_dir = self.create_subdirectory("output")
        karaoke_file = output_dir / "karaoke.json"
        minus_file = output_dir / "minus.mp3"
        
        # Build karaoke JSON
        debug_logger.log_info(self.name, "Building karaoke JSON...")
        try:
            karaoke_data = self._build_karaoke_json()
            
            with open(karaoke_file, 'w', encoding='utf-8') as f:
                json.dump(karaoke_data, f, ensure_ascii=False, indent=2)
            
            debug_logger.log_info(self.name, f"Created: {karaoke_file.name}")
            
        except Exception as e:
            error_msg = f"Failed to build karaoke JSON: {str(e)}"
            debug_logger.log_error(self.name, error_msg)
            return self._failure_result(error_msg)
        
        # Convert instrumental to MP3 using FFmpeg
        debug_logger.log_info(self.name, "Converting to MP3...")
        
        from ..utils.ffmpeg_helper import get_ffmpeg_path
        ffmpeg_path = get_ffmpeg_path()
        
        if not ffmpeg_path:
            error_msg = "FFmpeg not found. Please install FFmpeg or add it to tools/ffmpeg/bin/"
            debug_logger.log_error(self.name, error_msg)
            return self._failure_result(error_msg)
        
        command = [
            str(ffmpeg_path),
            "-i", str(self.context.instrumental_file),
            "-b:a", "192k",
            "-y",  # Overwrite
            str(minus_file)
        ]
        
        runner = StageRunner(self.context.job_id, self.work_dir)
        result = runner.run(
            name=self.name,
            command=command,
            input_files=[self.context.instrumental_file],
            output_files=[minus_file],
            timeout=300,  # 5 minutes for conversion
        )
        
        if result.success:
            self.context.karaoke_json = karaoke_file
            self.context.minus_mp3 = minus_file
            
            debug_logger.log_info(self.name, f"Created: {minus_file.name}")
            debug_logger.log_info(self.name, f"Package complete!")
        
        return result
    
    def _build_karaoke_json(self) -> Dict[str, Any]:
        """Build the final karaoke JSON structure"""
        
        # Load words data
        with open(self.context.words_json, 'r', encoding='utf-8') as f:
            words_data = json.load(f)
        
        # Load pitch data
        with open(self.context.pitch_json, 'r', encoding='utf-8') as f:
            pitch_data = json.load(f)
        
        # Get audio duration from pitch metadata or estimate
        duration = pitch_data.get("metadata", {}).get("duration", 0)
        
        # If we don't have duration, try to get it from the audio file
        if duration == 0 and self.context.input_file:
            try:
                import torchaudio
                waveform, sr = torchaudio.load(str(self.context.input_file))
                duration = waveform.shape[1] / sr
            except:
                duration = 0
        
        # Build lyrics structure - normalize from WhisperX format
        lyrics_lines = []
        
        whisperx_lines = words_data.get("lines", [])
        
        # For prototype: use WhisperX lines as-is
        # TODO: Implement proper line matching with original TXT
        for line in whisperx_lines:
            lyrics_lines.append({
                "start": line.get("start", 0),
                "end": line.get("end", 0),
                "text": line.get("text", ""),
                "words": line.get("words", [])
            })
        
        # Build pitch points structure
        pitch_points = pitch_data.get("points", [])
        
        # Filter to only include high-confidence voiced points
        # But keep all points for potential future analysis
        filtered_pitch = []
        for point in pitch_points:
            filtered_pitch.append({
                "time": point.get("time", 0),
                "frequency": point.get("frequency", 0),
                "confidence": point.get("confidence", 0)
            })
        
        # Build final structure
        karaoke_json = {
            "format": "karaoke",
            "version": 1,
            
            "metadata": {
                "title": self.context.title or "Unknown",
                "duration": round(duration, 2),
                "created_at": datetime.now().isoformat(),
                "builder_version": "0.1.0-prototype"
            },
            
            "lyrics": {
                "lines": lyrics_lines
            },
            
            "pitch": {
                "metadata": pitch_data.get("metadata", {}),
                "points": filtered_pitch
            }
        }
        
        return karaoke_json
    
    def _failure_result(self, error_message: str) -> StageResult:
        """Create a failure StageResult"""
        return StageResult(
            success=False,
            stage=self.name,
            duration=0,
            outputs=[],
            stdout="",
            stderr=error_message,
            exit_code=-1,
            error_message=error_message
        )
