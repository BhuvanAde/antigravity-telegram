"""
Async message queue for communication between Telegram bot and MCP server.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable, Optional
from uuid import uuid4


class MessageType(Enum):
    """Types of messages in the queue."""
    
    # From user to agent
    PROMPT = "prompt"
    APPROVAL = "approval"
    REJECTION = "rejection"
    USER_MESSAGE = "user_message"
    
    # From agent to user
    PLAN_APPROVAL_REQUEST = "plan_approval_request"
    CHANGE_APPROVAL_REQUEST = "change_approval_request"
    STATUS_UPDATE = "status_update"
    ARTIFACT = "artifact"
    ERROR = "error"
    INFO = "info"
    COMPLETION = "completion"


class Priority(Enum):
    """Message priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class QueueMessage:
    """A message in the queue."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    type: MessageType = MessageType.INFO
    priority: Priority = Priority.NORMAL
    content: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    # For approval tracking
    approval_id: Optional[str] = None
    requires_response: bool = False
    response_future: Optional[asyncio.Future] = None


class MessageQueue:
    """
    Bidirectional async message queue for Telegram <-> MCP communication.
    """
    
    def __init__(self):
        # Queues for different directions
        self._to_telegram: asyncio.Queue[QueueMessage] = asyncio.Queue()
        self._to_agent: asyncio.Queue[QueueMessage] = asyncio.Queue()
        
        # Pending approvals waiting for response
        self._pending_approvals: dict[str, QueueMessage] = {}
        
        # Callbacks for real-time notifications
        self._telegram_callbacks: list[Callable[[QueueMessage], Awaitable[None]]] = []
        self._agent_callbacks: list[Callable[[QueueMessage], Awaitable[None]]] = []
        
        # Status ticker message ID (for editing instead of sending new)
        self._status_message_id: Optional[int] = None
        self._status_chat_id: Optional[int] = None
    
    # ===== Telegram -> Agent direction =====
    
    async def send_to_agent(self, message: QueueMessage) -> None:
        """Send a message to the agent."""
        await self._to_agent.put(message)
        for callback in self._agent_callbacks:
            await callback(message)
    
    async def receive_from_telegram(self, timeout: Optional[float] = None) -> Optional[QueueMessage]:
        """Receive a message from Telegram (for the agent to process)."""
        try:
            if timeout:
                return await asyncio.wait_for(self._to_agent.get(), timeout)
            return await self._to_agent.get()
        except asyncio.TimeoutError:
            return None
    
    # ===== Agent -> Telegram direction =====
    
    async def send_to_telegram(self, message: QueueMessage) -> None:
        """Send a message to Telegram."""
        await self._to_telegram.put(message)
        for callback in self._telegram_callbacks:
            await callback(message)
    
    async def receive_from_agent(self, timeout: Optional[float] = None) -> Optional[QueueMessage]:
        """Receive a message from the agent (for Telegram to display)."""
        try:
            if timeout:
                return await asyncio.wait_for(self._to_telegram.get(), timeout)
            return await self._to_telegram.get()
        except asyncio.TimeoutError:
            return None
    
    # ===== Approval workflow =====
    
    async def request_approval(
        self,
        approval_type: MessageType,
        content: str,
        data: dict[str, Any] | None = None,
        timeout: float = 300.0,  # 5 minute default timeout
    ) -> tuple[bool, Optional[str]]:
        """
        Request approval from the user and wait for response.
        
        Args:
            approval_type: Type of approval request
            content: Message content to display
            data: Additional data for the request
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (approved: bool, user_message: Optional[str])
        """
        approval_id = str(uuid4())
        future: asyncio.Future[tuple[bool, Optional[str]]] = asyncio.Future()
        
        message = QueueMessage(
            type=approval_type,
            priority=Priority.HIGH,
            content=content,
            data=data or {},
            approval_id=approval_id,
            requires_response=True,
            response_future=future,
        )
        
        self._pending_approvals[approval_id] = message
        await self.send_to_telegram(message)
        
        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            del self._pending_approvals[approval_id]
            return False, "Approval timed out"
    
    async def respond_to_approval(
        self,
        approval_id: str,
        approved: bool,
        user_message: Optional[str] = None,
    ) -> bool:
        """
        Respond to a pending approval request.
        
        Args:
            approval_id: ID of the approval to respond to
            approved: Whether the request was approved
            user_message: Optional message from the user
            
        Returns:
            True if the approval was found and responded to
        """
        message = self._pending_approvals.pop(approval_id, None)
        if message and message.response_future:
            message.response_future.set_result((approved, user_message))
            return True
        return False
    
    # ===== Status ticker =====
    
    def set_status_message(self, chat_id: int, message_id: int) -> None:
        """Set the current status ticker message for editing."""
        self._status_chat_id = chat_id
        self._status_message_id = message_id
    
    def get_status_message(self) -> tuple[Optional[int], Optional[int]]:
        """Get the current status ticker message info."""
        return self._status_chat_id, self._status_message_id
    
    def clear_status_message(self) -> None:
        """Clear the status ticker message reference."""
        self._status_chat_id = None
        self._status_message_id = None
    
    # ===== Callbacks =====
    
    def on_telegram_message(
        self,
        callback: Callable[[QueueMessage], Awaitable[None]],
    ) -> None:
        """Register a callback for messages going to Telegram."""
        self._telegram_callbacks.append(callback)
    
    def on_agent_message(
        self,
        callback: Callable[[QueueMessage], Awaitable[None]],
    ) -> None:
        """Register a callback for messages going to the agent."""
        self._agent_callbacks.append(callback)


# Global message queue instance
_message_queue: Optional[MessageQueue] = None


def get_message_queue() -> MessageQueue:
    """Get the global message queue instance."""
    global _message_queue
    if _message_queue is None:
        _message_queue = MessageQueue()
    return _message_queue


def set_message_queue(queue: MessageQueue) -> None:
    """Set the global message queue instance."""
    global _message_queue
    _message_queue = queue
