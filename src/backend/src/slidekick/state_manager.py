"""
State Manager Module

Manages presentation state including current slide position and session metadata
for the agentic slide deck.

This module provides:
- Current slide index tracking
- Total slide count management
- Navigation state management
- Session metadata
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StateManager:
    """
    Manages presentation state for WebSocket sessions.
    
    Tracks:
    - Current slide position
    - Total slides (reported by frontend)
    - Session metadata
    
    Note: When used with a real Reveal.js frontend, the frontend is the source
    of truth for slide navigation. This manager tracks state for context and
    tool responses.
    """
    
    def __init__(self, total_slides: int = 0):
        """
        Initialize the state manager.
        
        Args:
            total_slides: Total number of slides (0 = unknown, will be set by frontend)
        """
        self.total_slides = total_slides
        self.current_slide = 0
        self.session_metadata: dict[str, Any] = {
            "started_at": datetime.now(),
            "session_id": None,
        }
        self._lock = asyncio.Lock()
        logger.debug(f"StateManager initialized with {total_slides} slides")
    
    async def navigate(self, direction: str, index: Optional[int] = None) -> int:
        """
        Update slide position based on navigation direction.
        
        Args:
            direction: "next", "prev", or "jump"
            index: Target slide index (required for "jump")
            
        Returns:
            New slide index
            
        Raises:
            ValueError: If navigation is invalid
        """
        async with self._lock:
            if direction == "next":
                # Allow going past known bounds if total_slides is 0 (unknown)
                if self.total_slides > 0:
                    new_index = min(self.current_slide + 1, self.total_slides - 1)
                else:
                    new_index = self.current_slide + 1
                    
            elif direction == "prev":
                new_index = max(self.current_slide - 1, 0)
                
            elif direction == "jump":
                if index is None:
                    raise ValueError("Index required for 'jump' navigation")
                new_index = max(0, index)
                if self.total_slides > 0:
                    new_index = min(new_index, self.total_slides - 1)
            else:
                raise ValueError(f"Invalid direction: {direction}")
            
            old_index = self.current_slide
            self.current_slide = new_index
            
            logger.debug(f"Navigation: {direction} from {old_index} to {new_index}")
            return new_index
    
    async def set_current_slide(self, index: int) -> None:
        """
        Set the current slide index (typically from frontend sync).
        
        Args:
            index: Slide index (0-based)
        """
        async with self._lock:
            self.current_slide = max(0, index)
            logger.debug(f"Current slide set to {self.current_slide}")
    
    async def get_current_slide(self) -> int:
        """Get the current slide index."""
        async with self._lock:
            return self.current_slide
    
    async def set_total_slides(self, total: int) -> None:
        """
        Set the total number of slides (typically from frontend).
        
        Args:
            total: Total slide count
        """
        async with self._lock:
            self.total_slides = max(0, total)
            logger.info(f"Total slides set to {self.total_slides}")
    
    async def get_total_slides(self) -> int:
        """Get the total number of slides."""
        async with self._lock:
            return self.total_slides
    
    async def get_context(self) -> dict[str, Any]:
        """
        Get presentation context summary.
        
        Returns:
            Dict with current state information
        """
        async with self._lock:
            return {
                "current_slide": self.current_slide,
                "total_slides": self.total_slides,
                "session_metadata": self.session_metadata.copy(),
            }
    
    async def set_session_id(self, session_id: Any) -> None:
        """Set the session ID."""
        async with self._lock:
            self.session_metadata["session_id"] = session_id
    
    async def reset(self) -> None:
        """Reset state to initial values."""
        async with self._lock:
            self.current_slide = 0
            self.session_metadata = {
                "started_at": datetime.now(),
                "session_id": None,
            }
            logger.debug("StateManager reset")

