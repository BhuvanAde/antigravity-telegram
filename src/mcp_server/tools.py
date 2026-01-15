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
    Tool(
        name="wait_for_new_prompt",
        description=(
            "Wait efficiently for a new prompt to arrive from Telegram. "
            "Blocks until a prompt is found or timeout is reached. "
            "Use this in a loop to monitor for incoming tasks."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Maximum seconds to wait (default: 60)",
                    "default": 60,
                },
            },
        },
    ),
    # ===== IDE Capability Tools =====
    Tool(
        name="read_project_file",
        description=(
            "Read the contents of a file from the current project. "
            "Use to report file contents back to Telegram or verify changes."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path to the file within the project",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Optional start line (1-indexed)",
                },
                "end_line": {
                    "type": "integer",
                    "description": "Optional end line (1-indexed)",
                },
            },
            "required": ["file_path"],
        },
    ),
    Tool(
        name="write_project_file",
        description=(
            "Write content to a file in the project. "
            "Creates parent directories if needed. Use for code modifications."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path to the file within the project",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
                "create_dirs": {
                    "type": "boolean",
                    "description": "Create parent directories if they don't exist (default: true)",
                    "default": True,
                },
            },
            "required": ["file_path", "content"],
        },
    ),
    Tool(
        name="list_project_files",
        description=(
            "List files and directories in the project. "
            "Use to explore project structure or find files matching a pattern."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory path relative to project root (default: '.')",
                    "default": ".",
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (default: '*')",
                    "default": "*",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Search recursively (default: false)",
                    "default": False,
                },
            },
        },
    ),
    Tool(
        name="search_project_code",
        description=(
            "Search for code patterns in the project using grep. "
            "Returns matching files with line numbers and content snippets."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search string or pattern to find",
                },
                "file_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "File extensions to search (e.g., ['.py', '.js'])",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 20)",
                    "default": 20,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="run_terminal_command",
        description=(
            "Run a terminal command in the project directory. "
            "Returns stdout, stderr, and return code. Use for builds, tests, etc."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 30)",
                    "default": 30,
                },
            },
            "required": ["command"],
        },
    ),
    Tool(
        name="get_project_context",
        description=(
            "Get information about the current project context. "
            "Returns project path, file counts by type, git status, and settings."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="set_project_context",
        description=(
            "Set the current project path for IDE operations. "
            "All file operations will be relative to this path."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Absolute path to the project directory",
                },
            },
            "required": ["project_path"],
        },
    ),
    Tool(
        name="send_code_update",
        description=(
            "Send a code update notification to Telegram. "
            "Use after making significant code changes to inform the user."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the modified file",
                },
                "change_type": {
                    "type": "string",
                    "enum": ["created", "modified", "deleted"],
                    "description": "Type of change made",
                },
                "summary": {
                    "type": "string",
                    "description": "Brief summary of the changes",
                },
                "diff_preview": {
                    "type": "string",
                    "description": "Optional diff or code snippet showing the change",
                },
            },
            "required": ["file_path", "change_type", "summary"],
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
        
        elif tool_name == "wait_for_new_prompt":
            return await _handle_wait_for_new_prompt(arguments)
        
        # IDE Capability Tools
        elif tool_name == "read_project_file":
            return await _handle_read_project_file(arguments)
        
        elif tool_name == "write_project_file":
            return await _handle_write_project_file(arguments, chat_id, queue)
        
        elif tool_name == "list_project_files":
            return await _handle_list_project_files(arguments)
        
        elif tool_name == "search_project_code":
            return await _handle_search_project_code(arguments)
        
        elif tool_name == "run_terminal_command":
            return await _handle_run_terminal_command(arguments, chat_id, queue)
        
        elif tool_name == "get_project_context":
            return await _handle_get_project_context(arguments)
        
        elif tool_name == "set_project_context":
            return await _handle_set_project_context(arguments, chat_id, queue)
        
        elif tool_name == "send_code_update":
            return await _handle_send_code_update(arguments, chat_id, queue)
        
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
    
    # Save to file queue for cross-process communication
    params = {
        "content": message_text,
        "chat_id": chat_id,
        "priority": priority_str,
        "timestamp": datetime.now().isoformat(),
        "type": "info"
    }
    _save_reply(params)
    
    # Also attempt queue (for local mode) if available
    try:
        await queue.send_to_telegram(msg)
    except Exception:
        pass
    
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

# ===== Pending Prompts Storage =====

import json
from datetime import datetime

PROMPTS_FILE = Path.home() / ".antigravity_prompts.json"
REPLIES_FILE = Path.home() / ".antigravity_replies.json"


def _load_prompts() -> list[dict[str, Any]]:
    """Load prompts from the persistence file."""
    if not PROMPTS_FILE.exists():
        return []
    try:
        content = PROMPTS_FILE.read_text()
        if not content.strip():
            return []
        return json.loads(content)
    except Exception as e:
        logger.error(f"Failed to load prompts: {e}")
        return []


def _save_prompts(prompts: list[dict[str, Any]]) -> None:
    """Save prompts to the persistence file."""
    try:
        PROMPTS_FILE.write_text(json.dumps(prompts, indent=2))
    except Exception as e:
        logger.error(f"Failed to save prompts: {e}")


def _save_reply(reply: dict[str, Any]) -> None:
    """Save a reply to the persistence file for the bot to pick up."""
    replies = []
    if REPLIES_FILE.exists():
        try:
            content = REPLIES_FILE.read_text()
            if content.strip():
                replies = json.loads(content)
        except Exception:
            pass
    
    replies.append(reply)
    
    try:
        REPLIES_FILE.write_text(json.dumps(replies, indent=2))
    except Exception as e:
        logger.error(f"Failed to save reply: {e}")


def add_pending_prompt(prompt: str, project_path: Optional[str] = None, chat_id: Optional[int] = None) -> None:
    """Add a prompt to the pending queue."""
    prompts = _load_prompts()
    prompts.append({
        "prompt": prompt,
        "project_path": project_path,
        "chat_id": chat_id,
        "timestamp": datetime.now().isoformat(),
    })
    _save_prompts(prompts)


def get_pending_prompts_list() -> list[dict[str, Any]]:
    """Get all pending prompts without clearing."""
    return _load_prompts()


def clear_pending_prompts() -> None:
    """Clear all pending prompts."""
    _save_prompts([])


async def _handle_get_pending_prompts(arguments: dict[str, Any]) -> str:
    """Handle get_pending_prompts tool."""
    clear_after = arguments.get("clear_after_read", True)
    
    prompts = get_pending_prompts_list()
    
    if not prompts:
        return "No pending prompts from Telegram."
    
    # Format prompts for output
    result_lines = [f"Found {len(prompts)} pending prompt(s) from Telegram:\n"]
    
    for i, p in enumerate(prompts, 1):
        project_info = f" (Project: {p.get('project_path')})" if p.get('project_path') else ""
        timestamp = p.get('timestamp', 'Unknown time')
        result_lines.append(f"{i}. {p['prompt']}{project_info}")
        result_lines.append(f"   Received: {timestamp}")
        result_lines.append("")
    
    if clear_after:
        clear_pending_prompts()
        result_lines.append("(Prompts cleared from queue)")
    
    return "\n".join(result_lines)


async def _handle_wait_for_new_prompt(arguments: dict[str, Any]) -> str:
    """Handle wait_for_new_prompt tool using file events."""
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    
    timeout = arguments.get("timeout_seconds", 60)
    
    # Check immediately first
    if get_pending_prompts_list():
        prompts = get_pending_prompts_list()
        return f"New prompts detected! (Count: {len(prompts)}). Call get_pending_prompts to read them."

    # Setup async event
    event = asyncio.Event()
    
    class PromptHandler(FileSystemEventHandler):
        def on_modified(self, event_data):
            if str(event_data.src_path) == str(PROMPTS_FILE):
                # Use loop.call_soon_threadsafe to set event from thread
                asyncio.get_event_loop().call_soon_threadsafe(event.set)
        
        def on_created(self, event_data):
            if str(event_data.src_path) == str(PROMPTS_FILE):
                asyncio.get_event_loop().call_soon_threadsafe(event.set)

    observer = Observer()
    handler = PromptHandler()
    
    # Watch the directory because watching a single file that might be re-created is flaky
    watch_dir = PROMPTS_FILE.parent
    observer.schedule(handler, str(watch_dir), recursive=False)
    observer.start()
    
    try:
        # Wait for file event or timeout
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            
            # Allow file write to complete
            await asyncio.sleep(0.1)
            
            prompts = get_pending_prompts_list()
            if prompts:
                return f"New prompts detected! (Count: {len(prompts)}). Call get_pending_prompts to read them."
            else:
                return "File changed, but no prompts found (potentially cleared)."
                
        except asyncio.TimeoutError:
            return "No new prompts received within timeout."
            
    finally:
        observer.stop()
        observer.join()


# ===== IDE Capability Tool Handlers =====

async def _handle_read_project_file(arguments: dict[str, Any]) -> str:
    """Handle read_project_file tool."""
    from src.utils.project_manager import read_project_file
    
    file_path = arguments.get("file_path", "")
    start_line = arguments.get("start_line")
    end_line = arguments.get("end_line")
    
    try:
        content = read_project_file(file_path)
        
        # Apply line filtering if specified
        if start_line or end_line:
            lines = content.split('\n')
            start = (start_line or 1) - 1  # Convert to 0-indexed
            end = end_line or len(lines)
            content = '\n'.join(lines[start:end])
        
        # Truncate if too long
        if len(content) > 5000:
            content = content[:5000] + f"\n\n... (truncated, {len(content)} total characters)"
        
        return content
        
    except FileNotFoundError as e:
        return f"Error: {str(e)}"
    except ValueError as e:
        return f"Error: {str(e)}"


async def _handle_write_project_file(
    arguments: dict[str, Any],
    chat_id: int,
    queue,
) -> str:
    """Handle write_project_file tool."""
    from src.utils.project_manager import write_project_file, get_project_manager
    
    file_path = arguments.get("file_path", "")
    content = arguments.get("content", "")
    
    try:
        result = write_project_file(file_path, content)
        
        # Notify Telegram about the file write
        pm = get_project_manager()
        project = pm.get_current_project()
        project_name = project.name if project else "Unknown"
        
        msg = QueueMessage(
            type=MessageType.INFO,
            priority=Priority.NORMAL,
            content=f"📝 File written: `{file_path}`\n📁 Project: {project_name}\n📊 Size: {len(content)} bytes",
            data={"chat_id": chat_id},
        )
        await queue.send_to_telegram(msg)
        
        return result
        
    except Exception as e:
        return f"Error writing file: {str(e)}"


async def _handle_list_project_files(arguments: dict[str, Any]) -> str:
    """Handle list_project_files tool."""
    from src.utils.project_manager import list_project_files
    import json
    
    directory = arguments.get("directory", ".")
    pattern = arguments.get("pattern", "*")
    recursive = arguments.get("recursive", False)
    
    try:
        files = list_project_files(directory, pattern, recursive)
        
        if not files:
            return f"No files found in '{directory}' matching '{pattern}'"
        
        # Format output
        lines = [f"Found {len(files)} items in '{directory}':\n"]
        for f in files:
            icon = "📁" if f["is_dir"] else "📄"
            size = f" ({f['size']} bytes)" if f.get("size") else ""
            lines.append(f"{icon} {f['path']}{size}")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error listing files: {str(e)}"


async def _handle_search_project_code(arguments: dict[str, Any]) -> str:
    """Handle search_project_code tool."""
    from src.utils.project_manager import search_project_code
    
    query = arguments.get("query", "")
    file_types = arguments.get("file_types")
    max_results = arguments.get("max_results", 20)
    
    try:
        matches = search_project_code(query, file_types, max_results=max_results)
        
        if not matches:
            return f"No matches found for '{query}'"
        
        if "error" in matches[0]:
            return f"Search error: {matches[0]['error']}"
        
        # Format output
        lines = [f"Found {len(matches)} match(es) for '{query}':\n"]
        for m in matches:
            lines.append(f"📄 {m['file']}:{m['line']}")
            lines.append(f"   {m['content']}")
            lines.append("")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error searching: {str(e)}"


async def _handle_run_terminal_command(
    arguments: dict[str, Any],
    chat_id: int,
    queue,
) -> str:
    """Handle run_terminal_command tool."""
    from src.utils.project_manager import run_terminal_command, get_project_manager
    
    command = arguments.get("command", "")
    timeout = arguments.get("timeout", 30)
    
    # Notify that command is starting
    pm = get_project_manager()
    project_path = pm.get_current_path() or "~"
    
    msg = QueueMessage(
        type=MessageType.STATUS_UPDATE,
        priority=Priority.NORMAL,
        content=f"⏳ Running: `{command[:50]}{'...' if len(command) > 50 else ''}`",
        data={"chat_id": chat_id},
    )
    await queue.send_to_telegram(msg)
    
    try:
        result = run_terminal_command(command, timeout=timeout)
        
        # Format output
        output_lines = []
        if result["success"]:
            output_lines.append(f"✅ Command succeeded (exit code: {result['return_code']})")
        else:
            output_lines.append(f"❌ Command failed (exit code: {result['return_code']})")
        
        if result["stdout"]:
            output_lines.append(f"\n📤 stdout:\n{result['stdout']}")
        
        if result["stderr"]:
            output_lines.append(f"\n📤 stderr:\n{result['stderr']}")
        
        return "\n".join(output_lines)
        
    except Exception as e:
        return f"Error running command: {str(e)}"


async def _handle_get_project_context(arguments: dict[str, Any]) -> str:
    """Handle get_project_context tool."""
    from src.utils.project_manager import get_project_context
    import json
    
    try:
        context = get_project_context()
        
        if "error" in context:
            return f"Error: {context['error']}"
        
        # Format output
        lines = [f"📁 Project: {context['name']}"]
        lines.append(f"📍 Path: {context['path']}")
        
        if context.get("git"):
            lines.append(f"🔀 Branch: {context['git']['branch']}")
            lines.append(f"📝 Uncommitted changes: {context['git']['changes']}")
        
        if context.get("file_counts"):
            lines.append("\n📊 File types:")
            for ext, count in list(context["file_counts"].items())[:5]:
                lines.append(f"   {ext}: {count}")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error getting project context: {str(e)}"


async def _handle_set_project_context(
    arguments: dict[str, Any],
    chat_id: int,
    queue,
) -> str:
    """Handle set_project_context tool."""
    from src.utils.project_manager import get_project_manager
    
    project_path = arguments.get("project_path", "")
    
    if not project_path:
        return "Error: project_path is required"
    
    try:
        pm = get_project_manager()
        project = pm.set_current_project(project_path)
        
        # Notify Telegram
        msg = QueueMessage(
            type=MessageType.INFO,
            priority=Priority.HIGH,
            content=f"📁 Project context set:\n`{project.path}`",
            data={"chat_id": chat_id},
        )
        await queue.send_to_telegram(msg)
        
        return f"Project context set to: {project.path} ({project.name})"
        
    except Exception as e:
        return f"Error setting project context: {str(e)}"


async def _handle_send_code_update(
    arguments: dict[str, Any],
    chat_id: int,
    queue,
) -> str:
    """Handle send_code_update tool."""
    file_path = arguments.get("file_path", "")
    change_type = arguments.get("change_type", "modified")
    summary = arguments.get("summary", "")
    diff_preview = arguments.get("diff_preview")
    
    # Format icon based on change type
    icons = {
        "created": "✨",
        "modified": "📝", 
        "deleted": "🗑️"
    }
    icon = icons.get(change_type, "📄")
    
    # Build message
    message_parts = [
        f"{icon} *{change_type.upper()}*: `{file_path}`",
        f"\n{summary}"
    ]
    
    if diff_preview:
        # Truncate diff if too long for Telegram
        if len(diff_preview) > 1000:
            diff_preview = diff_preview[:1000] + "\n... (truncated)"
        message_parts.append(f"\n```\n{diff_preview}\n```")
    
    msg = QueueMessage(
        type=MessageType.INFO,
        priority=Priority.NORMAL,
        content="\n".join(message_parts),
        data={"chat_id": chat_id},
    )
    await queue.send_to_telegram(msg)
    
    return f"Code update notification sent for {file_path}"
