"""
Base Processor for Karaoke Builder

Abstract base class for all pipeline processors.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

import sys
from pathlib import Path as P
sys.path.insert(0, str(P(__file__).parent.parent))

from stage_runner import StageResult


@dataclass
class ProcessorContext:
    """Context passed to processors"""
    job_id: str
    work_dir: Path
    input_file: Optional[Path] = None
    lyrics_file: Optional[Path] = None
    title: str = ""
    
    # Intermediate results
    vocals_file: Optional[Path] = None
    instrumental_file: Optional[Path] = None
    words_json: Optional[Path] = None
    pitch_json: Optional[Path] = None
    
    # Final outputs
    karaoke_json: Optional[Path] = None
    minus_mp3: Optional[Path] = None


class BaseProcessor(ABC):
    """Abstract base class for all processors"""
    
    def __init__(self, context: ProcessorContext):
        self.context = context
        self.work_dir = context.work_dir
    
    @abstractmethod
    def execute(self) -> StageResult:
        """
        Execute the processor
        
        Returns:
            StageResult with success status and details
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Processor name for logging"""
        pass
    
    def validate_inputs(self, required_files: List[Path]) -> Optional[str]:
        """
        Validate that required input files exist
        
        Returns:
            Error message if validation fails, None if success
        """
        for file_path in required_files:
            if not file_path.exists():
                return f"Required file not found: {file_path}"
            if file_path.stat().st_size == 0:
                return f"File is empty: {file_path}"
        return None
    
    def create_subdirectory(self, name: str) -> Path:
        """Create and return a subdirectory in work_dir"""
        subdir = self.work_dir / name
        subdir.mkdir(exist_ok=True)
        return subdir
