"""
Approval state management for MCP server.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class ApprovalStatus(Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
    """An approval request waiting for user response."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    request_type: str = "plan"  # plan, change, commit
    content: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    user_message: Optional[str] = None
    
    # For async waiting
    _future: Optional[asyncio.Future] = field(default=None, repr=False)


class ApprovalStateManager:
    """
    Manages the state of approval requests.
    
    Thread-safe and async-compatible.
    """
    
    def __init__(self):
        self._requests: dict[str, ApprovalRequest] = {}
        self._lock = asyncio.Lock()
        
        # Current task state
        self._current_task: Optional[str] = None
        self._task_status: str = "idle"
        self._last_update: datetime = datetime.now()
    
    async def create_approval(
        self,
        request_type: str,
        content: str,
        data: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Create a new approval request."""
        async with self._lock:
            request = ApprovalRequest(
                request_type=request_type,
                content=content,
                data=data or {},
                _future=asyncio.Future(),
            )
            self._requests[request.id] = request
            return request
    
    async def wait_for_approval(
        self,
        request_id: str,
        timeout: float = 300.0,
    ) -> tuple[bool, Optional[str]]:
        """
        Wait for an approval request to be resolved.
        
        Args:
            request_id: ID of the request to wait for
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (approved, user_message)
        """
        request = self._requests.get(request_id)
        if not request or not request._future:
            return False, "Request not found"
        
        try:
            result = await asyncio.wait_for(request._future, timeout)
            return result
        except asyncio.TimeoutError:
            async with self._lock:
                request.status = ApprovalStatus.TIMED_OUT
                request.resolved_at = datetime.now()
            return False, "Request timed out"
    
    async def resolve_approval(
        self,
        request_id: str,
        approved: bool,
        user_message: Optional[str] = None,
    ) -> bool:
        """
        Resolve an approval request.
        
        Args:
            request_id: ID of the request to resolve
            approved: Whether the request was approved
            user_message: Optional message from the user
            
        Returns:
            True if the request was found and resolved
        """
        async with self._lock:
            request = self._requests.get(request_id)
            if not request:
                return False
            
            request.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            request.resolved_at = datetime.now()
            request.user_message = user_message
            
            if request._future and not request._future.done():
                request._future.set_result((approved, user_message))
            
            return True
    
    async def cancel_approval(self, request_id: str) -> bool:
        """Cancel a pending approval request."""
        async with self._lock:
            request = self._requests.get(request_id)
            if not request or request.status != ApprovalStatus.PENDING:
                return False
            
            request.status = ApprovalStatus.CANCELLED
            request.resolved_at = datetime.now()
            
            if request._future and not request._future.done():
                request._future.set_result((False, "Cancelled"))
            
            return True
    
    async def cancel_all_pending(self) -> int:
        """Cancel all pending approval requests."""
        cancelled = 0
        async with self._lock:
            for request in self._requests.values():
                if request.status == ApprovalStatus.PENDING:
                    request.status = ApprovalStatus.CANCELLED
                    request.resolved_at = datetime.now()
                    if request._future and not request._future.done():
                        request._future.set_result((False, "Cancelled"))
                    cancelled += 1
        return cancelled
    
    def get_pending_requests(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        return [
            r for r in self._requests.values()
            if r.status == ApprovalStatus.PENDING
        ]
    
    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get an approval request by ID."""
        return self._requests.get(request_id)
    
    # ===== Task State =====
    
    def set_current_task(self, task_name: str) -> None:
        """Set the current task name."""
        self._current_task = task_name
        self._last_update = datetime.now()
    
    def set_task_status(self, status: str) -> None:
        """Set the current task status."""
        self._task_status = status
        self._last_update = datetime.now()
    
    def get_task_state(self) -> dict[str, Any]:
        """Get the current task state."""
        return {
            "current_task": self._current_task,
            "status": self._task_status,
            "last_update": self._last_update.isoformat(),
            "pending_approvals": len(self.get_pending_requests()),
        }
    
    def clear_task(self) -> None:
        """Clear the current task state."""
        self._current_task = None
        self._task_status = "idle"
        self._last_update = datetime.now()


# Global state manager
_state_manager: Optional[ApprovalStateManager] = None


def get_state_manager() -> ApprovalStateManager:
    """Get the global state manager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = ApprovalStateManager()
    return _state_manager


def set_state_manager(manager: ApprovalStateManager) -> None:
    """Set the global state manager instance."""
    global _state_manager
    _state_manager = manager
