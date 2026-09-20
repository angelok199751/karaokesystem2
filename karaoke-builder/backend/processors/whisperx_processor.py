"""
WhisperX Processor for Karaoke Builder

Stage 2: Word-level Alignment
Uses WhisperX with forced alignment to get word timestamps
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

from .base_processor import BaseProcessor, ProcessorContext
from ..stage_runner import StageResult
from ..debug_logger import debug_logger
from ..config import WHISPER_MODEL, WHISPERX_TIMEOUT


class WhisperXProcessor(BaseProcessor):
    """Processor for word-level alignment using WhisperX"""
    
    @property
    def name(self) -> str:
        return "WhisperX"
    
    def execute(self) -> StageResult:
        """
        Execute WhisperX alignment
        
        Returns:
            StageResult with words.json path containing aligned lyrics
        """
        from ..stage_runner import StageRunner
        
        # Validate inputs
        error = self.validate_inputs([self.context.vocals_file, self.context.lyrics_file])
        if error:
            debug_logger.log_error(self.name, error)
            return StageResult(
                success=False,
                stage=self.name,
                duration=0,
                outputs=[],
                stdout="",
                stderr=error,
                exit_code=-1,
                error_message=error
            )
        
        # Create output directory
        whisperx_dir = self.create_subdirectory("whisperx")
        words_file = whisperx_dir / "words.json"
        
        # Read lyrics file
        try:
            with open(self.context.lyrics_file, 'r', encoding='utf-8') as f:
                lyrics_text = f.read().strip()
            
            # Split into lines (for reference)
            lyrics_lines = [line.strip() for line in lyrics_text.split('\n') if line.strip()]
            debug_logger.log_info(self.name, f"Lyrics: {len(lyrics_lines)} lines")
            
        except Exception as e:
            error_msg = f"Failed to read lyrics file: {str(e)}"
            debug_logger.log_error(self.name, error_msg)
            return StageResult(
                success=False,
                stage=self.name,
                duration=0,
                outputs=[],
                stdout="",
                stderr=error_msg,
                exit_code=-1,
                error_message=error_msg
            )
        
        # Build Python script for WhisperX processing
        # We use a Python script instead of CLI for better control
        script_content = self._build_whisperx_script(
            vocals_path=str(self.context.vocals_file),
            lyrics_text=lyrics_text,
            output_path=str(words_file),
            model=WHISPER_MODEL
        )
        
        script_file = whisperx_dir / "run_whisperx.py"
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # Build command
        # Using sys.executable to ensure we use the same Python environment
        command = [sys.executable, str(script_file)]
        
        # Get FFmpeg path and add to PATH for child process
        from ..utils.ffmpeg_helper import get_ffmpeg_path
        ffmpeg_path = get_ffmpeg_path()
        
        if ffmpeg_path:
            ffmpeg_dir = str(ffmpeg_path.parent)
            debug_logger.log_info(self.name, f"WhisperX: FFmpeg path: {ffmpeg_path}")
            debug_logger.log_info(self.name, f"WhisperX: FFmpeg exists: {ffmpeg_path.exists()}")
            
            # Add FFmpeg directory to PATH for child process
            process_env = os.environ.copy()
            if 'PATH' in process_env:
                process_env['PATH'] = f"{ffmpeg_dir}{os.pathsep}{process_env['PATH']}"
            else:
                process_env['PATH'] = ffmpeg_dir
        else:
            debug_logger.log_warning(self.name, "FFmpeg not found in bundled location, using system PATH")
            process_env = None
        
        debug_logger.log_info(self.name, f"Using model: {WHISPER_MODEL}")
        debug_logger.log_info(self.name, f"Output: {words_file.name}")
        
        # Run WhisperX
        runner = StageRunner(self.context.job_id, self.work_dir)
        result = runner.run(
            name=self.name,
            command=command,
            input_files=[self.context.vocals_file],
            output_files=[words_file],
            env=process_env,
            timeout=WHISPERX_TIMEOUT,
        )
        
        # Update context on success
        if result.success:
            self.context.words_json = words_file
            debug_logger.log_info(self.name, f"Words JSON created: {words_file.name}")
        
        return result
    
    def _build_whisperx_script(self, vocals_path: str, lyrics_text: str, 
                                output_path: str, model: str) -> str:
        """Build Python script for WhisperX processing"""
        
        # Escape strings for embedding in script
        lyrics_escaped = lyrics_text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        
        return f'''#!/usr/bin/env python3
"""
WhisperX Alignment Script
Generated by Karaoke Builder
"""

import sys
import json
import warnings
warnings.filterwarnings("ignore")

try:
    import torch
    import whisperx
except ImportError as e:
    print(f"ERROR: Required library not found: {{e}}", file=sys.stderr)
    print("Please install whisperx: pip install git+https://github.com/m-bain/whisperx.git", file=sys.stderr)
    sys.exit(1)

# Configuration
VOCALS_PATH = r"{vocals_path}"
LYRICS_TEXT = r"""{lyrics_escaped}"""
OUTPUT_PATH = r"{output_path}"
MODEL_NAME = "{model}"

def main():
    print(f"Loading audio: {{VOCALS_PATH}}")
    
    # Detect device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {{device}}")
    
    if device == "cuda":
        compute_type = "float16"
    else:
        compute_type = "int8"
    
    try:
        # Load audio
        audio = whisperx.load_audio(VOCALS_PATH)
        
        # Load Whisper model
        print(f"Loading Whisper model: {{MODEL_NAME}}")
        model = whisperx.load_model(
            whisper_arch=MODEL_NAME,
            device=device,
            compute_type=compute_type
        )
        
        # Transcribe
        print("Transcribing...")
        result = model.transcribe(audio, batch_size=16)
        
        # Align
        print("Aligning with forced alignment...")
        align_model, align_metadata = whisperx.load_align_model(
            language_code=result["language"],
            device=device
        )
        
        result = whisperx.align(
            result["segments"],
            align_model,
            align_metadata,
            audio,
            device,
            return_char_alignments=False
        )
        
        # Convert to our normalized format
        print("Converting to normalized format...")
        
        # Parse original lyrics lines
        original_lines = [line.strip() for line in LYRICS_TEXT.split("\\n") if line.strip()]
        
        # Build output structure
        output = {{
            "format": "whisperx_aligned",
            "version": 1,
            "lines": []
        }}
        
        # Group segments into lines based on original lyrics
        # This is a simplified approach - production version would need better matching
        
        current_line_idx = 0
        current_line_words = []
        current_line_start = None
        current_line_end = None
        
        for segment in result.get("segments", []):
            segment_text = segment.get("text", "").strip()
            segment_start = segment.get("start", 0)
            segment_end = segment.get("end", 0)
            
            # Get words from this segment
            words_in_segment = segment.get("words", [])
            
            for word_info in words_in_segment:
                word_text = word_info.get("word", "").strip()
                word_start = word_info.get("start", 0)
                word_end = word_info.get("end", 0)
                
                if not word_text:
                    continue
                
                current_line_words.append({{
                    "text": word_text,
                    "start": round(word_start, 3),
                    "end": round(word_end, 3)
                }})
                
                if current_line_start is None:
                    current_line_start = word_start
                current_line_end = word_end
        
        # If we have words, create a single line (simplified for prototype)
        # TODO: Implement proper line matching with original lyrics
        if current_line_words:
            line_text = " ".join(w["text"] for w in current_line_words)
            
            output["lines"].append({{
                "start": round(current_line_start, 3) if current_line_start else 0,
                "end": round(current_line_end, 3) if current_line_end else 0,
                "text": line_text,
                "words": current_line_words
            }})
        
        # Save output
        print(f"Saving to {{OUTPUT_PATH}}")
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"Success! Created {{len(output['lines'])}} lines with {{len(current_line_words)}} words")
        
    except Exception as e:
        print(f"ERROR: {{str(e)}}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
