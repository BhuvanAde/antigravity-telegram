"""
MCP Tools for Antigravity to interact with the Telegram bridge.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from mcp.types import Tool, TextContent

from src.config import get_config
from src.bot.message_queue import get_message_queue, QueueMessage, MessageType, Priority
from src.mcp_server.state import get_state_manager

logger = logging.getLogger(__name__)


# Tool definitions for MCP registration
TOOLS: list[Tool] = [
    Tool(
        name="send_telegram_message",
        description=(
            "Send a message to the user via Telegram. Use for status updates, "
            "informational messages, or any communication that doesn't require approval."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to send to the user",
                },
                "priority": {
                    "type": "string",
                    "enum": ["info", "warning", "critical"],
                    "description": "Message priority level",
                    "default": "info",
                },
            },
            "required": ["message"],
        },
    ),
    Tool(
        name="request_plan_approval",
        description=(
            "Request approval for an implementation plan before making changes. "
            "Use this before modifying more than 3 files or making significant changes. "
            "The user will see the plan summary and can approve or reject."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "plan_summary": {
                    "type": "string",
                    "description": "Summary of the implementation plan",
                },
                "files_affected": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file paths that will be modified",
                },
                "task_name": {
                    "type": "string",
                    "description": "Optional name/title for the task",
                },
            },
            "required": ["plan_summary"],
        },
    ),
    Tool(
        name="request_change_approval",
        description=(
            "Request approval for specific code changes. "
            "Use for reviewing important modifications before they are committed."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "change_summary": {
                    "type": "string",
                    "description": "Summary of the changes made",
                },
                "diff_preview": {
                    "type": "string",
                    "description": "Optional diff preview of the changes",
                },
            },
            "required": ["change_summary"],
        },
    ),
    Tool(
        name="send_artifact",
        description=(
            "Send an artifact (screenshot, recording, or file) to the user via Telegram. "
            "Use after capturing UI screenshots or generating visual content."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "artifact_path": {
                    "type": "string",
                    "description": "Absolute path to the artifact file",
                },
                "caption": {
                    "type": "string",
                    "description": "Optional caption for the artifact",
                },
            },
            "required": ["artifact_path"],
        },
    ),
    Tool(
        name="update_status",
        description=(
            "Update the status ticker message. This edits the existing status message "
            "instead of sending a new one, reducing message spam."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "status_text": {
                    "type": "string",
                    "description": "Current status description",
                },
                "progress_percent": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Optional progress percentage (0-100)",
                },
            },
            "required": ["status_text"],
        },
    ),
    Tool(
        name="notify_error",
        description=(
            "Send a critical error notification to the user. "
            "Use when terminal commands fail or errors occur that need user attention."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "error_message": {
                    "type": "string",
                    "description": "The error message",
                },
                "stack_trace": {
                    "type": "string",
                    "description": "Optional stack trace or detailed error output",
                },
                "command": {
                    "type": "string",
                    "description": "Optional command that caused the error",
                },
            },
            "required": ["error_message"],
        },
    ),
    Tool(
        name="await_user_response",
        description=(
            "Wait for the user to respond with a message. "
            "Use when you need specific input or instructions from the user."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Prompt to show the user",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 300)",
                    "default": 300,
                },
            },
            "required": ["prompt"],
        },
    ),
    Tool(
        name="get_pending_prompts",
        description=(
            "Check for pending prompts from the Telegram user. "
            "Call this when the user asks you to check telegram or at the start of a session. "
            "Returns any queued prompts that the user sent via the Telegram bot."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "clear_after_read": {
                    "type": "boolean",
                    "description": "Whether to clear prompts after reading (default: true)",
                    "default": True,
                },
            },
        },
    ),
]


async def handle_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    chat_id: int,
) -> str:
    """
    Handle an MCP tool call.
    
    Args:
        tool_name: Name of the tool to call
        arguments: Tool arguments
        chat_id: Telegram chat ID to send messages to
        
    Returns:
        Result string from the tool execution
    """
    queue = get_message_queue()
    state = get_state_manager()
    
    try:
        if tool_name == "send_telegram_message":
            return await _handle_send_message(arguments, chat_id, queue)
        
        elif tool_name == "request_plan_approval":
            return await _handle_plan_approval(arguments, chat_id, queue, state)
        
        elif tool_name == "request_change_approval":
            return await _handle_change_approval(arguments, chat_id, queue, state)
        
        elif tool_name == "send_artifact":
            return await _handle_send_artifact(arguments, chat_id, queue)
        
        elif tool_name == "update_status":
            return await _handle_update_status(arguments, chat_id, queue, state)
        
        elif tool_name == "notify_error":
            return await _handle_notify_error(arguments, chat_id, queue)
        
        elif tool_name == "await_user_response":
            return await _handle_await_response(arguments, chat_id, queue)
        
        elif tool_name == "get_pending_prompts":
            return await _handle_get_pending_prompts(arguments)
        
        else:
            return f"Unknown tool: {tool_name}"
    
    except Exception as e:
        logger.exception(f"Error handling tool {tool_name}")
        return f"Error: {str(e)}"


async def _handle_send_message(
    arguments: dict[str, Any],
    chat_id: int,
    queue,
) -> str:
    """Handle send_telegram_message tool."""
    message_text = arguments.get("message", "")
    priority_str = arguments.get("priority", "info")
    
    priority_map = {
        "info": Priority.NORMAL,
        "warning": Priority.HIGH,
        "critical": Priority.CRITICAL,
    }
    priority = priority_map.get(priority_str, Priority.NORMAL)
    
    msg = QueueMessage(
        type=MessageType.INFO,
        priority=priority,
        content=message_text,
        data={"chat_id": chat_id, "priority": priority_str},
    )
    await queue.send_to_telegram(msg)
    
    return "Message sent successfully"


async def _handle_plan_approval(
    arguments: dict[str, Any],
    chat_id: int,
    queue,
    state,
) -> str:
    """Handle request_plan_approval tool."""
    plan_summary = arguments.get("plan_summary", "")
    files_affected = arguments.get("files_affected", [])
    task_name = arguments.get("task_name")
    
    # Create approval request
    request = await state.create_approval(
        request_type="plan",
        content=plan_summary,
        data={
            "files_affected": files_affected,
            "task_name": task_name,
        },
    )
    
    # Send to Telegram
    msg = QueueMessage(
        type=MessageType.PLAN_APPROVAL_REQUEST,
        priority=Priority.HIGH,
        content=plan_summary,
        data={
            "chat_id": chat_id,
            "files_affected": files_affected,
            "task_name": task_name,
            "approval_id": request.id,
        },
        approval_id=request.id,
        requires_response=True,
    )
    await queue.send_to_telegram(msg)
    
    # Wait for approval
    approved, user_message = await state.wait_for_approval(request.id, timeout=300.0)
    
    if approved:
        return "Plan approved by user. Proceeding with implementation."
    else:
        return f"Plan rejected by user. Reason: {user_message or 'No reason provided'}. Do not proceed with the changes."


async def _handle_change_approval(
    arguments: dict[str, Any],
    chat_id: int,
    queue,
    state,
) -> str:
    """Handle request_change_approval tool."""
    change_summary = arguments.get("change_summary", "")
    diff_preview = arguments.get("diff_preview")
    
    # Create approval request
    request = await state.create_approval(
        request_type="change",
        content=change_summary,
        data={"diff_preview": diff_preview},
    )
    
    # Send to Telegram
    msg = QueueMessage(
        type=MessageType.CHANGE_APPROVAL_REQUEST,
        priority=Priority.HIGH,
        content=change_summary,
        data={
            "chat_id": chat_id,
            "diff_preview": diff_preview,
            "approval_id": request.id,
        },
        approval_id=request.id,
        requires_response=True,
    )
    await queue.send_to_telegram(msg)
    
    # Wait for approval
    approved, user_message = await state.wait_for_approval(request.id, timeout=300.0)
    
    if approved:
        return "Changes approved by user."
    else:
        return f"Changes rejected by user. Feedback: {user_message or 'No feedback provided'}."


async def _handle_send_artifact(
    arguments: dict[str, Any],
    chat_id: int,
    queue,
) -> str:
    """Handle send_artifact tool."""
    artifact_path = arguments.get("artifact_path", "")
    caption = arguments.get("caption")
    
    path = Path(artifact_path).expanduser()
    if not path.exists():
        return f"Error: Artifact not found at {artifact_path}"
    
    msg = QueueMessage(
        type=MessageType.ARTIFACT,
        priority=Priority.NORMAL,
        content=str(path),
        data={
            "chat_id": chat_id,
            "artifact_path": str(path),
            "caption": caption,
        },
    )
    await queue.send_to_telegram(msg)
    
    return f"Artifact sent: {path.name}"


async def _handle_update_status(
    arguments: dict[str, Any],
    chat_id: int,
    queue,
    state,
) -> str:
    """Handle update_status tool."""
    status_text = arguments.get("status_text", "")
    progress_percent = arguments.get("progress_percent")
    
    state.set_task_status(status_text)
    
    msg = QueueMessage(
        type=MessageType.STATUS_UPDATE,
        priority=Priority.LOW,
        content=status_text,
        data={
            "chat_id": chat_id,
            "progress_percent": progress_percent,
        },
    )
    await queue.send_to_telegram(msg)
    
    return "Status updated"


async def _handle_notify_error(
    arguments: dict[str, Any],
    chat_id: int,
    queue,
) -> str:
    """Handle notify_error tool."""
    error_message = arguments.get("error_message", "")
    stack_trace = arguments.get("stack_trace")
    command = arguments.get("command")
    
    msg = QueueMessage(
        type=MessageType.ERROR,
        priority=Priority.CRITICAL,
        content=error_message,
        data={
            "chat_id": chat_id,
            "stack_trace": stack_trace,
            "command": command,
        },
    )
    await queue.send_to_telegram(msg)
    
    return "Error notification sent"


async def _handle_await_response(
    arguments: dict[str, Any],
    chat_id: int,
    queue,
) -> str:
    """Handle await_user_response tool."""
    prompt = arguments.get("prompt", "")
    timeout_seconds = arguments.get("timeout_seconds", 300)
    
    # Send prompt
    msg = QueueMessage(
        type=MessageType.INFO,
        priority=Priority.HIGH,
        content=prompt,
        data={"chat_id": chat_id, "awaiting_response": True},
    )
    await queue.send_to_telegram(msg)
    
    # Wait for user response
    try:
        response_msg = await queue.receive_from_telegram(timeout=float(timeout_seconds))
        if response_msg:
            return f"User response: {response_msg.content}"
        return "No response received (timed out)"
    except asyncio.TimeoutError:
        return "Request timed out waiting for user response"


# ===== Pending Prompts Storage =====

_pending_prompts: list[dict[str, Any]] = []


def add_pending_prompt(prompt: str, project_path: Optional[str] = None, chat_id: Optional[int] = None) -> None:
    """Add a prompt to the pending queue."""
    from datetime import datetime
    _pending_prompts.append({
        "prompt": prompt,
        "project_path": project_path,
        "chat_id": chat_id,
        "timestamp": datetime.now().isoformat(),
    })


def get_pending_prompts_list() -> list[dict[str, Any]]:
    """Get all pending prompts without clearing."""
    return list(_pending_prompts)


def clear_pending_prompts() -> None:
    """Clear all pending prompts."""
    _pending_prompts.clear()


async def _handle_get_pending_prompts(arguments: dict[str, Any]) -> str:
    """Handle get_pending_prompts tool."""
    clear_after = arguments.get("clear_after_read", True)
    
    if not _pending_prompts:
        return "No pending prompts from Telegram."
    
    # Format prompts for output
    result_lines = [f"Found {len(_pending_prompts)} pending prompt(s) from Telegram:\n"]
    
    for i, p in enumerate(_pending_prompts, 1):
        project_info = f" (Project: {p['project_path']})" if p.get('project_path') else ""
        result_lines.append(f"{i}. {p['prompt']}{project_info}")
        result_lines.append(f"   Received: {p['timestamp']}")
        result_lines.append("")
    
    if clear_after:
        clear_pending_prompts()
        result_lines.append("(Prompts cleared from queue)")
    
    return "\n".join(result_lines)

