"""
Inline keyboard builders for Telegram bot interactions.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class CallbackData:
    """Callback data constants for inline buttons."""
    
    # Plan approval
    APPROVE_PLAN = "approve_plan"
    REJECT_PLAN = "reject_plan"
    
    # Change approval
    ACCEPT_CHANGE = "accept_change"
    REJECT_CHANGE = "reject_change"
    
    # Commit actions
    COMMIT_PUSH = "commit_push"
    SKIP_COMMIT = "skip_commit"
    
    # Error actions
    RETRY = "retry"
    STOP = "stop"
    CUSTOM_FIX = "custom_fix"
    
    # General
    CANCEL = "cancel"
    CONTINUE = "continue"
    
    # Prefixes for data with IDs
    APPROVAL_PREFIX = "approval:"
    ARTIFACT_PREFIX = "artifact:"


def plan_approval_keyboard(approval_id: str | None = None) -> InlineKeyboardMarkup:
    """
    Create keyboard for plan approval.
    
    Returns:
        Keyboard with [✅ Approve Plan] [❌ Cancel] buttons
    """
    approve_data = f"{CallbackData.APPROVAL_PREFIX}{approval_id}" if approval_id else CallbackData.APPROVE_PLAN
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve Plan", callback_data=approve_data),
            InlineKeyboardButton("❌ Cancel", callback_data=CallbackData.REJECT_PLAN),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def change_approval_keyboard(change_id: str | None = None) -> InlineKeyboardMarkup:
    """
    Create keyboard for code change approval.
    
    Returns:
        Keyboard with [✅ Accept] [❌ Reject] buttons
    """
    accept_data = f"{CallbackData.APPROVAL_PREFIX}{change_id}" if change_id else CallbackData.ACCEPT_CHANGE
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Accept", callback_data=accept_data),
            InlineKeyboardButton("❌ Reject", callback_data=CallbackData.REJECT_CHANGE),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def commit_keyboard() -> InlineKeyboardMarkup:
    """
    Create keyboard for commit actions.
    
    Returns:
        Keyboard with [📦 Commit & Push] [⏭️ Skip] buttons
    """
    keyboard = [
        [
            InlineKeyboardButton("📦 Commit & Push", callback_data=CallbackData.COMMIT_PUSH),
            InlineKeyboardButton("⏭️ Skip", callback_data=CallbackData.SKIP_COMMIT),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def error_action_keyboard() -> InlineKeyboardMarkup:
    """
    Create keyboard for error handling actions.
    
    Returns:
        Keyboard with [🔄 Retry] [✋ Stop] [💬 Custom Fix] buttons
    """
    keyboard = [
        [
            InlineKeyboardButton("🔄 Retry", callback_data=CallbackData.RETRY),
            InlineKeyboardButton("✋ Stop", callback_data=CallbackData.STOP),
        ],
        [
            InlineKeyboardButton("💬 Custom Fix", callback_data=CallbackData.CUSTOM_FIX),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def continue_cancel_keyboard() -> InlineKeyboardMarkup:
    """
    Create a simple continue/cancel keyboard.
    
    Returns:
        Keyboard with [▶️ Continue] [❌ Cancel] buttons
    """
    keyboard = [
        [
            InlineKeyboardButton("▶️ Continue", callback_data=CallbackData.CONTINUE),
            InlineKeyboardButton("❌ Cancel", callback_data=CallbackData.CANCEL),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def custom_keyboard(buttons: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """
    Create a custom keyboard from a list of (text, callback_data) tuples.
    
    Args:
        buttons: List of (button_text, callback_data) tuples
        
    Returns:
        InlineKeyboardMarkup with the specified buttons
    """
    keyboard = [
        [InlineKeyboardButton(text, callback_data=data) for text, data in buttons]
    ]
    return InlineKeyboardMarkup(keyboard)


def multi_row_keyboard(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    """
    Create a multi-row keyboard.
    
    Args:
        rows: List of rows, each row is a list of (button_text, callback_data) tuples
        
    Returns:
        InlineKeyboardMarkup with the specified button layout
    """
    keyboard = [
        [InlineKeyboardButton(text, callback_data=data) for text, data in row]
        for row in rows
    ]
    return InlineKeyboardMarkup(keyboard)
