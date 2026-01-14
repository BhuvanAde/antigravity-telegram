"""
Message formatting utilities for Telegram output.
"""

from pathlib import Path
from typing import Optional


def format_plan_message(
    plan_summary: str,
    files_affected: list[str] | None = None,
    task_name: str | None = None,
) -> str:
    """
    Format a plan approval message.
    
    Args:
        plan_summary: Summary of the implementation plan
        files_affected: List of files that will be modified
        task_name: Optional task name/title
        
    Returns:
        Formatted markdown message
    """
    lines = []
    
    if task_name:
        lines.append(f"📋 *Implementation Plan: {escape_markdown(task_name)}*")
    else:
        lines.append("📋 *Implementation Plan*")
    
    lines.append("")
    lines.append(escape_markdown(plan_summary))
    
    if files_affected:
        lines.append("")
        lines.append("📁 *Files to be modified:*")
        for file_path in files_affected[:10]:  # Limit to 10 files
            filename = Path(file_path).name
            lines.append(f"  • `{escape_markdown(filename)}`")
        if len(files_affected) > 10:
            lines.append(f"  _...and {len(files_affected) - 10} more files_")
    
    lines.append("")
    lines.append("_Please review and approve to continue._")
    
    return "\n".join(lines)


def format_change_message(
    change_summary: str,
    diff_preview: str | None = None,
) -> str:
    """
    Format a code change approval message.
    
    Args:
        change_summary: Summary of the changes
        diff_preview: Optional diff preview
        
    Returns:
        Formatted markdown message
    """
    lines = []
    
    lines.append("✏️ *Code Change Review*")
    lines.append("")
    lines.append(escape_markdown(change_summary))
    
    if diff_preview:
        lines.append("")
        lines.append("```diff")
        # Truncate diff if too long
        if len(diff_preview) > 1000:
            lines.append(diff_preview[:1000])
            lines.append("... (truncated)")
        else:
            lines.append(diff_preview)
        lines.append("```")
    
    return "\n".join(lines)


def format_error_message(
    error_message: str,
    stack_trace: str | None = None,
    command: str | None = None,
) -> str:
    """
    Format a critical error message.
    
    Args:
        error_message: The error message
        stack_trace: Optional stack trace
        command: Optional command that caused the error
        
    Returns:
        Formatted markdown message
    """
    lines = []
    
    lines.append("🚨 *CRITICAL ERROR*")
    lines.append("")
    
    if command:
        lines.append(f"Command: `{escape_markdown(command)}`")
        lines.append("")
    
    lines.append(escape_markdown(error_message))
    
    if stack_trace:
        lines.append("")
        lines.append("```")
        # Truncate stack trace if too long
        if len(stack_trace) > 2000:
            lines.append(stack_trace[-2000:])  # Show last 2000 chars (most relevant)
        else:
            lines.append(stack_trace)
        lines.append("```")
    
    return "\n".join(lines)


def format_status_message(
    status_text: str,
    progress_percent: int | None = None,
    steps: list[tuple[str, bool]] | None = None,
) -> str:
    """
    Format a status ticker message.
    
    Args:
        status_text: Current status description
        progress_percent: Optional progress percentage (0-100)
        steps: Optional list of (step_name, completed) tuples
        
    Returns:
        Formatted status message
    """
    lines = []
    
    # Progress bar if percentage provided
    if progress_percent is not None:
        bar_length = 10
        filled = int(bar_length * progress_percent / 100)
        bar = "▓" * filled + "░" * (bar_length - filled)
        lines.append(f"🔨 `[{bar}]` {progress_percent}%")
    else:
        lines.append("🔨 *In Progress...*")
    
    lines.append("")
    lines.append(escape_markdown(status_text))
    
    if steps:
        lines.append("")
        for i, (step_name, completed) in enumerate(steps):
            prefix = "├─" if i < len(steps) - 1 else "└─"
            icon = "✓" if completed else "○"
            lines.append(f"{prefix} {icon} {escape_markdown(step_name)}")
    
    return "\n".join(lines)


def format_completion_message(
    summary: str,
    files_changed: int | None = None,
    duration: str | None = None,
) -> str:
    """
    Format a task completion message.
    
    Args:
        summary: Completion summary
        files_changed: Optional number of files changed
        duration: Optional duration string
        
    Returns:
        Formatted markdown message
    """
    lines = []
    
    lines.append("✅ *Task Completed*")
    lines.append("")
    lines.append(escape_markdown(summary))
    
    if files_changed is not None or duration:
        lines.append("")
        if files_changed is not None:
            lines.append(f"📁 Files changed: {files_changed}")
        if duration:
            lines.append(f"⏱️ Duration: {duration}")
    
    return "\n".join(lines)


def format_info_message(
    message: str,
    priority: str = "info",
) -> str:
    """
    Format an info message.
    
    Args:
        message: The message content
        priority: Priority level (info, warning, critical)
        
    Returns:
        Formatted message
    """
    icons = {
        "info": "ℹ️",
        "warning": "⚠️",
        "critical": "🚨",
    }
    icon = icons.get(priority, "ℹ️")
    return f"{icon} {escape_markdown(message)}"


def escape_markdown(text: str) -> str:
    """
    Escape special Markdown characters for Telegram.
    
    Args:
        text: Text to escape
        
    Returns:
        Escaped text safe for Markdown parsing
    """
    # Characters that need escaping in Telegram MarkdownV2
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text


def truncate_text(text: str, max_length: int = 4000, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix
