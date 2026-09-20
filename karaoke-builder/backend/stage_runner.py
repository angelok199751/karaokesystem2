"""
Stage Runner for Karaoke Builder

Universal mechanism for running pipeline stages with:
- Automatic logging
- stdout/stderr capture
- Exit code tracking
- Output file verification
- Structured results
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime

# Fix imports when run directly
if __name__ != "__main__":
    try:
        from .debug_logger import debug_logger
    except ImportError:
        from backend.debug_logger import debug_logger

from backend.config import TEMP_DIR


@dataclass
class StageResult:
    """Structured result from a stage execution"""
    success: bool
    stage: str
    duration: float
    outputs: List[str]
    stdout: str
    stderr: str
    exit_code: int
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StageRunner:
    """Universal runner for pipeline stages"""
    
    def __init__(self, job_id: str, work_dir: Path):
        self.job_id = job_id
        self.work_dir = work_dir
        self.results: Dict[str, StageResult] = {}
    
    def run(
        self,
        name: str,
        command: Union[str, List[str]],
        input_files: List[Path] = None,
        output_files: List[Path] = None,
        env: Dict[str, str] = None,
        timeout: int = 600,
        check_outputs: bool = True,
    ) -> StageResult:
        """
        Run a stage with full logging and monitoring
        
        Args:
            name: Stage name (e.g., "Demucs", "WhisperX")
            command: Command to execute (string or list)
            input_files: List of input file paths to verify
            output_files: List of expected output file paths
            env: Environment variables to set
            timeout: Timeout in seconds
            check_outputs: Whether to verify output files exist
            
        Returns:
            StageResult with success status and details
        """
        start_time = time.time()
        
        debug_logger.start_stage(name)
        debug_logger.log_info(name, f"Starting stage: {name}")
        
        # Verify input files
        if input_files:
            for input_file in input_files:
                if not input_file.exists():
                    error_msg = f"Input file not found: {input_file}"
                    debug_logger.log_error(name, error_msg)
                    return StageResult(
                        success=False,
                        stage=name,
                        duration=0,
                        outputs=[],
                        stdout="",
                        stderr=error_msg,
                        exit_code=-1,
                        error_message=error_msg
                    )
                debug_logger.log_info(name, f"Input: {input_file.name} ({self._format_size(input_file)})")
        
        # Prepare command
        if isinstance(command, str):
            cmd_str = command
            shell = True
        else:
            cmd_str = " ".join(command)
            shell = False
        
        debug_logger.log_info(name, f"Command: {cmd_str}")
        
        # Setup environment
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        
        # Execute
        stdout_lines = []
        stderr_lines = []
        exit_code = -1
        
        try:
            debug_logger.log_info(name, f"Executing... (timeout: {timeout}s)")
            
            process = subprocess.Popen(
                command,
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                env=process_env,
                cwd=str(self.work_dir),
            )
            
            try:
                stdout_bytes, stderr_bytes = process.communicate(timeout=timeout)
                stdout_text = stdout_bytes.decode('utf-8', errors='replace')
                stderr_text = stderr_bytes.decode('utf-8', errors='replace')
                exit_code = process.returncode
                
                stdout_lines = stdout_text.split('\n')
                stderr_lines = stderr_text.split('\n')
                
                # Log output (first/last few lines to avoid spam)
                if stdout_text.strip():
                    debug_logger.capture_stdout(name, stdout_text[:2000])
                
                if stderr_text.strip():
                    debug_logger.capture_stderr(name, stderr_text)
                    
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                error_msg = f"Stage timed out after {timeout} seconds"
                debug_logger.log_error(name, error_msg)
                
                return StageResult(
                    success=False,
                    stage=name,
                    duration=time.time() - start_time,
                    outputs=[],
                    stdout='\n'.join(stdout_lines),
                    stderr=error_msg,
                    exit_code=-1,
                    error_message=error_msg
                )
                
        except Exception as e:
            error_msg = f"Stage execution failed: {str(e)}"
            debug_logger.log_error(name, error_msg)
            
            return StageResult(
                success=False,
                stage=name,
                duration=time.time() - start_time,
                outputs=[],
                stdout='\n'.join(stdout_lines),
                stderr=error_msg,
                exit_code=-1,
                error_message=error_msg
            )
        
        duration = time.time() - start_time
        
        # Check exit code
        if exit_code != 0:
            error_msg = f"Process exited with code {exit_code}"
            debug_logger.log_error(name, error_msg)
            
            # Verify if any outputs were created despite error
            outputs = []
            if output_files and check_outputs:
                for output_file in output_files:
                    if output_file.exists():
                        outputs.append(str(output_file))
                        debug_logger.log_info(name, f"Output created despite error: {output_file.name}")
            
            debug_logger.end_stage(name, False, duration, outputs, exit_code)
            
            return StageResult(
                success=False,
                stage=name,
                duration=duration,
                outputs=outputs,
                stdout='\n'.join(stdout_lines),
                stderr=stderr_text if stderr_text.strip() else error_msg,
                exit_code=exit_code,
                error_message=error_msg
            )
        
        # Verify output files
        outputs = []
        if output_files and check_outputs:
            for output_file in output_files:
                if output_file.exists():
                    outputs.append(str(output_file))
                    debug_logger.log_info(name, f"Output: {output_file.name} ({self._format_size(output_file)})")
                else:
                    error_msg = f"Expected output file not found: {output_file}"
                    debug_logger.log_error(name, error_msg)
                    
                    debug_logger.end_stage(name, False, duration, [], exit_code)
                    
                    return StageResult(
                        success=False,
                        stage=name,
                        duration=duration,
                        outputs=[],
                        stdout='\n'.join(stdout_lines),
                        stderr=error_msg,
                        exit_code=exit_code,
                        error_message=error_msg
                    )
        
        # Success
        debug_logger.end_stage(name, True, duration, outputs, exit_code)
        
        result = StageResult(
            success=True,
            stage=name,
            duration=duration,
            outputs=outputs,
            stdout='\n'.join(stdout_lines),
            stderr='\n'.join(stderr_lines),
            exit_code=exit_code
        )
        
        self.results[name] = result
        return result
    
    def _format_size(self, path: Path) -> str:
        """Format file size in human-readable form"""
        try:
            size_bytes = path.stat().st_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.1f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.1f} TB"
        except Exception:
            return "unknown size"
    
    def get_all_results(self) -> Dict[str, StageResult]:
        """Get all stage results"""
        return self.results
    
    def get_failed_stages(self) -> List[str]:
        """Get list of failed stage names"""
        return [name for name, result in self.results.items() if not result.success]
