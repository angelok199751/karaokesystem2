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
        # TWO-STAGE PROCESS: 1) Find candidates, 2) Validate strictly
        # Returns: dict mapping original_line_index -> {{start, end, word_indices, ...}}
        
        # STAGE 1: Find all candidate anchors
        candidates = []  # List of (orig_idx, match_data, word_range, similarity, matched_words_count)
        used_word_ranges = []  # List of (start_idx, end_idx) to avoid reuse
        
        def words_overlap(range1, range2):
            """Check if two word index ranges overlap"""
            return not (range1[1] <= range2[0] or range2[1] <= range1[0])
        
        def find_best_match(orig_normalized, start_search_idx=0):
            """Find best matching word sequence for an original line"""
            if not orig_normalized:
                return None, None, 0
            
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
            
            return best_match, best_range, best_score
        
        # Sequential candidate finding to handle repeated lines correctly
        current_word_idx = 0
        
        for orig_idx, orig_line, orig_normalized in normalized_original_lines:
            if not orig_normalized:
                continue
            
            match, word_range, similarity = find_best_match(orig_normalized, current_word_idx)
            
            if match and word_range:
                # Check if this range overlaps with already used ranges
                is_overlapping = False
                for used_range in used_word_ranges:
                    if words_overlap(word_range, used_range):
                        is_overlapping = True
                        break
                
                if not is_overlapping:
                    matched_words_count = len(match["words"])
                    duration = match["end"] - match["start"]
                    
                    candidates.append({{
                        "orig_idx": orig_idx,
                        "orig_line": orig_line,
                        "orig_normalized": orig_normalized,
                        "start": match["start"],
                        "end": match["end"],
                        "duration": duration,
                        "words": match["words"],
                        "word_range": word_range,
                        "similarity": similarity,
                        "matched_words": matched_words_count,
                        "text_length": len(orig_normalized),
                        "num_words_in_line": len(orig_normalized.split())
                    }})
                    used_word_ranges.append(word_range)
                    # Move search position forward past this match
                    current_word_idx = word_range[1]
        
        print(f"\\n=== Candidate Anchors Found: {{len(candidates)}} ===")
        
        # STAGE 2: Strict validation of candidates
        accepted_anchors = {{}}
        rejected_candidates = []
        last_accepted_end = -1
        
        def validate_candidate(cand, prev_end):
            """Validate a candidate anchor against strict criteria"""
            reasons = []
            
            # Criterion 1: Minimum similarity
            if cand["similarity"] < 0.65:
                reasons.append(f"similarity_too_low ({{cand['similarity']:.2f}} < 0.65)")
            
            # Criterion 2: Minimum matched words
            if cand["matched_words"] < 2:
                reasons.append(f"too_few_words ({{cand['matched_words']}} < 2)")
            
            # Criterion 3: Minimum duration (with soft check for short lines)
            min_duration_for_words = max(0.15, cand["num_words_in_line"] * 0.08)
            if cand["duration"] < min_duration_for_words:
                reasons.append(f"duration_too_short ({{cand['duration']:.2f}}s < {{min_duration_for_words:.2f}}s expected for {{cand['num_words_in_line']}} words)")
            
            # Criterion 4: Duration vs text length sanity check
            # Very long text cannot fit in very short duration
            words_per_sec = cand["num_words_in_line"] / max(cand["duration"], 0.01)
            if words_per_sec > 12:  # More than 12 words per second is suspicious
                reasons.append(f"unrealistic_speed ({{words_per_sec:.1f}} words/sec)")
            
            # Criterion 5: Sequential ordering (must come after previous accepted anchor)
            if cand["start"] < prev_end - 0.1:  # Small tolerance for rounding
                reasons.append(f"out_of_order (starts at {{cand['start']:.2f}} but prev ended at {{prev_end:.2f}})")
            
            return reasons
        
        for cand in candidates:
            validation_errors = validate_candidate(cand, last_accepted_end)
            
            if not validation_errors:
                # Accept this anchor
                accepted_anchors[cand["orig_idx"]] = {{
                    "start": cand["start"],
                    "end": cand["end"],
                    "duration": cand["duration"],
                    "words": cand["words"],
                    "word_range": cand["word_range"],
                    "similarity": cand["similarity"],
                    "matched_words": cand["matched_words"],
                    "text_length": cand["text_length"],
                    "num_words_in_line": cand["num_words_in_line"]
                }}
                last_accepted_end = cand["end"]
                print(f"ACCEPT anchor line {{cand['orig_idx'] + 1}}: sim={{cand['similarity']:.2f}}, words={{cand['matched_words']}}, dur={{cand['duration']:.2f}}s")
            else:
                # Reject this candidate
                rejected_candidates.append((cand, validation_errors))
                reason_str = "; ".join(validation_errors)
                print(f"REJECT anchor line {{cand['orig_idx'] + 1}}: sim={{cand['similarity']:.2f}}, words={{cand['matched_words']}}, dur={{cand['duration']:.2f}}s | REASONS: {{reason_str}}")
        
        print(f"\\n=== Anchor Validation Summary ===")
        print(f"Candidate anchors: {{len(candidates)}}")
        print(f"Accepted anchors: {{len(accepted_anchors)}}")
        print(f"Rejected anchors: {{len(rejected_candidates)}}")
        
        # Use accepted_anchors for further processing
        anchors = accepted_anchors
        
        # Now build the final output with all lines
        # For anchored lines: use anchor as reference point within the line
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
                # This is an anchor line - store anchor data for later processing
                anchor_data = anchors[orig_idx]
                output_lines.append({{
                    "text": orig_line,
                    "anchor_start": anchor_data["start"],
                    "anchor_end": anchor_data["end"],
                    "word_range": anchor_data["word_range"],
                    "text_length": anchor_data["text_length"],
                    "is_anchor": True,
                    "orig_idx": orig_idx
                }})
                print(f"Anchor line {{orig_idx + 1}}: {{orig_line[:50]}}... -> anchor at {{anchor_data['start']:.2f}} - {{anchor_data['end']:.2f}}")
            else:
                # This line needs interpolation
                output_lines.append({{
                    "text": orig_line,
                    "text_length": len(orig_normalized),
                    "is_anchor": False,
                    "orig_idx": orig_idx
                }})
        
        # Now calculate final start/end times for all lines
        print(f"\\n=== Calculating Line Timings ===")
        
        # Helper to calculate weight for a line
        def get_line_weight(line_data):
            """Weight based on text length (proxy for syllables/duration)"""
            return max(1, line_data.get("text_length", len(line_data["text"])))
        
        # Process all lines to assign start/end times
        prev_anchor_end = vocal_start
        i = 0
        
        while i < len(output_lines):
            line_data = output_lines[i]
            
            if line_data["is_anchor"]:
                # Find the next anchor to determine the end boundary for this anchor line
                next_anchor_start = vocal_end
                for j in range(i + 1, len(output_lines)):
                    if output_lines[j]["is_anchor"]:
                        next_anchor_start = output_lines[j]["anchor_start"]
                        break
                
                # For anchor lines, we need to distribute time between this anchor and the next
                # The anchor point should be somewhere within the line's duration
                # Use anchor_start as the line start, and interpolate to next anchor
                
                # Collect consecutive anchor lines (no interpolation needed between them)
                anchor_group_start = i
                anchor_group_end = i + 1
                
                # Look ahead for consecutive anchors
                while anchor_group_end < len(output_lines) and output_lines[anchor_group_end]["is_anchor"]:
                    anchor_group_end += 1
                
                # If there are more lines after this anchor group, find the next anchor or vocal_end
                if anchor_group_end < len(output_lines):
                    # There might be interpolated lines followed by an anchor
                    for j in range(anchor_group_end, len(output_lines)):
                        if output_lines[j]["is_anchor"]:
                            next_anchor_start = output_lines[j]["anchor_start"]
                            break
                
                # Process anchor lines in this group
                for k in range(anchor_group_start, anchor_group_end):
                    anchor_line = output_lines[k]
                    
                    # Determine start time
                    if k == anchor_group_start:
                        # First anchor in group: use previous boundary or anchor_start
                        line_start = max(prev_anchor_end, anchor_line["anchor_start"])
                    else:
                        # Subsequent anchors: use previous anchor's calculated end
                        line_start = output_lines[k - 1]["end"]
                    
                    # Determine end time
                    if k == anchor_group_end - 1:
                        # Last anchor in group: interpolate to next anchor or vocal_end
                        if anchor_group_end < len(output_lines):
                            # Find next anchor start
                            for j in range(anchor_group_end, len(output_lines)):
                                if output_lines[j]["is_anchor"]:
                                    next_anchor_start = output_lines[j]["anchor_start"]
                                    break
                            # Give this anchor line reasonable duration
                            # Use anchor_end as reference, but ensure it doesn't overlap with next anchor
                            line_end = min(anchor_line["anchor_end"], next_anchor_start - 0.1)
                        else:
                            # No more anchors, use vocal_end
                            line_end = vocal_end
                    else:
                        # Not the last anchor in group: end before next anchor in group
                        next_in_group = output_lines[k + 1]
                        line_end = next_in_group["anchor_start"] - 0.05
                    
                    # Ensure minimum duration
                    min_duration = 0.5
                    if line_end - line_start < min_duration:
                        # Extend end time, but don't overlap with next anchor
                        if k < len(output_lines) - 1 and output_lines[k + 1]["is_anchor"]:
                            max_end = output_lines[k + 1]["anchor_start"] - 0.05
                        else:
                            max_end = vocal_end
                        line_end = min(line_start + max(min_duration, anchor_line["anchor_end"] - anchor_line["anchor_start"]), max_end)
                    
                    anchor_line["start"] = round(line_start, 3)
                    anchor_line["end"] = round(line_end, 3)
                    
                    print(f"Line {{k + 1}} (ANCHOR): {{line_start:.2f}} - {{line_end:.2f}} ({{line_end - line_start:.2f}}s) | {{anchor_line['text'][:40]}}...")
                
                i = anchor_group_end
                if i > 0:
                    prev_anchor_end = output_lines[i - 1]["end"]
            else:
                # Found a non-anchor line, collect the segment of consecutive non-anchor lines
                segment_start_idx = i
                segment_lines = []
                
                while i < len(output_lines) and not output_lines[i]["is_anchor"]:
                    segment_lines.append(output_lines[i])
                    i += 1
                
                # Determine time boundaries for this segment
                # Find previous anchor end
                start_time = prev_anchor_end
                if segment_start_idx > 0:
                    for j in range(segment_start_idx - 1, -1, -1):
                        if output_lines[j]["is_anchor"]:
                            start_time = output_lines[j]["end"]
                            break
                
                # Find next anchor start
                end_time = vocal_end
                for j in range(i, len(output_lines)):
                    if output_lines[j]["is_anchor"]:
                        end_time = output_lines[j]["anchor_start"]
                        break
                
                # Calculate total weight
                total_weight = sum(get_line_weight(line) for line in segment_lines)
                
                if total_weight > 0 and end_time > start_time:
                    # Distribute time proportionally
                    current_time = start_time
                    for line_data in segment_lines:
                        weight = get_line_weight(line_data)
                        duration = (weight / total_weight) * (end_time - start_time)
                        
                        # Ensure minimum duration
                        duration = max(duration, 0.5)
                        
                        line_data["start"] = round(current_time, 3)
                        line_data["end"] = round(current_time + duration, 3)
                        
                        print(f"Line {{segment_lines.index(line_data) + segment_start_idx + 1}} (INTERP): {{line_data['start']:.2f}} - {{line_data['end']:.2f}} ({{duration:.2f}}s) | {{line_data['text'][:40]}}...")
                        
                        current_time += duration
                else:
                    # Fallback: assign minimal durations
                    current_time = start_time
                    for line_data in segment_lines:
                        line_data["start"] = round(current_time, 3)
                        line_data["end"] = round(current_time + 0.5, 3)
                        current_time += 0.5
        
        # Final validation and cleanup
        print(f"\\n=== Final Line Timings Validation ===")
        
        anchored_count = sum(1 for line in output_lines if line["is_anchor"])
        interpolated_count = sum(1 for line in output_lines if not line["is_anchor"])
        
        warnings_list = []
        
        for idx, line_data in enumerate(output_lines):
            duration = line_data["end"] - line_data["start"]
            
            # Check for suspiciously short lines
            if duration < 0.3:
                warnings_list.append(f"WARNING: Line {{idx + 1}} suspiciously short: {{duration:.3f}}s")
            
            # Check for suspiciously long lines
            if duration > 15:
                warnings_list.append(f"WARNING: Line {{idx + 1}} suspiciously long: {{duration:.3f}}s")
            
            # Check for overlapping lines
            if idx > 0:
                prev_end = output_lines[idx - 1]["end"]
                curr_start = line_data["start"]
                if curr_start < prev_end - 0.05:  # Allow small gap
                    warnings_list.append(f"WARNING: Lines {{idx}} and {{idx + 1}} may overlap: {{prev_end:.2f}} vs {{curr_start:.2f}}")
        
        for warning in warnings_list:
            print(warning)
        
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
