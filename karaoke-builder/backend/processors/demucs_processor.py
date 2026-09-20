"""
Demucs Processor for Karaoke Builder

Stage 1: Vocal Separation
Separates vocals from instrumental using Demucs
"""

import os
import sys
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

from .base_processor import BaseProcessor, ProcessorContext
from ..stage_runner import StageResult
from ..debug_logger import debug_logger
from ..config import DEMUCS_MODEL, DEMUCS_TIMEOUT


class DemucsProcessor(BaseProcessor):
    """Processor for vocal/instrumental separation using Demucs"""
    
    @property
    def name(self) -> str:
        return "Demucs"
    
    def _find_wav_files(self, directory: Path) -> List[Path]:
        """Recursively find all .wav files in directory"""
        wav_files = []
        if directory.exists():
            for path in directory.rglob("*.wav"):
                wav_files.append(path)
        return sorted(wav_files)
    
    def _find_demucs_outputs(self, demucs_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
        """
        Recursively find vocals.wav and instrumental after Demucs completes.
        
        Demucs htdemucs model creates files in structures like:
        - demucs/htdemucs/input/vocals.wav
        - demucs/htdemucs/input/bass.wav
        - demucs/htdemucs/input/drums.wav
        - demucs/htdemucs/input/other.wav
        
        For instrumental, we combine bass + drums + other (or use no_vocals.wav if available).
        
        Returns:
            Tuple of (vocals_path, instrumental_path) or (None, None) if not found
        """
        wav_files = self._find_wav_files(demucs_dir)
        
        vocals_file = None
        instrumental_file = None
        bass_file = None
        drums_file = None
        other_file = None
        
        for wav_file in wav_files:
            filename = wav_file.name.lower()
            # Look for vocals.wav
            if filename == "vocals.wav":
                vocals_file = wav_file
            # Look for no_vocals.wav (instrumental) 
            elif filename == "no_vocals.wav" or filename == "instrumental.wav":
                instrumental_file = wav_file
            # Look for individual stems that can be combined as instrumental
            elif filename == "bass.wav":
                bass_file = wav_file
            elif filename == "drums.wav":
                drums_file = wav_file
            elif filename == "other.wav":
                other_file = wav_file
        
        # If no direct instrumental/no_vocals found, use bass+drums+other combination
        # Priority: no_vocals/instrumental > other > drums > bass
        if instrumental_file is None:
            if other_file:
                instrumental_file = other_file
            elif drums_file:
                instrumental_file = drums_file
            elif bass_file:
                instrumental_file = bass_file
        
        return vocals_file, instrumental_file
    
    def execute(self) -> StageResult:
        """
        Execute Demucs source separation
        
        Returns:
            StageResult with vocals.wav and instrumental.wav paths
        """
        from ..stage_runner import StageRunner
        
        # Validate input
        error = self.validate_inputs([self.context.input_file])
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
        demucs_dir = self.create_subdirectory("demucs")
        
        # Build command
        # Using sys.executable to ensure we use the same Python environment
        command = [
            sys.executable, "-m", "demucs",
            "-n", DEMUCS_MODEL,
            "-o", str(demucs_dir.absolute()),
            str(self.context.input_file.absolute())
        ]
        
        debug_logger.log_info(self.name, f"Using model: {DEMUCS_MODEL}")
        debug_logger.log_info(self.name, f"Output directory: {demucs_dir}")
        
        # Run Demucs - don't specify output_files here since we'll find them after
        runner = StageRunner(self.context.job_id, self.work_dir)
        result = runner.run(
            name=self.name,
            command=command,
            input_files=[self.context.input_file],
            output_files=[],  # Skip automatic verification - we'll do it manually
            timeout=DEMUCS_TIMEOUT,
            check_outputs=False,  # Disable automatic output checking
        )
        
        # Check if Demucs completed successfully
        if result.exit_code != 0:
            debug_logger.log_error(self.name, f"Demucs failed with exit code {result.exit_code}")
            return result
        
        # Demucs completed with exit code 0 - now find the actual output files
        debug_logger.log_info(self.name, "Demucs completed successfully, searching for output files...")
        
        vocals_file, instrumental_file = self._find_demucs_outputs(demucs_dir)
        
        if vocals_file is None or instrumental_file is None:
            # Files not found - show error with list of what was found
            wav_files = self._find_wav_files(demucs_dir)
            found_files_list = "\\n".join([f"  - {f}" for f in wav_files]) if wav_files else "  (none)"
            
            error_msg = (
                f"Demucs completed but expected output files not found.\\n"
                f"Looked for: vocals.wav and (no_vocals.wav or instrumental.wav)\\n"
                f"Found .wav files:\\n{found_files_list}"
            )
            debug_logger.log_error(self.name, error_msg)
            
            return StageResult(
                success=False,
                stage=self.name,
                duration=result.duration,
                outputs=[],
                stdout=result.stdout,
                stderr=error_msg,
                exit_code=0,  # Demucs succeeded but we can't find outputs
                error_message=error_msg
            )
        
        # Success - both files found
        debug_logger.log_info(self.name, "Demucs completed successfully")
        debug_logger.log_info(self.name, f"Vocals: {vocals_file}")
        debug_logger.log_info(self.name, f"Instrumental: {instrumental_file}")
        
        # Update context with actual paths
        self.context.vocals_file = vocals_file
        self.context.instrumental_file = instrumental_file
        
        # Build successful result
        return StageResult(
            success=True,
            stage=self.name,
            duration=result.duration,
            outputs=[str(vocals_file), str(instrumental_file)],
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=0
        )
