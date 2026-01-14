"""
Main entry point for Antigravity Mobile Command.

This module starts both the Telegram bot and MCP server,
coordinating communication between them.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from telegram.ext import Application

from src.config import Config, get_config, set_config
from src.bot.handlers import (
    setup_handlers,
    send_plan_approval,
    send_change_approval,
    send_error_notification,
    send_or_update_status,
    send_artifact,
    send_completion,
)
from src.bot.message_queue import (
    get_message_queue,
    QueueMessage,
    MessageType,
)
from src.mcp_server.server import TelegramBridgeServer
from src.mcp_server.state import get_state_manager
from src.monitors.artifacts import create_artifact_watcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class AntigravityMobileCommand:
    """
    Main application class that orchestrates all components.
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        set_config(self.config)
        
        self.telegram_app: Optional[Application] = None
        self.mcp_server: Optional[TelegramBridgeServer] = None
        self.artifact_watcher = None
        
        self._running = False
        self._shutdown_event = asyncio.Event()
    
    async def setup(self) -> None:
        """Set up all components."""
        logger.info("Setting up Antigravity Mobile Command...")
        
        # Ensure directories exist
        self.config.ensure_directories()
        
        # Set up Telegram bot
        self.telegram_app = Application.builder().token(self.config.bot_token).build()
        setup_handlers(self.telegram_app)
        
        # Set up MCP server
        self.mcp_server = TelegramBridgeServer(self.config.mcp_server_name)
        
        # Set up message queue processor
        queue = get_message_queue()
        queue.on_telegram_message(self._handle_telegram_message)
        
        # Set up artifact watcher
        self.artifact_watcher = await create_artifact_watcher(
            self.config.artifacts_path,
            self._handle_new_artifact,
        )
        
        logger.info("Setup complete")
    
    async def _handle_telegram_message(self, message: QueueMessage) -> None:
        """Handle messages destined for Telegram."""
        if not self.telegram_app:
            return
        
        chat_id = message.data.get("chat_id")
        if not chat_id:
            # Try to get from authorized IDs
            if self.config.authorized_chat_ids:
                chat_id = self.config.authorized_chat_ids[0]
            else:
                logger.warning("No chat ID available for message")
                return
        
        try:
            if message.type == MessageType.PLAN_APPROVAL_REQUEST:
                await send_plan_approval(
                    self.telegram_app,
                    chat_id,
                    message.content,
                    message.data.get("files_affected"),
                    message.data.get("task_name"),
                    message.approval_id,
                )
            
            elif message.type == MessageType.CHANGE_APPROVAL_REQUEST:
                await send_change_approval(
                    self.telegram_app,
                    chat_id,
                    message.content,
                    message.data.get("diff_preview"),
                    message.approval_id,
                )
            
            elif message.type == MessageType.ERROR:
                await send_error_notification(
                    self.telegram_app,
                    chat_id,
                    message.content,
                    message.data.get("stack_trace"),
                    message.data.get("command"),
                )
            
            elif message.type == MessageType.STATUS_UPDATE:
                await send_or_update_status(
                    self.telegram_app,
                    chat_id,
                    message.content,
                    message.data.get("progress_percent"),
                )
            
            elif message.type == MessageType.ARTIFACT:
                artifact_path = Path(message.data.get("artifact_path", message.content))
                await send_artifact(
                    self.telegram_app,
                    chat_id,
                    artifact_path,
                    message.data.get("caption"),
                )
            
            elif message.type == MessageType.COMPLETION:
                await send_completion(
                    self.telegram_app,
                    chat_id,
                    message.content,
                    message.data.get("files_changed"),
                    message.data.get("duration"),
                )
            
            elif message.type == MessageType.INFO:
                priority = message.data.get("priority", "info")
                icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(priority, "ℹ️")
                await self.telegram_app.bot.send_message(
                    chat_id=chat_id,
                    text=f"{icon} {message.content}",
                )
        
        except Exception as e:
            logger.exception(f"Error handling message for Telegram: {e}")
    
    async def _handle_new_artifact(self, artifact_path: Path) -> None:
        """Handle new artifacts detected by the watcher."""
        logger.info(f"New artifact: {artifact_path}")
        
        queue = get_message_queue()
        chat_id, _ = queue.get_status_message()
        
        if not chat_id and self.config.authorized_chat_ids:
            chat_id = self.config.authorized_chat_ids[0]
        
        if chat_id and self.telegram_app:
            try:
                await send_artifact(
                    self.telegram_app,
                    chat_id,
                    artifact_path,
                    f"📸 {artifact_path.name}",
                )
            except Exception as e:
                logger.error(f"Failed to send artifact: {e}")
    
    async def run_telegram_bot(self) -> None:
        """Run the Telegram bot."""
        if not self.telegram_app:
            raise RuntimeError("Telegram app not initialized")
        
        logger.info("Starting Telegram bot...")
        
        # Initialize and start the bot
        await self.telegram_app.initialize()
        await self.telegram_app.start()
        await self.telegram_app.updater.start_polling(drop_pending_updates=True)
        
        logger.info("Telegram bot started")
        
        # Wait for shutdown
        await self._shutdown_event.wait()
        
        # Stop the bot
        await self.telegram_app.updater.stop()
        await self.telegram_app.stop()
        await self.telegram_app.shutdown()
    
    async def run_mcp_server(self) -> None:
        """Run the MCP server."""
        if not self.mcp_server:
            raise RuntimeError("MCP server not initialized")
        
        logger.info("Starting MCP server...")
        await self.mcp_server.run_stdio()
    
    async def run(self, mode: str = "both") -> None:
        """
        Run the application.
        
        Args:
            mode: "bot" for Telegram only, "mcp" for MCP server only, "both" for both
        """
        await self.setup()
        self._running = True
        
        try:
            if mode == "bot":
                await self.run_telegram_bot()
            elif mode == "mcp":
                await self.run_mcp_server()
            else:
                # Run both in parallel
                await asyncio.gather(
                    self.run_telegram_bot(),
                    self.run_mcp_server(),
                    return_exceptions=True,
                )
        except asyncio.CancelledError:
            logger.info("Application cancelled")
        finally:
            await self.shutdown()
    
    async def shutdown(self) -> None:
        """Shutdown all components."""
        logger.info("Shutting down...")
        self._running = False
        self._shutdown_event.set()
        
        if self.artifact_watcher:
            await self.artifact_watcher.stop()
        
        # Cancel pending approvals
        state = get_state_manager()
        await state.cancel_all_pending()
        
        logger.info("Shutdown complete")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Antigravity Mobile Command")
    parser.add_argument(
        "--mode",
        choices=["bot", "mcp", "both"],
        default="both",
        help="Run mode: bot only, mcp server only, or both",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Path to .env file",
    )
    args = parser.parse_args()
    
    # Load config
    try:
        if args.env_file:
            config = Config.from_env(args.env_file)
        else:
            config = Config.from_env()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please set up your .env file based on .env.example")
        sys.exit(1)
    
    # Create and run application
    app = AntigravityMobileCommand(config)
    
    # Handle signals
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        asyncio.get_event_loop().call_soon_threadsafe(app._shutdown_event.set)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run
    asyncio.run(app.run(args.mode))


if __name__ == "__main__":
    main()
