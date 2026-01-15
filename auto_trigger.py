#!/usr/bin/env python3
"""
Fully Automated Antigravity IDE Trigger

This daemon watches telegram_tasks.md and automatically triggers
Antigravity IDE to start implementing when the file is updated.

Usage:
    python3 auto_trigger.py

Requirements:
    - macOS (uses AppleScript for automation)
    - VS Code with Antigravity extension open
    - Accessibility permissions for Terminal/Python
"""

import time
import subprocess
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configuration
WATCH_FILE = Path("/Users/bhuvan_ade/telegram_tasks.md")
DEBOUNCE_SECONDS = 2.0
ANTIGRAVITY_APP = "Antigravity"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_file_hash(filepath: Path) -> str:
    """Get hash of file contents to detect real changes."""
    if not filepath.exists():
        return ""
    return hashlib.md5(filepath.read_bytes()).hexdigest()


def trigger_antigravity_chat(task_content: str) -> bool:
    """
    Trigger Antigravity IDE using AppleScript.
    
    This script:
    1. Brings Antigravity to focus
    2. Opens a new chat (Cmd+N or equivalent)
    3. Types the task content
    4. Sends the message
    """
    
    # Escape content for AppleScript
    escaped_content = task_content.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    
    # AppleScript to trigger Antigravity
    applescript = f'''
    tell application "{ANTIGRAVITY_APP}"
        activate
        delay 0.5
    end tell
    
    tell application "System Events"
        tell process "{ANTIGRAVITY_APP}"
            -- Open new chat (try Cmd+N first)
            keystroke "n" using command down
            delay 1.0
            
            -- Type the task (use clipboard for reliability)
            set the clipboard to "{escaped_content}"
            keystroke "v" using command down
            delay 0.3
            
            -- Send the message (Enter)
            keystroke return
        end tell
    end tell
    '''
    
    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info("✅ Successfully triggered Antigravity IDE")
            return True
        else:
            logger.error(f"❌ AppleScript failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("❌ AppleScript timed out")
        return False
    except Exception as e:
        logger.error(f"❌ Error triggering IDE: {e}")
        return False


class TaskFileHandler(FileSystemEventHandler):
    """Watches for changes to the task file."""
    
    def __init__(self, filepath: Path):
        super().__init__()
        self.filepath = filepath
        self.last_hash = get_file_hash(filepath)
        self.last_trigger = datetime.min
        self.pending_trigger = False
    
    def on_modified(self, event):
        if event.is_directory:
            return
            
        if not event.src_path.endswith(self.filepath.name):
            return
        
        # Debounce
        now = datetime.now()
        if (now - self.last_trigger).total_seconds() < DEBOUNCE_SECONDS:
            return
        
        # Check if content actually changed
        new_hash = get_file_hash(self.filepath)
        if new_hash == self.last_hash:
            return
        
        self.last_hash = new_hash
        self.last_trigger = now
        
        # Read the content
        content = self.filepath.read_text().strip()
        if not content:
            logger.info("File is empty, skipping trigger")
            return
        
        logger.info(f"📝 Task file updated! Content length: {len(content)}")
        
        # Add the workflow instruction
        full_prompt = f"""Execute this task from the file update:

{content}

IMPORTANT: When you complete this task, reply with 'Ready for next task' so the user knows to update the file again."""
        
        # Trigger the IDE
        trigger_antigravity_chat(full_prompt)


def main():
    """Main entry point."""
    logger.info("🚀 Starting Antigravity Auto-Trigger Daemon")
    logger.info(f"📁 Watching: {WATCH_FILE}")
    
    # Ensure the file exists
    if not WATCH_FILE.exists():
        logger.warning(f"Creating task file: {WATCH_FILE}")
        WATCH_FILE.touch()
    
    # Set up the watcher
    handler = TaskFileHandler(WATCH_FILE)
    observer = Observer()
    observer.schedule(handler, str(WATCH_FILE.parent), recursive=False)
    observer.start()
    
    logger.info("✅ Daemon started. Waiting for file updates...")
    logger.info("💡 Edit telegram_tasks.md to trigger Antigravity automatically")
    logger.info("   Press Ctrl+C to stop")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Stopping daemon...")
        observer.stop()
    
    observer.join()
    logger.info("👋 Daemon stopped")


if __name__ == "__main__":
    main()
