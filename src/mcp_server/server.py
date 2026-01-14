"""
MCP Server implementation for Antigravity Mobile Command.

This server exposes tools that allow Antigravity to communicate
with users via Telegram.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
    CallToolResult,
)

from src.mcp_server.tools import TOOLS, handle_tool_call
from src.mcp_server.state import get_state_manager
from src.bot.message_queue import get_message_queue, QueueMessage, MessageType

logger = logging.getLogger(__name__)


class TelegramBridgeServer:
    """
    MCP Server that bridges Antigravity and Telegram.
    
    This server exposes tools for:
    - Sending messages to Telegram
    - Requesting plan/change approvals
    - Sending artifacts (screenshots, recordings)
    - Updating status tickers
    - Reporting errors
    """
    
    def __init__(self, name: str = "telegram-bridge"):
        self.name = name
        self.server = Server(name)
        self._chat_id: Optional[int] = None
        self._setup_handlers()
    
    def set_chat_id(self, chat_id: int) -> None:
        """Set the current chat ID for tool calls."""
        self._chat_id = chat_id
    
    def _setup_handlers(self) -> None:
        """Set up MCP server handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return TOOLS
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
            """Handle tool calls."""
            logger.info(f"Tool call: {name} with args: {arguments}")
            
            # Get chat ID from arguments or use default
            chat_id = arguments.pop("chat_id", None) or self._chat_id
            if not chat_id:
                # Try to get from message queue
                queue = get_message_queue()
                chat_id_from_queue, _ = queue.get_status_message()
                chat_id = chat_id_from_queue
            
            if not chat_id:
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text="Error: No chat ID available. User must initiate conversation first.",
                    )],
                    isError=True,
                )
            
            try:
                result = await handle_tool_call(name, arguments, chat_id)
                return CallToolResult(
                    content=[TextContent(type="text", text=result)],
                    isError=False,
                )
            except Exception as e:
                logger.exception(f"Error in tool {name}")
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Error: {str(e)}")],
                    isError=True,
                )
    
    async def run_stdio(self) -> None:
        """Run the server using stdio transport."""
        logger.info(f"Starting MCP server: {self.name}")
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


async def run_mcp_server(name: str = "telegram-bridge") -> None:
    """Run the MCP server."""
    server = TelegramBridgeServer(name)
    await server.run_stdio()


# For direct execution
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_mcp_server())
