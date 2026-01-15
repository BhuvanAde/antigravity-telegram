"""
Task file watcher for triggering actions from markdown updates.
"""

import asyncio
import logging
from pathlib import Path
from typing import Callable, Awaitable, Optional
from datetime import datetime, timedelta

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from src.mcp_server.tools import add_pending_prompt

logger = logging.getLogger(__name__)


class TaskFileHandler(FileSystemEventHandler):
    """
    Handles file system events for the task file.
    """
    
    def __init__(
        self,
        filename: str,
        callback: Callable[[str], Awaitable[None]],
        loop: asyncio.AbstractEventLoop,
        debounce_seconds: float = 1.0,
    ):
        super().__init__()
        self.filename = filename
        self.callback = callback
        self.loop = loop
        self.debounce_seconds = debounce_seconds
        
        self._last_processed: datetime = datetime.min
        self._pending = False
    
    def on_modified(self, event: FileModifiedEvent) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return
            
        path = Path(event.src_path)
        if path.name != self.filename:
            return
            
        # Debounce
        now = datetime.now()
        if now - self._last_processed < timedelta(seconds=self.debounce_seconds):
            return
            
        if self._pending:
            return
            
        self._pending = True
        
        async def run_callback():
            try:
                # Wait for write to stabilize
                await asyncio.sleep(self.debounce_seconds)
                
                if path.exists():
                    content = path.read_text().strip()
                    if content:
                        await self.callback(content)
                        self._last_processed = datetime.now()
            except Exception as e:
                logger.error(f"Error processing task file {path}: {e}")
            finally:
                self._pending = False
        
        asyncio.run_coroutine_threadsafe(run_callback(), self.loop)


class TaskFileWatcher:
    """
    Watches a specific file for task triggers.
    """
    
    def __init__(
        self,
        watch_path: Path,
        filename: str,
    ):
        self.watch_path = watch_path
        self.filename = filename
        
        self._observer: Optional[Observer] = None
        self._running = False
    
    async def start(self) -> None:
        """Start watching for task file updates."""
        if self._running:
            return
        
        # Ensure directory exists
        self.watch_path.mkdir(parents=True, exist_ok=True)
        
        # Create file if it doesn't exist
        file_path = self.watch_path / self.filename
        if not file_path.exists():
            file_path.touch()
            logger.info(f"Created task file: {file_path}")
        
        loop = asyncio.get_running_loop()
        
        handler = TaskFileHandler(
            filename=self.filename,
            callback=self._handle_task_update,
            loop=loop,
        )
        
        self._observer = Observer()
        self._observer.schedule(
            handler,
            str(self.watch_path),
            recursive=False,
        )
        self._observer.start()
        self._running = True
        
        logger.info(f"Task watcher started for {self.filename} in {self.watch_path}")
    
    async def stop(self) -> None:
        """Stop watching."""
        if not self._running or not self._observer:
            return
        
        self._observer.stop()
        self._observer.join(timeout=5.0)
        self._running = False
        
        logger.info("Task watcher stopped")
    
    async def _handle_task_update(self, content: str) -> None:
        """Handle content update from the task file."""
        logger.info(f"Task file updated. Content length: {len(content)}")
        
        # Add as pending prompt
        # Use a "system" chat ID or similar to indicate it's from file? 
        # For now, we'll leave chat_id None which implies it's a general task
        
        full_prompt = f"Task from file update:\n\n{content}\n\nIMPORTANT: When you complete this task, you MUST reply with 'Ready for next task' so the user knows to update the file again."
        
        add_pending_prompt(
            prompt=full_prompt,
            project_path=str(self.watch_path),
        )
        logger.info("Task queued from file")


async def create_task_watcher(
    watch_path: Path,
    filename: str,
) -> TaskFileWatcher:
    """Create and start an task watcher."""
    watcher = TaskFileWatcher(watch_path, filename)
    await watcher.start()
    return watcher
