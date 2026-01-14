"""
Telegram bot command and callback handlers.
"""

import logging
from pathlib import Path
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

from src.config import get_config
from src.bot.keyboards import (
    CallbackData,
    plan_approval_keyboard,
    change_approval_keyboard,
    commit_keyboard,
    error_action_keyboard,
)
from src.bot.message_queue import (
    get_message_queue,
    QueueMessage,
    MessageType,
    Priority,
)
from src.utils.formatting import (
    format_plan_message,
    format_change_message,
    format_error_message,
    format_status_message,
    format_completion_message,
    format_info_message,
    escape_markdown,
)
from src.mcp_server.tools import add_pending_prompt

logger = logging.getLogger(__name__)


def is_authorized(chat_id: int) -> bool:
    """Check if a chat ID is authorized."""
    config = get_config()
    # If no authorized IDs configured, allow all (for development)
    if not config.authorized_chat_ids:
        return True
    return chat_id in config.authorized_chat_ids


# ===== Command Handlers =====

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    if not update.effective_chat:
        return
    
    chat_id = update.effective_chat.id
    
    if not is_authorized(chat_id):
        await update.message.reply_text(
            "⛔ Unauthorized. Your chat ID is not in the allowed list.\n"
            f"Your chat ID: `{chat_id}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    
    welcome_message = """
🚀 *Antigravity Mobile Command*

Your remote Mission Control for coding!

*Setup:*
1️⃣ `/setproject ~/path/to/project`
2️⃣ `/prompt Your coding task here`
3️⃣ Open `~/telegram_tasks.md` in Antigravity

*Commands:*
• `/setproject <path>` - Set working project
• `/prompt <task>` - Send a coding task
• `/screenshot` - Request a screenshot
• `/status` - Check status
• `/cancel` - Cancel operation

*How it works:*
Tasks are written to `~/telegram_tasks.md`
→ Open in Antigravity to auto-execute!

Your chat ID: `{chat_id}`
""".format(chat_id=chat_id)
    
    await update.message.reply_text(
        welcome_message,
        parse_mode=ParseMode.MARKDOWN,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command."""
    await start_command(update, context)


async def prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /prompt command to inject a task."""
    if not update.effective_chat or not update.message:
        return
    
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    # Get the prompt text (everything after /prompt)
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a prompt.\n"
            "Usage: `/prompt Fix the login bug`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    
    prompt_text = " ".join(context.args)
    
    # Get current project context
    project = get_current_project()
    
    if not project:
        await update.message.reply_text(
            "⚠️ *No project set!*\n\n"
            "First set your project:\n"
            "`/setproject /path/to/your/project`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    
    # Write to task file for Antigravity to pick up (auto-opens the file)
    from src.utils.task_file import write_task, copy_to_clipboard
    task_file = write_task(prompt_text, project, update.effective_chat.id, auto_open=True)
    
    # Copy prompt to clipboard for easy pasting
    copy_to_clipboard(prompt_text)
    
    # Also store in memory for MCP retrieval
    add_pending_prompt(prompt_text, project, update.effective_chat.id)
    
    # Send sleek confirmation
    await update.message.reply_text(
        f"🚀 *Task Sent & File Opened!*\n\n"
        f"📝 _{prompt_text[:80]}{'...' if len(prompt_text) > 80 else ''}_\n"
        f"📁 `{project}`\n\n"
        f"✅ File auto-opened on your computer\n"
        f"📋 Prompt copied to clipboard\n\n"
        f"*Paste it into Antigravity to execute!*",
        parse_mode=ParseMode.MARKDOWN,
    )
    
    logger.info(f"Task written and file opened: {task_file}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /status command."""
    if not update.effective_chat or not update.message:
        return
    
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    # TODO: Get actual status from the agent
    await update.message.reply_text(
        "📊 *Current Status*\n\n"
        "No active tasks.\n"
        "Send `/prompt <your task>` to start.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /cancel command."""
    if not update.effective_chat or not update.message:
        return
    
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    queue = get_message_queue()
    
    # Send cancellation to agent
    message = QueueMessage(
        type=MessageType.USER_MESSAGE,
        priority=Priority.CRITICAL,
        content="CANCEL",
        data={"action": "cancel", "chat_id": update.effective_chat.id},
    )
    await queue.send_to_agent(message)
    
    # Clear status message
    queue.clear_status_message()
    
    # Clear task file
    from src.utils.task_file import clear_tasks
    clear_tasks()
    
    await update.message.reply_text("🛑 Task cancelled and cleared.")


async def screenshot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /screenshot command to request a screenshot."""
    if not update.effective_chat or not update.message:
        return
    
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    project = get_current_project()
    
    if not project:
        await update.message.reply_text(
            "⚠️ *No project set!*\n\n"
            "First set your project:\n"
            "`/setproject /path/to/your/project`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    
    # Optional URL from args
    url = " ".join(context.args) if context.args else "http://localhost:3000"
    
    # Write screenshot request to task file
    from src.utils.task_file import write_task
    screenshot_prompt = f"Take a screenshot of the current UI at {url} and send it to me via Telegram using send_artifact."
    task_file = write_task(screenshot_prompt, project, update.effective_chat.id)
    
    await update.message.reply_text(
        f"📸 *Screenshot Requested!*\n\n"
        f"URL: `{url}`\n"
        f"📄 Written to: `~/telegram_tasks.md`\n\n"
        f"Open in Antigravity to capture!",
        parse_mode=ParseMode.MARKDOWN,
    )


# Store current project path
_current_project: Optional[str] = None


def get_current_project() -> Optional[str]:
    """Get the currently set project path."""
    return _current_project


async def setproject_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /setproject command to set the working project."""
    global _current_project
    
    if not update.effective_chat or not update.message:
        return
    
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    if not context.args:
        if _current_project:
            await update.message.reply_text(
                f"📁 *Current Project:*\n`{_current_project}`\n\n"
                "To change: `/setproject /path/to/project`",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text(
                "❌ No project set.\n\n"
                "Usage: `/setproject /path/to/your/project`\n\n"
                "Example:\n`/setproject /Users/bhuvan_ade/my-app`",
                parse_mode=ParseMode.MARKDOWN,
            )
        return
    
    project_path = " ".join(context.args)
    
    # Expand ~ to home directory
    if project_path.startswith("~"):
        project_path = str(Path(project_path).expanduser())
    
    # Validate path exists
    if not Path(project_path).exists():
        await update.message.reply_text(
            f"❌ Path does not exist: `{project_path}`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    
    _current_project = project_path
    
    await update.message.reply_text(
        f"✅ *Project set!*\n\n"
        f"📁 `{project_path}`\n\n"
        "All prompts will now work in this context.",
        parse_mode=ParseMode.MARKDOWN,
    )
    
    # Notify the queue/agent about the project change
    queue = get_message_queue()
    message = QueueMessage(
        type=MessageType.USER_MESSAGE,
        priority=Priority.HIGH,
        content=f"Project context set to: {project_path}",
        data={
            "action": "set_project",
            "project_path": project_path,
            "chat_id": update.effective_chat.id,
        },
    )
    await queue.send_to_agent(message)


async def projects_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /projects command to list recent projects."""
    if not update.effective_chat or not update.message:
        return
    
    if not is_authorized(update.effective_chat.id):
        await update.message.reply_text("⛔ Unauthorized")
        return
    
    # Common project locations to check
    home = Path.home()
    common_paths = [
        home / "antigravity-telegram",
        home / "liveintent-panel",
        home / "projects",
        home / "code",
        home / "dev",
    ]
    
    existing = [p for p in common_paths if p.exists()]
    
    if existing:
        projects_list = "\n".join([f"• `{p}`" for p in existing[:10]])
        message = (
            "📂 *Found Projects:*\n\n"
            f"{projects_list}\n\n"
            "Set one with: `/setproject <path>`"
        )
    else:
        message = (
            "No common project folders found.\n\n"
            "Set your project: `/setproject /path/to/project`"
        )
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)


# ===== Callback Query Handlers =====

async def approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plan/change approval button callbacks."""
    query = update.callback_query
    if not query or not query.data:
        return
    
    await query.answer()
    
    data = query.data
    queue = get_message_queue()
    
    # Extract approval ID if present
    approval_id: Optional[str] = None
    if data.startswith(CallbackData.APPROVAL_PREFIX):
        approval_id = data[len(CallbackData.APPROVAL_PREFIX):]
        approved = True
    elif data == CallbackData.APPROVE_PLAN:
        approved = True
    elif data == CallbackData.REJECT_PLAN:
        approved = False
    elif data == CallbackData.ACCEPT_CHANGE:
        approved = True
    elif data == CallbackData.REJECT_CHANGE:
        approved = False
    else:
        return
    
    # Respond to the approval if we have an ID
    if approval_id:
        await queue.respond_to_approval(approval_id, approved)
    
    # Update the message
    status = "✅ Approved" if approved else "❌ Rejected"
    try:
        await query.edit_message_text(
            f"{query.message.text}\n\n*Status:* {status}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")
    
    # Also send to agent queue
    message = QueueMessage(
        type=MessageType.APPROVAL if approved else MessageType.REJECTION,
        priority=Priority.HIGH,
        content="approved" if approved else "rejected",
        data={"approval_id": approval_id},
    )
    await queue.send_to_agent(message)


async def commit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle commit button callbacks."""
    query = update.callback_query
    if not query or not query.data:
        return
    
    await query.answer()
    
    queue = get_message_queue()
    
    if query.data == CallbackData.COMMIT_PUSH:
        message = QueueMessage(
            type=MessageType.USER_MESSAGE,
            priority=Priority.HIGH,
            content="commit",
            data={"action": "commit_push"},
        )
        status = "📦 Committing changes..."
    else:
        message = QueueMessage(
            type=MessageType.USER_MESSAGE,
            priority=Priority.NORMAL,
            content="skip",
            data={"action": "skip_commit"},
        )
        status = "⏭️ Skipped commit"
    
    await queue.send_to_agent(message)
    
    try:
        await query.edit_message_text(
            f"{query.message.text}\n\n*Status:* {status}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")


async def error_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle error action button callbacks."""
    query = update.callback_query
    if not query or not query.data:
        return
    
    await query.answer()
    
    queue = get_message_queue()
    
    if query.data == CallbackData.RETRY:
        action = "retry"
        status = "🔄 Retrying..."
    elif query.data == CallbackData.STOP:
        action = "stop"
        status = "✋ Stopped"
    elif query.data == CallbackData.CUSTOM_FIX:
        action = "custom_fix"
        status = "💬 Waiting for your instructions..."
        await query.edit_message_text(
            f"{query.message.text}\n\n*Status:* {status}\n\nPlease reply with fix instructions.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    else:
        return
    
    message = QueueMessage(
        type=MessageType.USER_MESSAGE,
        priority=Priority.HIGH,
        content=action,
        data={"action": action},
    )
    await queue.send_to_agent(message)
    
    try:
        await query.edit_message_text(
            f"{query.message.text}\n\n*Status:* {status}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")


async def general_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle general callback queries."""
    query = update.callback_query
    if not query or not query.data:
        return
    
    await query.answer()
    
    queue = get_message_queue()
    
    if query.data == CallbackData.CONTINUE:
        message = QueueMessage(
            type=MessageType.USER_MESSAGE,
            priority=Priority.NORMAL,
            content="continue",
            data={"action": "continue"},
        )
        status = "▶️ Continuing..."
    elif query.data == CallbackData.CANCEL:
        message = QueueMessage(
            type=MessageType.USER_MESSAGE,
            priority=Priority.HIGH,
            content="cancel",
            data={"action": "cancel"},
        )
        status = "❌ Cancelled"
    else:
        return
    
    await queue.send_to_agent(message)
    
    try:
        await query.edit_message_text(
            f"{query.message.text}\n\n*Status:* {status}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.warning(f"Failed to edit message: {e}")


# ===== Message Handler =====

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages (not commands)."""
    if not update.effective_chat or not update.message or not update.message.text:
        return
    
    if not is_authorized(update.effective_chat.id):
        return
    
    text = update.message.text
    queue = get_message_queue()
    
    # Check if this is a reply to a bot message (feedback on artifact, etc.)
    reply_to = update.message.reply_to_message
    if reply_to and reply_to.from_user and reply_to.from_user.is_bot:
        message = QueueMessage(
            type=MessageType.USER_MESSAGE,
            priority=Priority.HIGH,
            content=text,
            data={
                "chat_id": update.effective_chat.id,
                "is_reply": True,
                "reply_to_message_id": reply_to.message_id,
            },
        )
    else:
        # Treat as a direct instruction/prompt
        message = QueueMessage(
            type=MessageType.USER_MESSAGE,
            priority=Priority.NORMAL,
            content=text,
            data={"chat_id": update.effective_chat.id},
        )
    
    await queue.send_to_agent(message)
    
    # Acknowledge
    await update.message.reply_text("📨 Message received")


# ===== Message Sending Functions =====

async def send_plan_approval(
    app: Application,
    chat_id: int,
    plan_summary: str,
    files_affected: list[str] | None = None,
    task_name: str | None = None,
    approval_id: str | None = None,
) -> int:
    """Send a plan for approval and return the message ID."""
    text = format_plan_message(plan_summary, files_affected, task_name)
    keyboard = plan_approval_keyboard(approval_id)
    
    message = await app.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )
    return message.message_id


async def send_change_approval(
    app: Application,
    chat_id: int,
    change_summary: str,
    diff_preview: str | None = None,
    change_id: str | None = None,
) -> int:
    """Send a code change for approval and return the message ID."""
    text = format_change_message(change_summary, diff_preview)
    keyboard = change_approval_keyboard(change_id)
    
    message = await app.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )
    return message.message_id


async def send_error_notification(
    app: Application,
    chat_id: int,
    error_message: str,
    stack_trace: str | None = None,
    command: str | None = None,
) -> int:
    """Send an error notification and return the message ID."""
    text = format_error_message(error_message, stack_trace, command)
    keyboard = error_action_keyboard()
    
    message = await app.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )
    return message.message_id


async def send_or_update_status(
    app: Application,
    chat_id: int,
    status_text: str,
    progress_percent: int | None = None,
    steps: list[tuple[str, bool]] | None = None,
) -> int:
    """Send or update a status ticker message."""
    queue = get_message_queue()
    current_chat_id, current_message_id = queue.get_status_message()
    
    text = format_status_message(status_text, progress_percent, steps)
    
    if current_chat_id == chat_id and current_message_id:
        # Try to edit existing message
        try:
            await app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=current_message_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
            return current_message_id
        except Exception:
            pass  # Fall through to send new message
    
    # Send new message
    message = await app.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
    )
    queue.set_status_message(chat_id, message.message_id)
    return message.message_id


async def send_artifact(
    app: Application,
    chat_id: int,
    artifact_path: Path,
    caption: str | None = None,
) -> int:
    """Send an artifact (image/video) and return the message ID."""
    if not artifact_path.exists():
        raise FileNotFoundError(f"Artifact not found: {artifact_path}")
    
    suffix = artifact_path.suffix.lower()
    
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        with open(artifact_path, "rb") as f:
            message = await app.bot.send_photo(
                chat_id=chat_id,
                photo=f,
                caption=caption,
            )
    elif suffix in {".mp4", ".webm", ".mov"}:
        with open(artifact_path, "rb") as f:
            message = await app.bot.send_video(
                chat_id=chat_id,
                video=f,
                caption=caption,
            )
    else:
        with open(artifact_path, "rb") as f:
            message = await app.bot.send_document(
                chat_id=chat_id,
                document=f,
                caption=caption,
            )
    
    return message.message_id


async def send_completion(
    app: Application,
    chat_id: int,
    summary: str,
    files_changed: int | None = None,
    duration: str | None = None,
) -> int:
    """Send a completion message and return the message ID."""
    text = format_completion_message(summary, files_changed, duration)
    keyboard = commit_keyboard()
    
    message = await app.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )
    
    # Clear status message
    get_message_queue().clear_status_message()
    
    return message.message_id


# ===== Application Setup =====

def setup_handlers(app: Application) -> None:
    """Set up all command and callback handlers."""
    
    # Command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("prompt", prompt_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("screenshot", screenshot_command))
    app.add_handler(CommandHandler("setproject", setproject_command))
    app.add_handler(CommandHandler("projects", projects_command))
    
    # Callback query handlers
    app.add_handler(CallbackQueryHandler(
        approval_callback,
        pattern=f"^({CallbackData.APPROVE_PLAN}|{CallbackData.REJECT_PLAN}|"
                f"{CallbackData.ACCEPT_CHANGE}|{CallbackData.REJECT_CHANGE}|"
                f"{CallbackData.APPROVAL_PREFIX})",
    ))
    app.add_handler(CallbackQueryHandler(
        commit_callback,
        pattern=f"^({CallbackData.COMMIT_PUSH}|{CallbackData.SKIP_COMMIT})$",
    ))
    app.add_handler(CallbackQueryHandler(
        error_action_callback,
        pattern=f"^({CallbackData.RETRY}|{CallbackData.STOP}|{CallbackData.CUSTOM_FIX})$",
    ))
    app.add_handler(CallbackQueryHandler(
        general_callback,
        pattern=f"^({CallbackData.CONTINUE}|{CallbackData.CANCEL})$",
    ))
    
    # Text message handler (for replies and direct instructions)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    
    logger.info("Telegram handlers configured")
