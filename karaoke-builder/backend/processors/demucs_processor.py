"""
Demucs Processor for Karaoke Builder

Stage 1: Vocal Separation
Separates vocals from instrumental using Demucs
"""

import os
import sys
from pathlib import Path
from typing import List

from .base_processor import BaseProcessor, ProcessorContext
from ..stage_runner import StageResult
from ..debug_logger import debug_logger
from ..config import DEMUCS_MODEL, DEMUCS_TIMEOUT


class DemucsProcessor(BaseProcessor):
    """Processor for vocal/instrumental separation using Demucs"""
    
    @property
    def name(self) -> str:
        return "Demucs"
    
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
        
        # Define expected output files
        # Demucs creates: htmodel/vocals.wav and htmodel/instrumental.wav
        model_dir = demucs_dir / DEMUCS_MODEL
        vocals_file = model_dir / "vocals.wav"
        instrumental_file = model_dir / "instrumental.wav"
        
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
        
        # Run Demucs
        runner = StageRunner(self.context.job_id, self.work_dir)
        result = runner.run(
            name=self.name,
            command=command,
            input_files=[self.context.input_file],
            output_files=[vocals_file, instrumental_file],
            timeout=DEMUCS_TIMEOUT,
        )
        
        # Update context on success
        if result.success:
            self.context.vocals_file = vocals_file
            self.context.instrumental_file = instrumental_file
            
            # Copy files to demucs root for easier access
            import shutil
            vocals_root = demucs_dir / "vocals.wav"
            instrumental_root = demucs_dir / "instrumental.wav"
            
            shutil.copy2(vocals_file, vocals_root)
            shutil.copy2(instrumental_file, instrumental_root)
            
            self.context.vocals_file = vocals_root
            self.context.instrumental_file = instrumental_root
            
            debug_logger.log_info(self.name, f"Vocals: {vocals_root.name}")
            debug_logger.log_info(self.name, f"Instrumental: {instrumental_root.name}")
        
        return result
