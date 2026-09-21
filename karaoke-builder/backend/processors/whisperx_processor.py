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
        
        # Escape double quotes and backslashes for embedding in script
        # Keep newlines as-is so they are preserved in the triple-quoted string
        lyrics_escaped = lyrics_text.replace('\\', '\\\\').replace('"', '\\"')
        
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
LYRICS_TEXT = """{lyrics_escaped}"""
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
                    "text": word_text.lower(),
                    "start": round(word_start, 3),
                    "end": round(word_end, 3)
                }})
        
        # Normalize original lines for matching
        def normalize_text(text):
            """Normalize text for fuzzy matching"""
            import re
            text = text.lower().strip()
            # Remove punctuation except hyphens within words
            text = re.sub(r'[^\\w\\s\\-]', ' ', text)
            # Normalize whitespace
            text = ' '.join(text.split())
            return text
        
        normalized_original_lines = [(i, line, normalize_text(line)) 
                                      for i, line in enumerate(original_lines)]
        
        # Find anchors: lines that can be matched to WhisperX words
        # Returns: dict mapping original_line_index -> {{start, end, word_indices}}
        anchors = {{}}
        used_word_ranges = []  # List of (start_idx, end_idx) to avoid reuse
        
        def words_overlap(range1, range2):
            """Check if two word index ranges overlap"""
            return not (range1[1] <= range2[0] or range2[1] <= range1[0])
        
        def find_best_match(orig_normalized, start_search_idx=0):
            """Find best matching word sequence for an original line"""
            if not orig_normalized:
                return None, None
            
            orig_words = orig_normalized.split()
            best_match = None
            best_score = 0
            best_range = None
            
            # Try to find matching sequence starting from different positions
            for start_idx in range(start_search_idx, min(start_search_idx + 50, len(all_words))):
                temp_words = []
                temp_text_parts = []
                
                for end_idx in range(start_idx, min(start_idx + 30, len(all_words))):
                    word = all_words[end_idx]
                    temp_words.append(word)
                    temp_text_parts.append(word["text"])
                    
                    temp_combined = ' '.join(temp_text_parts)
                    temp_words_list = temp_combined.split()
                    
                    # Calculate similarity score
                    orig_set = set(orig_words)
                    temp_set = set(temp_words_list)
                    overlap = len(orig_set & temp_set)
                    
                    # Score based on word overlap and length similarity
                    length_ratio = len(temp_combined) / max(len(orig_normalized), 1)
                    length_score = 1.0 if 0.7 <= length_ratio <= 1.3 else max(0, 1.0 - abs(length_ratio - 1.0))
                    
                    word_overlap_ratio = overlap / max(len(orig_words), 1)
                    score = word_overlap_ratio * 0.7 + length_score * 0.3
                    
                    # Check for containment
                    if orig_normalized in temp_combined or temp_combined in orig_normalized:
                        score = max(score, 0.9)
                    
                    if score > best_score and score >= 0.6:
                        best_score = score
                        best_match = {{
                            "start": temp_words[0]["start"],
                            "end": temp_words[-1]["end"],
                            "words": temp_words
                        }}
                        best_range = (start_idx, end_idx + 1)
                
                # Early exit if we found a very good match
                if best_score >= 0.9:
                    break
            
            return best_match, best_range
        
        # Sequential anchor finding to handle repeated lines correctly
        current_word_idx = 0
        anchor_line_indices = []
        
        for orig_idx, orig_line, orig_normalized in normalized_original_lines:
            if not orig_normalized:
                continue
            
            match, word_range = find_best_match(orig_normalized, current_word_idx)
            
            if match and word_range:
                # Check if this range overlaps with already used ranges
                is_overlapping = False
                for used_range in used_word_ranges:
                    if words_overlap(word_range, used_range):
                        is_overlapping = True
                        break
                
                if not is_overlapping:
                    anchors[orig_idx] = match
                    used_word_ranges.append(word_range)
                    anchor_line_indices.append(orig_idx)
                    # Move search position forward
                    current_word_idx = word_range[1]
        
        # Now build the final output with all lines
        # For anchored lines: use real timestamps
        # For interpolated lines: calculate timing based on neighbors
        
        output_lines = []
        
        # Get vocal time range from WhisperX
        if all_words:
            vocal_start = all_words[0]["start"]
            vocal_end = all_words[-1]["end"]
        else:
            vocal_start = 0
            vocal_end = 10  # fallback
        
        print(f"\\n=== Anchor Detection Results ===")
        print(f"Total original lines: {{len(original_lines)}}")
        print(f"Total WhisperX words: {{len(all_words)}}")
        print(f"Anchors found: {{len(anchors)}}")
        
        # Process each original line
        for orig_idx, orig_line, orig_normalized in normalized_original_lines:
            if not orig_line.strip():
                continue
            
            if orig_idx in anchors:
                # This is an anchor line - use real timestamps
                anchor_data = anchors[orig_idx]
                output_lines.append({{
                    "text": orig_line,
                    "start": round(anchor_data["start"], 3),
                    "end": round(anchor_data["end"], 3),
                    "is_anchor": True
                }})
                print(f"Anchor line {{orig_idx + 1}}: {{orig_line[:50]}}... -> {{anchor_data['start']:.2f}} - {{anchor_data['end']:.2f}}")
            else:
                # This line needs interpolation
                output_lines.append({{
                    "text": orig_line,
                    "start": None,
                    "end": None,
                    "is_anchor": False,
                    "orig_idx": orig_idx
                }})
        
        # Interpolate timing for non-anchor lines
        print(f"\\n=== Interpolation ===")
        
        def interpolate_timing(lines_to_interpolate, start_time, end_time, total_weight):
            """Distribute time range among lines proportionally to their weight"""
            if not lines_to_interpolate or total_weight <= 0:
                return
            
            current_time = start_time
            for i, line_data in enumerate(lines_to_interpolate):
                # Weight based on character count (proxy for syllables/duration)
                text_len = len(line_data["text"].strip())
                weight = max(1, text_len)
                
                # Proportional duration
                duration = (weight / total_weight) * (end_time - start_time)
                
                line_data["start"] = round(current_time, 3)
                line_data["end"] = round(current_time + duration, 3)
                
                current_time += duration
        
        # Process segments between anchors
        prev_anchor_end = vocal_start
        
        i = 0
        while i < len(output_lines):
            line_data = output_lines[i]
            
            if line_data["is_anchor"]:
                prev_anchor_end = line_data["end"]
                i += 1
                continue
            
            # Found a non-anchor line, collect the segment
            segment_start_idx = i
            segment_lines = []
            
            while i < len(output_lines) and not output_lines[i]["is_anchor"]:
                segment_lines.append(output_lines[i])
                i += 1
            
            # Determine time boundaries for this segment
            # Find previous anchor
            start_time = prev_anchor_end
            if segment_start_idx > 0:
                for j in range(segment_start_idx - 1, -1, -1):
                    if output_lines[j]["is_anchor"]:
                        start_time = output_lines[j]["end"]
                        break
            
            # Find next anchor
            end_time = vocal_end
            for j in range(i, len(output_lines)):
                if output_lines[j]["is_anchor"]:
                    end_time = output_lines[j]["start"]
                    break
            
            # Calculate total weight
            total_weight = sum(len(line["text"]) for line in segment_lines)
            
            if total_weight > 0 and end_time > start_time:
                interpolate_timing(segment_lines, start_time, end_time, total_weight)
                print(f"Interpolated lines {{segment_start_idx + 1}}-{{i}}: {{start_time:.2f}} - {{end_time:.2f}} ({{len(segment_lines)}} lines)")
        
        # Final statistics
        anchored_count = sum(1 for line in output_lines if line["is_anchor"])
        interpolated_count = sum(1 for line in output_lines if not line["is_anchor"])
        
        print(f"\\n=== Final Statistics ===")
        print(f"Original lyrics lines: {{len(original_lines)}}")
        print(f"WhisperX words found: {{len(all_words)}}")
        print(f"Anchor lines: {{anchored_count}}")
        print(f"Interpolated lines: {{interpolated_count}}")
        print(f"Total output lines: {{len(output_lines)}}")
        
        # Clean up internal fields and prepare final output
        final_output = {{
            "format": "whisperx_aligned",
            "version": 1,
            "lines": []
        }}
        
        for line_data in output_lines:
            final_output["lines"].append({{
                "text": line_data["text"],
                "start": line_data["start"],
                "end": line_data["end"]
            }})
        
        # Save output
        print(f"\\nSaving to {{OUTPUT_PATH}}")
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(final_output, f, ensure_ascii=False, indent=2)
        
        print(f"Success! Created {{len(final_output['lines'])}} lines")
        
    except Exception as e:
        print(f"ERROR: {{str(e)}}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
