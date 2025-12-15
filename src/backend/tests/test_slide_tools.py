"""
Unit tests for SlideTools

Tests slide control tools with StateManager integration:
- navigate_slide: Navigate between slides
- get_presentation_context: Get current state
- inject_summary: Inject summary slide content
- trigger_summary: Trigger background summary generation
"""

import pytest

from slidekick.state_manager import StateManager
from slidekick.slide_tools import SlideTools


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def state_manager():
    """Create a StateManager instance for testing."""
    return StateManager(total_slides=10)


@pytest.fixture
def slide_tools(state_manager):
    """Create a SlideTools instance for testing."""
    return SlideTools(state_manager)


# =============================================================================
# Navigation Tests
# =============================================================================


class TestNavigateSlide:
    """Tests for the navigate_slide tool."""
    
    @pytest.mark.asyncio
    async def test_navigate_next(self, slide_tools, state_manager):
        """Test navigating to next slide."""
        await state_manager.set_current_slide(3)
        
        result = await slide_tools.navigate_slide("next")
        
        assert result["success"] is True
        assert result["action"] == "navigate"
        assert result["direction"] == "next"
        assert result["current_slide"] == 4
        assert result["total_slides"] == 10
    
    @pytest.mark.asyncio
    async def test_navigate_prev(self, slide_tools, state_manager):
        """Test navigating to previous slide."""
        await state_manager.set_current_slide(5)
        
        result = await slide_tools.navigate_slide("prev")
        
        assert result["success"] is True
        assert result["direction"] == "prev"
        assert result["current_slide"] == 4
    
    @pytest.mark.asyncio
    async def test_navigate_jump(self, slide_tools):
        """Test jumping to specific slide."""
        result = await slide_tools.navigate_slide("jump", index=7)
        
        assert result["success"] is True
        assert result["direction"] == "jump"
        assert result["current_slide"] == 7
    
    @pytest.mark.asyncio
    async def test_navigate_jump_missing_index(self, slide_tools):
        """Test navigation with missing index for jump."""
        result = await slide_tools.navigate_slide("jump")  # Missing index
        
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_navigate_invalid_direction(self, slide_tools):
        """Test navigation with invalid direction."""
        result = await slide_tools.navigate_slide("sideways")
        
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_navigate_next_at_boundary(self, slide_tools, state_manager):
        """Test navigating next at last slide."""
        await state_manager.set_current_slide(9)  # Last slide
        
        result = await slide_tools.navigate_slide("next")
        
        assert result["success"] is True
        assert result["current_slide"] == 9  # Should stay at last slide
    
    @pytest.mark.asyncio
    async def test_navigate_prev_at_boundary(self, slide_tools, state_manager):
        """Test navigating prev at first slide."""
        await state_manager.set_current_slide(0)
        
        result = await slide_tools.navigate_slide("prev")
        
        assert result["success"] is True
        assert result["current_slide"] == 0  # Should stay at first slide


# =============================================================================
# Presentation Context Tests
# =============================================================================


class TestGetPresentationContext:
    """Tests for the get_presentation_context tool."""
    
    @pytest.mark.asyncio
    async def test_get_context_basic(self, slide_tools, state_manager):
        """Test getting basic presentation context."""
        await state_manager.set_current_slide(5)
        
        result = await slide_tools.get_presentation_context()
        
        assert result["success"] is True
        assert result["action"] == "get_context"
        assert result["current_slide"] == 5
        assert result["total_slides"] == 10
        assert "session_metadata" in result
    
    @pytest.mark.asyncio
    async def test_get_context_with_session_id(self, slide_tools, state_manager):
        """Test that context includes session metadata."""
        await state_manager.set_session_id("test-session-123")
        await state_manager.set_current_slide(3)
        
        result = await slide_tools.get_presentation_context()
        
        assert result["success"] is True
        assert result["session_metadata"]["session_id"] == "test-session-123"
    
    @pytest.mark.asyncio
    async def test_get_context_at_start(self, slide_tools):
        """Test getting context at presentation start."""
        result = await slide_tools.get_presentation_context()
        
        assert result["success"] is True
        assert result["current_slide"] == 0


# =============================================================================
# Inject Summary Tests
# =============================================================================


class TestInjectSummary:
    """Tests for the inject_summary tool."""
    
    @pytest.mark.asyncio
    async def test_inject_summary_basic(self, slide_tools):
        """Test injecting a summary with text content."""
        summary_text = "Key point 1. Key point 2. Key point 3."
        
        result = await slide_tools.inject_summary(summary_text)
        
        assert result["success"] is True
        assert result["action"] == "inject_summary"
        assert result["summary"] == summary_text
        assert "html" in result
        assert "Presentation Summary" in result["html"]
        assert summary_text in result["html"]
    
    @pytest.mark.asyncio
    async def test_inject_summary_with_html_content(self, slide_tools):
        """Test that summary text is included in HTML wrapper."""
        summary_text = "<ul><li>First point</li><li>Second point</li></ul>"
        
        result = await slide_tools.inject_summary(summary_text)
        
        assert result["success"] is True
        assert summary_text in result["html"]
        assert "summary-content" in result["html"]
    
    @pytest.mark.asyncio
    async def test_inject_summary_empty_text(self, slide_tools):
        """Test injecting summary with empty text."""
        result = await slide_tools.inject_summary("")
        
        # Should still succeed - empty is valid
        assert result["success"] is True
        assert result["summary"] == ""
    
    @pytest.mark.asyncio
    async def test_inject_summary_long_text(self, slide_tools):
        """Test injecting summary with long text."""
        long_text = "This is a very long summary. " * 100
        
        result = await slide_tools.inject_summary(long_text)
        
        assert result["success"] is True
        assert len(result["summary"]) > 1000


# =============================================================================
# Trigger Summary Tests
# =============================================================================


class TestTriggerSummary:
    """Tests for the trigger_summary tool."""
    
    @pytest.mark.asyncio
    async def test_trigger_summary_basic(self, slide_tools):
        """Test triggering background summary generation."""
        result = await slide_tools.trigger_summary()
        
        assert result["success"] is True
        assert result["action"] == "start_background_summary"
        assert "message" in result
    
    @pytest.mark.asyncio
    async def test_trigger_summary_with_context(self, slide_tools):
        """Test triggering summary with conversational context."""
        context = "The speaker discussed AI advancements and future trends."
        
        result = await slide_tools.trigger_summary(conversational_context=context)
        
        assert result["success"] is True
        assert result["conversational_context"] == context
    
    @pytest.mark.asyncio
    async def test_trigger_summary_empty_context(self, slide_tools):
        """Test triggering summary with empty context."""
        result = await slide_tools.trigger_summary(conversational_context="")
        
        assert result["success"] is True
        assert result["conversational_context"] == ""


# =============================================================================
# Integration Tests
# =============================================================================


class TestSlideToolsIntegration:
    """Integration tests for multiple slide tools working together."""
    
    @pytest.mark.asyncio
    async def test_navigation_and_context(self, slide_tools, state_manager):
        """Test navigation followed by context retrieval."""
        # Navigate to slide 5
        nav_result = await slide_tools.navigate_slide("jump", index=5)
        assert nav_result["success"] is True
        
        # Get context
        context = await slide_tools.get_presentation_context()
        assert context["current_slide"] == 5
    
    @pytest.mark.asyncio
    async def test_full_workflow(self, slide_tools, state_manager):
        """Test a complete presentation workflow."""
        # Start at beginning
        context = await slide_tools.get_presentation_context()
        assert context["current_slide"] == 0
        
        # Navigate through slides
        await slide_tools.navigate_slide("next")
        await slide_tools.navigate_slide("next")
        await slide_tools.navigate_slide("next")
        
        context = await slide_tools.get_presentation_context()
        assert context["current_slide"] == 3
        
        # Jump to specific slide
        await slide_tools.navigate_slide("jump", index=7)
        
        context = await slide_tools.get_presentation_context()
        assert context["current_slide"] == 7
        
        # Trigger summary
        summary_trigger = await slide_tools.trigger_summary(
            conversational_context="We covered the main architecture."
        )
        assert summary_trigger["success"] is True
        
        # Inject summary content
        summary_inject = await slide_tools.inject_summary("Architecture overview complete.")
        assert summary_inject["success"] is True
    
    @pytest.mark.asyncio
    async def test_multiple_navigations(self, slide_tools, state_manager):
        """Test multiple consecutive navigations."""
        # Start at slide 5
        await state_manager.set_current_slide(5)
        
        # Navigate forward
        result1 = await slide_tools.navigate_slide("next")
        assert result1["current_slide"] == 6
        
        result2 = await slide_tools.navigate_slide("next")
        assert result2["current_slide"] == 7
        
        # Navigate backward
        result3 = await slide_tools.navigate_slide("prev")
        assert result3["current_slide"] == 6
        
        # Jump
        result4 = await slide_tools.navigate_slide("jump", index=0)
        assert result4["current_slide"] == 0
    
    @pytest.mark.asyncio
    async def test_state_manager_shared_correctly(self, slide_tools, state_manager):
        """Test that slide_tools shares state with state_manager."""
        # Navigate via slide_tools
        await slide_tools.navigate_slide("jump", index=3)
        
        # Check state_manager directly
        current = await state_manager.get_current_slide()
        assert current == 3
        
        # Modify state_manager directly
        await state_manager.set_current_slide(7)
        
        # Check via slide_tools
        context = await slide_tools.get_presentation_context()
        assert context["current_slide"] == 7
