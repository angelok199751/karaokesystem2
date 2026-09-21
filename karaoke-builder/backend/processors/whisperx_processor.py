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
        # Match recognized words to original lyric lines by text content
        
        # Build a list of all recognized words in order
        all_words = []
        for segment in result.get("segments", []):
            words_in_segment = segment.get("words", [])
            for word_info in words_in_segment:
                word_text = word_info.get("word", "").strip()
                word_start = word_info.get("start", 0)
                word_end = word_info.get("end", 0)
                
                if not word_text:
                    continue
                
                all_words.append({{
                    "text": word_text,
                    "start": round(word_start, 3),
                    "end": round(word_end, 3)
                }})
        
        # Match words to original lyrics lines
        # We use a simple approach: iterate through original lines and find matching words
        word_idx = 0
        total_words = len(all_words)
        
        for orig_line in original_lines:
            # Normalize the original line for matching (lowercase, remove punctuation)
            orig_line_normalized = orig_line.lower()
            
            # Try to find words that match this line
            line_words = []
            line_start = None
            line_end = None
            
            # Collect words until we have enough to match the line
            # We look for consecutive words whose combined text matches the original line
            temp_words = []
            temp_text_parts = []
            
            while word_idx < total_words:
                word = all_words[word_idx]
                temp_words.append(word)
                temp_text_parts.append(word["text"].lower())
                
                # Check if the accumulated text matches or contains the original line
                temp_combined = " ".join(temp_text_parts)
                
                # Simple heuristic: if we've collected enough words to cover the line length
                # and the line text is contained in or equals the combined words
                if len(temp_combined) >= len(orig_line_normalized) * 0.7:
                    # Check if this roughly matches the original line
                    # We allow some flexibility for recognition errors
                    if orig_line_normalized in temp_combined or temp_combined in orig_line_normalized:
                        # Good match, consume these words
                        line_words.extend(temp_words)
                        if line_start is None:
                            line_start = temp_words[0]["start"]
                        line_end = temp_words[-1]["end"]
                        word_idx += len(temp_words)
                        break
                    elif len(temp_combined) > len(orig_line_normalized) * 1.5:
                        # Too much text, probably moved past this line
                        # Take what we have if we have anything
                        if temp_words:
                            line_words.extend(temp_words)
                            if line_start is None:
                                line_start = temp_words[0]["start"]
                            line_end = temp_words[-1]["end"]
                            word_idx += len(temp_words)
                        break
                
                word_idx += 1
                temp_words = []
                temp_text_parts = []
            
            # If we collected words for this line, add it to output
            if line_words:
                line_text = " ".join(w["text"] for w in line_words)
                
                output["lines"].append({{
                    "start": round(line_start, 3) if line_start else 0,
                    "end": round(line_end, 3) if line_end else 0,
                    "text": line_text,
                    "words": line_words
                }})
        
        # Handle any remaining words that didn't match a specific line
        # (e.g., if there are more recognized words than original lines)
        remaining_words = all_words[word_idx:]
        if remaining_words:
            line_start = remaining_words[0]["start"]
            line_end = remaining_words[-1]["end"]
            line_text = " ".join(w["text"] for w in remaining_words)
            
            output["lines"].append({{
                "start": round(line_start, 3),
                "end": round(line_end, 3),
                "text": line_text,
                "words": remaining_words
            }})
        
        # Save output
        print(f"Saving to {{OUTPUT_PATH}}")
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        # Count total words in all lines
        total_words = sum(len(line.get("words", [])) for line in output["lines"])
        print(f"Success! Created {{len(output['lines'])}} lines with {{total_words}} words")
        
    except Exception as e:
        print(f"ERROR: {{str(e)}}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
