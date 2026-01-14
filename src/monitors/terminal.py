"""
Terminal output monitoring for error detection and status updates.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Awaitable, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class TerminalEventType(Enum):
    """Types of terminal events."""
    ERROR = "error"
    WARNING = "warning"
    SUCCESS = "success"
    PROGRESS = "progress"
    OUTPUT = "output"


@dataclass
class TerminalEvent:
    """A terminal event detected from output."""
    
    type: TerminalEventType
    message: str
    details: Optional[str] = None
    command: Optional[str] = None
    exit_code: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)


# Error pattern matchers
ERROR_PATTERNS = [
    # Common error patterns
    (re.compile(r"(?i)error[:\s](.+)", re.MULTILINE), "error"),
    (re.compile(r"(?i)failed[:\s](.+)", re.MULTILINE), "error"),
    (re.compile(r"(?i)exception[:\s](.+)", re.MULTILINE), "error"),
    (re.compile(r"(?i)fatal[:\s](.+)", re.MULTILINE), "error"),
    
    # Exit code patterns
    (re.compile(r"exit(?:ed with)?\s*(?:code|status)?\s*(\d+)", re.IGNORECASE), "exit_code"),
    
    # Stack traces
    (re.compile(r"Traceback \(most recent call last\):(.+?)(?=\n\n|\Z)", re.DOTALL), "stack_trace"),
    (re.compile(r"at [\w.$]+\([\w.:]+\)", re.MULTILINE), "stack_trace"),
    
    # Build/test specific
    (re.compile(r"(?i)build failed", re.MULTILINE), "error"),
    (re.compile(r"(?i)test failed", re.MULTILINE), "error"),
    (re.compile(r"(?i)compilation failed", re.MULTILINE), "error"),
    (re.compile(r"npm ERR!", re.MULTILINE), "error"),
]

# Warning patterns
WARNING_PATTERNS = [
    (re.compile(r"(?i)warning[:\s](.+)", re.MULTILINE), "warning"),
    (re.compile(r"(?i)deprecated[:\s](.+)", re.MULTILINE), "warning"),
]

# Success patterns
SUCCESS_PATTERNS = [
    (re.compile(r"(?i)success(?:fully)?[:\s]?(.+)?", re.MULTILINE), "success"),
    (re.compile(r"(?i)completed successfully", re.MULTILINE), "success"),
    (re.compile(r"(?i)build succeeded", re.MULTILINE), "success"),
    (re.compile(r"(?i)all tests passed", re.MULTILINE), "success"),
]

# Progress patterns
PROGRESS_PATTERNS = [
    (re.compile(r"(\d+)%"), "percent"),
    (re.compile(r"(\d+)/(\d+)"), "fraction"),
    (re.compile(r"(?i)building[:\s]?(.+)?", re.MULTILINE), "building"),
    (re.compile(r"(?i)installing[:\s]?(.+)?", re.MULTILINE), "installing"),
    (re.compile(r"(?i)running[:\s]?(.+)?", re.MULTILINE), "running"),
]


class TerminalMonitor:
    """
    Monitors terminal output for errors, warnings, and progress.
    """
    
    def __init__(
        self,
        on_error: Optional[Callable[[TerminalEvent], Awaitable[None]]] = None,
        on_warning: Optional[Callable[[TerminalEvent], Awaitable[None]]] = None,
        on_success: Optional[Callable[[TerminalEvent], Awaitable[None]]] = None,
        on_progress: Optional[Callable[[TerminalEvent], Awaitable[None]]] = None,
    ):
        self.on_error = on_error
        self.on_warning = on_warning
        self.on_success = on_success
        self.on_progress = on_progress
        
        self._current_command: Optional[str] = None
        self._output_buffer: list[str] = []
        self._last_progress: Optional[int] = None
    
    def set_current_command(self, command: str) -> None:
        """Set the current command being monitored."""
        self._current_command = command
        self._output_buffer = []
        self._last_progress = None
    
    async def process_output(self, output: str) -> list[TerminalEvent]:
        """
        Process terminal output and detect events.
        
        Args:
            output: Terminal output to process
            
        Returns:
            List of detected events
        """
        events: list[TerminalEvent] = []
        self._output_buffer.append(output)
        
        # Check for errors
        for pattern, pattern_type in ERROR_PATTERNS:
            matches = pattern.findall(output)
            if matches:
                if pattern_type == "exit_code":
                    exit_code = int(matches[0]) if matches else None
                    if exit_code and exit_code != 0:
                        event = TerminalEvent(
                            type=TerminalEventType.ERROR,
                            message=f"Command exited with code {exit_code}",
                            command=self._current_command,
                            exit_code=exit_code,
                        )
                        events.append(event)
                        if self.on_error:
                            await self.on_error(event)
                elif pattern_type == "stack_trace":
                    # Get full stack trace
                    full_output = "\n".join(self._output_buffer)
                    event = TerminalEvent(
                        type=TerminalEventType.ERROR,
                        message="Stack trace detected",
                        details=output,
                        command=self._current_command,
                    )
                    events.append(event)
                    if self.on_error:
                        await self.on_error(event)
                else:
                    match_text = matches[0] if isinstance(matches[0], str) else str(matches[0])
                    event = TerminalEvent(
                        type=TerminalEventType.ERROR,
                        message=match_text[:200],
                        details=output,
                        command=self._current_command,
                    )
                    events.append(event)
                    if self.on_error:
                        await self.on_error(event)
        
        # Check for warnings (only if no errors found)
        if not events:
            for pattern, _ in WARNING_PATTERNS:
                matches = pattern.findall(output)
                if matches:
                    match_text = matches[0] if isinstance(matches[0], str) else str(matches[0])
                    event = TerminalEvent(
                        type=TerminalEventType.WARNING,
                        message=match_text[:200],
                        command=self._current_command,
                    )
                    events.append(event)
                    if self.on_warning:
                        await self.on_warning(event)
                    break
        
        # Check for success
        for pattern, _ in SUCCESS_PATTERNS:
            if pattern.search(output):
                event = TerminalEvent(
                    type=TerminalEventType.SUCCESS,
                    message="Operation completed successfully",
                    command=self._current_command,
                )
                events.append(event)
                if self.on_success:
                    await self.on_success(event)
                break
        
        # Check for progress
        for pattern, pattern_type in PROGRESS_PATTERNS:
            matches = pattern.findall(output)
            if matches:
                if pattern_type == "percent":
                    progress = int(matches[-1])  # Use last match
                    if progress != self._last_progress:
                        self._last_progress = progress
                        event = TerminalEvent(
                            type=TerminalEventType.PROGRESS,
                            message=f"Progress: {progress}%",
                            command=self._current_command,
                        )
                        events.append(event)
                        if self.on_progress:
                            await self.on_progress(event)
                elif pattern_type == "fraction":
                    current, total = matches[-1]
                    progress = int(int(current) / int(total) * 100)
                    if progress != self._last_progress:
                        self._last_progress = progress
                        event = TerminalEvent(
                            type=TerminalEventType.PROGRESS,
                            message=f"Progress: {current}/{total}",
                            command=self._current_command,
                        )
                        events.append(event)
                        if self.on_progress:
                            await self.on_progress(event)
                break
        
        return events
    
    def get_full_output(self) -> str:
        """Get the full buffered output."""
        return "\n".join(self._output_buffer)
    
    def clear_buffer(self) -> None:
        """Clear the output buffer."""
        self._output_buffer = []
        self._last_progress = None


def extract_error_summary(output: str, max_length: int = 500) -> str:
    """
    Extract a concise error summary from terminal output.
    
    Args:
        output: Full terminal output
        max_length: Maximum length of the summary
        
    Returns:
        Concise error summary
    """
    lines = output.strip().split("\n")
    
    # Look for error lines
    error_lines = []
    for line in lines:
        lower = line.lower()
        if any(kw in lower for kw in ["error", "failed", "exception", "fatal"]):
            error_lines.append(line.strip())
    
    if error_lines:
        # Return the most relevant error lines
        summary = "\n".join(error_lines[:5])
    else:
        # Return the last few lines
        summary = "\n".join(lines[-10:])
    
    if len(summary) > max_length:
        summary = summary[:max_length - 3] + "..."
    
    return summary
