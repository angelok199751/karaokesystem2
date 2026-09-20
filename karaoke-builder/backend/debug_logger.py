"""
Debug Logger for Karaoke Builder

Provides structured logging with:
- Timestamp tracking
- Stage-specific logs
- stdout/stderr capture
- Error details
- System information
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import threading

from .config import LOGS_DIR, TEMP_DIR


class DebugLogger:
    """Thread-safe debug logger for pipeline stages"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.current_job_id: Optional[str] = None
        self.logs: List[Dict[str, Any]] = []
        self.stage_logs: Dict[str, List[Dict[str, Any]]] = {}
        
        # Setup file handler
        self.log_file = LOGS_DIR / f"karaoke-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        
        # Setup logging
        self.logger = logging.getLogger("karaoke_builder")
        self.logger.setLevel(logging.DEBUG)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # File handler
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        file_handler.setFormatter(file_format)
        self.logger.addHandler(file_handler)
    
    def start_job(self, job_id: str):
        """Start a new job/session"""
        self.current_job_id = job_id
        self.stage_logs = {}
        self._log("INFO", "PIPELINE", f"Job started: {job_id}")
    
    def end_job(self, success: bool):
        """End current job"""
        status = "completed successfully" if success else "failed"
        self._log("INFO", "PIPELINE", f"Job {self.current_job_id} {status}")
        self.current_job_id = None
    
    def start_stage(self, stage_name: str):
        """Mark stage start"""
        if self.current_job_id:
            self._log("INFO", stage_name, f"Stage started")
            if stage_name not in self.stage_logs:
                self.stage_logs[stage_name] = []
    
    def end_stage(self, stage_name: str, success: bool, duration: float, 
                  outputs: List[str] = None, exit_code: int = 0):
        """Mark stage end with results"""
        if self.current_job_id:
            status = "completed" if success else "failed"
            self._log("INFO" if success else "ERROR", stage_name, 
                     f"Stage {status} in {duration:.2f}s (exit code: {exit_code})")
            
            if outputs:
                for output in outputs:
                    self._log("INFO", stage_name, f"Output: {output}")
    
    def log_info(self, stage: str, message: str):
        """Log info message"""
        self._log("INFO", stage, message)
    
    def log_error(self, stage: str, message: str):
        """Log error message"""
        self._log("ERROR", stage, message)
    
    def log_warning(self, stage: str, message: str):
        """Log warning message"""
        self._log("WARNING", stage, message)
    
    def log_debug(self, stage: str, message: str):
        """Log debug message"""
        self._log("DEBUG", stage, message)
    
    def capture_stdout(self, stage: str, output: str):
        """Capture stdout from external process"""
        if output.strip():
            self._log("INFO", f"{stage}_stdout", output[:2000])  # Limit size
    
    def capture_stderr(self, stage: str, error: str):
        """Capture stderr from external process"""
        if error.strip():
            self._log("ERROR", f"{stage}_stderr", error[:5000])  # Larger limit for errors
    
    def _log(self, level: str, stage: str, message: str):
        """Internal log method"""
        timestamp = datetime.now().isoformat()
        
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "stage": stage,
            "message": message,
            "job_id": self.current_job_id
        }
        
        self.logs.append(log_entry)
        
        if stage in self.stage_logs:
            self.stage_logs[stage].append(log_entry)
        
        # Log to file
        log_message = f"[{stage}] {message}"
        if level == "ERROR":
            self.logger.error(log_message)
        elif level == "WARNING":
            self.logger.warning(log_message)
        elif level == "DEBUG":
            self.logger.debug(log_message)
        else:
            self.logger.info(log_message)
    
    def get_logs(self, stage: str = None) -> List[Dict[str, Any]]:
        """Get logs, optionally filtered by stage"""
        if stage:
            return self.stage_logs.get(stage, [])
        return self.logs
    
    def get_debug_report(self) -> str:
        """Generate full debug report for copying/saving"""
        report_lines = [
            "=" * 60,
            "Karaoke Builder Debug Report",
            "=" * 60,
            f"Generated: {datetime.now().isoformat()}",
            f"Job ID: {self.current_job_id or 'N/A'}",
            "",
            "=" * 60,
            "SYSTEM INFORMATION",
            "=" * 60,
        ]
        
        # Add system info
        try:
            import platform
            import torch
            
            report_lines.extend([
                f"OS: {platform.system()} {platform.release()}",
                f"Python: {sys.version}",
                f"PyTorch: {torch.__version__}",
                f"CUDA Available: {torch.cuda.is_available()}",
            ])
            
            if torch.cuda.is_available():
                report_lines.extend([
                    f"GPU Count: {torch.cuda.device_count()}",
                    f"GPU Name: {torch.cuda.get_device_name(0)}",
                ])
        except Exception as e:
            report_lines.append(f"Error getting system info: {e}")
        
        report_lines.extend([
            "",
            "=" * 60,
            "PIPELINE LOGS",
            "=" * 60,
        ])
        
        # Add all logs
        for log in self.logs:
            report_lines.append(
                f"{log['timestamp']} [{log['level']}] {log['stage']}: {log['message']}"
            )
        
        report_lines.extend([
            "",
            "=" * 60,
            "END OF REPORT",
            "=" * 60,
        ])
        
        return "\n".join(report_lines)
    
    def save_debug_log(self, filepath: str = None) -> str:
        """Save debug log to file"""
        if filepath is None:
            filepath = LOGS_DIR / f"karaoke-debug-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        
        report = self.get_debug_report()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return str(filepath)
    
    def clear(self):
        """Clear all logs"""
        self.logs = []
        self.stage_logs = {}


# Global instance
debug_logger = DebugLogger()
