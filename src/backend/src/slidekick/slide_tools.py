"""
Slide Tools Module

Implements slide deck-specific tools for the agentic slide presentation system.

Tools provided:
- navigate_slide: Navigate between slides
- get_presentation_context: Get current state
- inject_summary: Inject summary slide

Future tools (to be implemented):
- inject_image: Generate and inject images via Imagen API
- add_content: Add text/bullet points
"""

import logging
from typing import Any, Optional

from slidekick.state_manager import StateManager

logger = logging.getLogger(__name__)


class SlideTools:
    """
    Collection of slide deck control tools.
    
    These tools integrate with StateManager to provide presentation
    control functionality for the Gemini Live API.
    """
    
    def __init__(self, state_manager: StateManager):
        """
        Initialize slide tools with a state manager.
        
        Args:
            state_manager: StateManager instance
        """
        self.state = state_manager
    
    async def navigate_slide(
        self, 
        direction: str, 
        index: Optional[int] = None
    ) -> dict[str, Any]:
        """
        Navigate to a different slide.
        
        Args:
            direction: 'next', 'prev', or 'jump'
            index: Slide index (required for 'jump')
            
        Returns:
            Dict with navigation result
        """
        try:
            new_index = await self.state.navigate(direction, index)
            total = await self.state.get_total_slides()
            
            logger.info(f"Navigate: {direction} -> slide {new_index + 1} of {total or '?'}")
            
            return {
                "action": "navigate",
                "direction": direction,
                "current_slide": new_index,
                "total_slides": total,
                "success": True,
            }
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return {
                "action": "navigate",
                "success": False,
                "error": str(e),
            }
    
    async def get_presentation_context(self) -> dict[str, Any]:
        """
        Get current presentation context.
        
        Returns current slide index, total slides, and session info.
        
        Returns:
            Dict with presentation context
        """
        try:
            context = await self.state.get_context()
            return {
                "action": "get_context",
                "success": True,
                **context,
            }
        except Exception as e:
            logger.error(f"Failed to get context: {e}")
            return {
                "action": "get_context",
                "success": False,
                "error": str(e),
            }

    async def inject_summary(self, summary_text: str) -> dict[str, Any]:
        """
        Inject a summary slide into the presentation.
        
        Args:
            summary_text: The text content to display in the summary.
            
        Returns:
            Dict with injection command.
        """
        try:
            logger.info(f"Injecting summary: {summary_text[:50]}...")
            
            # Simple HTML formatting using a Reveal.js compatible structure
            html_content = f"""
            <h2>Presentation Summary</h2>
            <div class="summary-content" style="text-align: left; font-size: 0.8em;">
{summary_text}
            </div>
            """
            
            return {
                "action": "inject_summary",
                "summary": summary_text,
                "html": html_content,
                "success": True
            }
        except Exception as e:
            logger.error(f"Inject summary failed: {e}")
            return {
                "action": "inject_summary",
                "success": False,
                "error": str(e)
            }

    async def trigger_summary(self, conversational_context: str = "") -> dict[str, Any]:
        """
        Trigger the background summary generation process.
        
        Args:
            conversational_context: Notes from the live model about what the speaker said.
        """
        logger.info("Triggering background summary generation")
        return {
            "action": "start_background_summary",
            "conversational_context": conversational_context,
            "success": True,
            "message": "Summary generation started in background."
        }
