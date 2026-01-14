"""
Artifact directory watcher for auto-pushing screenshots and recordings.
"""

import asyncio
import logging
from pathlib import Path
from typing import Callable, Awaitable, Optional, Set
from datetime import datetime, timedelta

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

logger = logging.getLogger(__name__)


# Supported artifact extensions
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}
ALL_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


class ArtifactEventHandler(FileSystemEventHandler):
    """
    Handles file system events for new artifacts.
    """
    
    def __init__(
        self,
        callback: Callable[[Path], Awaitable[None]],
        loop: asyncio.AbstractEventLoop,
        debounce_seconds: float = 1.0,
    ):
        super().__init__()
        self.callback = callback
        self.loop = loop
        self.debounce_seconds = debounce_seconds
        
        # Track recently processed files to debounce
        self._processed: dict[str, datetime] = {}
        self._pending: Set[str] = set()
    
    def _should_process(self, path: Path) -> bool:
        """Check if this file should be processed."""
        # Check extension
        if path.suffix.lower() not in ALL_EXTENSIONS:
            return False
        
        # Check if we're in debounce period
        path_str = str(path)
        if path_str in self._processed:
            last_processed = self._processed[path_str]
            if datetime.now() - last_processed < timedelta(seconds=self.debounce_seconds):
                return False
        
        # Check if already pending
        if path_str in self._pending:
            return False
        
        return True
    
    def _schedule_callback(self, path: Path) -> None:
        """Schedule the async callback."""
        path_str = str(path)
        self._pending.add(path_str)
        
        async def run_callback():
            try:
                # Small delay to ensure file is fully written
                await asyncio.sleep(0.5)
                
                # Verify file still exists and has content
                if path.exists() and path.stat().st_size > 0:
                    await self.callback(path)
                    self._processed[path_str] = datetime.now()
            except Exception as e:
                logger.error(f"Error processing artifact {path}: {e}")
            finally:
                self._pending.discard(path_str)
        
        asyncio.run_coroutine_threadsafe(run_callback(), self.loop)
    
    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        if self._should_process(path):
            logger.info(f"New artifact detected: {path.name}")
            self._schedule_callback(path)
    
    def on_modified(self, event: FileModifiedEvent) -> None:
        """Handle file modification events (for overwritten files)."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        # Only process modifications if not recently created
        if path.suffix.lower() in ALL_EXTENSIONS:
            path_str = str(path)
            if path_str not in self._processed:
                self._schedule_callback(path)


class ArtifactWatcher:
    """
    Watches an artifacts directory and triggers callbacks for new files.
    """
    
    def __init__(
        self,
        artifacts_path: Path,
        on_artifact: Callable[[Path], Awaitable[None]],
        recursive: bool = True,
    ):
        self.artifacts_path = artifacts_path
        self.on_artifact = on_artifact
        self.recursive = recursive
        
        self._observer: Optional[Observer] = None
        self._running = False
    
    async def start(self) -> None:
        """Start watching for artifacts."""
        if self._running:
            return
        
        # Ensure directory exists
        self.artifacts_path.mkdir(parents=True, exist_ok=True)
        
        # Get the current event loop
        loop = asyncio.get_running_loop()
        
        # Create event handler
        handler = ArtifactEventHandler(
            callback=self.on_artifact,
            loop=loop,
        )
        
        # Create and start observer
        self._observer = Observer()
        self._observer.schedule(
            handler,
            str(self.artifacts_path),
            recursive=self.recursive,
        )
        self._observer.start()
        self._running = True
        
        logger.info(f"Artifact watcher started: {self.artifacts_path}")
    
    async def stop(self) -> None:
        """Stop watching for artifacts."""
        if not self._running or not self._observer:
            return
        
        self._observer.stop()
        self._observer.join(timeout=5.0)
        self._running = False
        
        logger.info("Artifact watcher stopped")
    
    @property
    def is_running(self) -> bool:
        """Check if the watcher is running."""
        return self._running


async def create_artifact_watcher(
    artifacts_path: Path,
    on_artifact: Callable[[Path], Awaitable[None]],
) -> ArtifactWatcher:
    """
    Create and start an artifact watcher.
    
    Args:
        artifacts_path: Path to watch for artifacts
        on_artifact: Callback for new artifacts
        
    Returns:
        Running ArtifactWatcher instance
    """
    watcher = ArtifactWatcher(artifacts_path, on_artifact)
    await watcher.start()
    return watcher
