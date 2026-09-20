"""
Karaoke Format Model for Karaoke Builder

Defines the internal karaoke JSON format structure and validation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class WordTiming:
    """Word-level timing"""
    text: str
    start: float
    end: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "start": round(self.start, 3),
            "end": round(self.end, 3)
        }


@dataclass
class LyricsLine:
    """Single line of lyrics with timings"""
    start: float
    end: float
    text: str
    words: List[WordTiming] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "text": self.text,
            "words": [w.to_dict() for w in self.words]
        }


@dataclass
class PitchPoint:
    """Single pitch measurement point"""
    time: float
    frequency: float
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "time": round(self.time, 3),
            "frequency": round(self.frequency, 2),
            "confidence": round(self.confidence, 4)
        }


@dataclass
class KaraokeProject:
    """Complete karaoke project in internal format"""
    
    title: str
    duration: float
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    builder_version: str = "0.1.0-prototype"
    
    lines: List[LyricsLine] = field(default_factory=list)
    pitch_points: List[PitchPoint] = field(default_factory=list)
    pitch_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_line(self, start: float, end: float, text: str, 
                 words: List[Dict[str, Any]] = None):
        """Add a lyrics line"""
        word_objects = []
        if words:
            for w in words:
                word_objects.append(WordTiming(
                    text=w.get("text", ""),
                    start=w.get("start", 0),
                    end=w.get("end", 0)
                ))
        
        self.lines.append(LyricsLine(
            start=start,
            end=end,
            text=text,
            words=word_objects
        ))
    
    def add_pitch_point(self, time: float, frequency: float, confidence: float):
        """Add a pitch measurement point"""
        self.pitch_points.append(PitchPoint(
            time=time,
            frequency=frequency,
            confidence=confidence
        ))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "format": "karaoke",
            "version": 1,
            
            "metadata": {
                "title": self.title,
                "duration": round(self.duration, 2),
                "created_at": self.created_at,
                "builder_version": self.builder_version
            },
            
            "lyrics": {
                "lines": [line.to_dict() for line in self.lines]
            },
            
            "pitch": {
                "metadata": self.pitch_metadata,
                "points": [p.to_dict() for p in self.pitch_points]
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KaraokeProject":
        """Create from dictionary (deserialization)"""
        project = cls(
            title=data.get("metadata", {}).get("title", "Unknown"),
            duration=data.get("metadata", {}).get("duration", 0),
            created_at=data.get("metadata", {}).get("created_at", ""),
            builder_version=data.get("metadata", {}).get("builder_version", "")
        )
        
        # Load lyrics
        lyrics_data = data.get("lyrics", {})
        for line_data in lyrics_data.get("lines", []):
            project.add_line(
                start=line_data.get("start", 0),
                end=line_data.get("end", 0),
                text=line_data.get("text", ""),
                words=line_data.get("words", [])
            )
        
        # Load pitch
        pitch_data = data.get("pitch", {})
        project.pitch_metadata = pitch_data.get("metadata", {})
        
        for point_data in pitch_data.get("points", []):
            project.add_pitch_point(
                time=point_data.get("time", 0),
                frequency=point_data.get("frequency", 0),
                confidence=point_data.get("confidence", 0)
            )
        
        return project
    
    def validate(self) -> List[str]:
        """
        Validate the project structure
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not self.title:
            errors.append("Title is required")
        
        if self.duration <= 0:
            errors.append("Duration must be positive")
        
        if not self.lines:
            errors.append("At least one lyrics line is required")
        
        # Check line ordering
        prev_end = 0
        for i, line in enumerate(self.lines):
            if line.start < 0:
                errors.append(f"Line {i+1}: start time cannot be negative")
            if line.end <= line.start:
                errors.append(f"Line {i+1}: end time must be after start time")
            if line.start < prev_end:
                errors.append(f"Line {i+1}: lines should not overlap")
            prev_end = line.end
        
        return errors
    
    def get_active_line(self, current_time: float) -> Optional[int]:
        """
        Get index of active line at given time
        
        Args:
            current_time: Current playback time in seconds
            
        Returns:
            Line index or None if no line is active
        """
        for i, line in enumerate(self.lines):
            if line.start <= current_time <= line.end:
                return i
        return None
    
    def get_active_word(self, current_time: float) -> Optional[int]:
        """
        Get index of active word in current line
        
        Args:
            current_time: Current playback time in seconds
            
        Returns:
            Word index within current line, or None
        """
        line_idx = self.get_active_line(current_time)
        if line_idx is None:
            return None
        
        line = self.lines[line_idx]
        for i, word in enumerate(line.words):
            if word.start <= current_time <= word.end:
                return i
        return None
