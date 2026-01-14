"""
File-based task injection for seamless Telegram → Antigravity flow.
"""

import os
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional


# Default task file location
DEFAULT_TASK_FILE = Path.home() / "telegram_tasks.md"


def get_task_file_path() -> Path:
    """Get the path to the task file."""
    env_path = os.getenv("TELEGRAM_TASK_FILE")
    if env_path:
        return Path(env_path).expanduser()
    return DEFAULT_TASK_FILE


def write_task(
    prompt: str,
    project_path: Optional[str] = None,
    chat_id: Optional[int] = None,
    append: bool = False,
    auto_open: bool = True,
) -> Path:
    """
    Write a task to the task file for Antigravity to pick up.
    
    Args:
        prompt: The task prompt
        project_path: Optional project path context
        chat_id: Telegram chat ID for responses
        append: If True, append to existing tasks; otherwise overwrite
        auto_open: If True, open the file after writing
        
    Returns:
        Path to the task file
    """
    task_file = get_task_file_path()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Format the task entry
    task_content = f"""
---

## 📱 Telegram Task ({timestamp})

**Prompt:** {prompt}

"""
    
    if project_path:
        task_content += f"**Project:** `{project_path}`\n\n"
    
    if chat_id:
        task_content += f"**Reply to Chat:** `{chat_id}`\n\n"
    
    task_content += """**Instructions for Antigravity:**
1. Execute this task in the specified project
2. Use `send_telegram_message` to update progress
3. Take screenshots of UI changes and use `send_artifact` to share
4. Use `request_plan_approval` before major changes
5. Use `notify_error` if something fails

---
"""
    
    # Write or append
    mode = "a" if append else "w"
    
    # If overwriting, add a header
    if not append:
        header = """# 📱 Telegram Mobile Command Tasks

This file contains tasks sent from Telegram. Antigravity should process these automatically.

**To process:** Read the latest task below and execute it.

"""
        task_content = header + task_content
    
    with open(task_file, mode) as f:
        f.write(task_content)
    
    # Auto-open the file
    if auto_open:
        open_task_file(task_file)
    
    return task_file


def open_task_file(task_file: Optional[Path] = None) -> bool:
    """
    Open the task file in the default application.
    
    Args:
        task_file: Path to open, defaults to the standard task file
        
    Returns:
        True if opened successfully
    """
    if task_file is None:
        task_file = get_task_file_path()
    
    if not task_file.exists():
        return False
    
    try:
        # macOS: open with default app
        subprocess.run(["open", str(task_file)], check=True)
        return True
    except Exception:
        return False


def copy_to_clipboard(text: str) -> bool:
    """
    Copy text to system clipboard (macOS).
    
    Args:
        text: Text to copy
        
    Returns:
        True if copied successfully
    """
    try:
        process = subprocess.Popen(
            ['pbcopy'],
            stdin=subprocess.PIPE,
            text=True
        )
        process.communicate(input=text)
        return process.returncode == 0
    except Exception:
        return False


def clear_tasks() -> None:
    """Clear all pending tasks."""
    task_file = get_task_file_path()
    if task_file.exists():
        task_file.unlink()


def get_latest_task() -> Optional[str]:
    """Get the content of the task file."""
    task_file = get_task_file_path()
    if task_file.exists():
        return task_file.read_text()
    return None
