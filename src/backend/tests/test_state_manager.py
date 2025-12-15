"""
Unit tests for StateManager

Tests slide tracking, transcript management, session metadata, and state operations.
"""

import asyncio
import pytest
from datetime import datetime

from slidekick.state_manager import StateManager


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def state_manager():
    """Create a StateManager instance for testing."""
    return StateManager(total_slides=10)


# =============================================================================
# Initialization Tests
# =============================================================================


class TestStateManagerInitialization:
    """Tests for StateManager initialization."""
    
    @pytest.mark.asyncio
    async def test_initialization_with_total_slides(self):
        """Test that StateManager initializes correctly with slide count."""
        manager = StateManager(total_slides=10)
        
        assert manager.total_slides == 10
        assert manager.current_slide == 0
        assert len(manager.transcript_history) == 0
    
    @pytest.mark.asyncio
    async def test_initialization_default_total_slides(self):
        """Test that StateManager defaults to 0 slides when not specified."""
        manager = StateManager()
        
        assert manager.total_slides == 0
        assert manager.current_slide == 0
    
    @pytest.mark.asyncio
    async def test_session_metadata_initialized(self):
        """Test that session metadata is initialized with started_at timestamp."""
        manager = StateManager()
        
        assert "started_at" in manager.session_metadata
        assert "session_id" in manager.session_metadata
        assert manager.session_metadata["session_id"] is None
        assert isinstance(manager.session_metadata["started_at"], datetime)


# =============================================================================
# Slide Navigation Tests
# =============================================================================


class TestSlideNavigation:
    """Tests for slide navigation functionality."""
    
    @pytest.mark.asyncio
    async def test_set_and_get_current_slide(self, state_manager):
        """Test setting and getting current slide."""
        await state_manager.set_current_slide(5)
        current = await state_manager.get_current_slide()
        
        assert current == 5
    
    @pytest.mark.asyncio
    async def test_set_current_slide_negative_clamped(self, state_manager):
        """Test that negative slide index is clamped to 0."""
        await state_manager.set_current_slide(-5)
        current = await state_manager.get_current_slide()
        
        assert current == 0
    
    @pytest.mark.asyncio
    async def test_navigate_next(self, state_manager):
        """Test navigating to next slide."""
        await state_manager.set_current_slide(5)
        new_index = await state_manager.navigate("next")
        
        assert new_index == 6
        assert await state_manager.get_current_slide() == 6
    
    @pytest.mark.asyncio
    async def test_navigate_prev(self, state_manager):
        """Test navigating to previous slide."""
        await state_manager.set_current_slide(5)
        new_index = await state_manager.navigate("prev")
        
        assert new_index == 4
        assert await state_manager.get_current_slide() == 4
    
    @pytest.mark.asyncio
    async def test_navigate_jump(self, state_manager):
        """Test jumping to specific slide."""
        new_index = await state_manager.navigate("jump", index=7)
        
        assert new_index == 7
        assert await state_manager.get_current_slide() == 7
    
    @pytest.mark.asyncio
    async def test_navigate_jump_requires_index(self, state_manager):
        """Test that jump navigation requires an index."""
        with pytest.raises(ValueError, match="Index required"):
            await state_manager.navigate("jump")
    
    @pytest.mark.asyncio
    async def test_navigate_invalid_direction(self, state_manager):
        """Test that invalid direction raises error."""
        with pytest.raises(ValueError, match="Invalid direction"):
            await state_manager.navigate("sideways")
    
    @pytest.mark.asyncio
    async def test_navigate_next_at_last_slide(self, state_manager):
        """Test that navigating next at last slide stays at last slide."""
        await state_manager.set_current_slide(9)  # Last slide (0-indexed)
        new_index = await state_manager.navigate("next")
        
        assert new_index == 9  # Should stay at last slide
    
    @pytest.mark.asyncio
    async def test_navigate_prev_at_first_slide(self, state_manager):
        """Test that navigating prev at first slide stays at first slide."""
        await state_manager.set_current_slide(0)
        new_index = await state_manager.navigate("prev")
        
        assert new_index == 0  # Should stay at first slide
    
    @pytest.mark.asyncio
    async def test_navigate_jump_clamped_to_bounds(self, state_manager):
        """Test that jump is clamped to slide bounds."""
        # Jump beyond total slides
        new_index = await state_manager.navigate("jump", index=100)
        assert new_index == 9  # Clamped to last slide
        
        # Jump to negative
        new_index = await state_manager.navigate("jump", index=-5)
        assert new_index == 0  # Clamped to first slide
    
    @pytest.mark.asyncio
    async def test_navigate_next_with_unknown_total(self):
        """Test navigating next when total_slides is unknown (0)."""
        manager = StateManager(total_slides=0)
        await manager.set_current_slide(5)
        
        new_index = await manager.navigate("next")
        
        # Should allow going beyond when total is unknown
        assert new_index == 6


# =============================================================================
# Total Slides Tests
# =============================================================================


class TestTotalSlides:
    """Tests for total slides management."""
    
    @pytest.mark.asyncio
    async def test_set_and_get_total_slides(self, state_manager):
        """Test setting and getting total slides."""
        await state_manager.set_total_slides(20)
        total = await state_manager.get_total_slides()
        
        assert total == 20
    
    @pytest.mark.asyncio
    async def test_set_total_slides_negative_clamped(self, state_manager):
        """Test that negative total slides is clamped to 0."""
        await state_manager.set_total_slides(-5)
        total = await state_manager.get_total_slides()
        
        assert total == 0


# =============================================================================
# Transcript Tests
# =============================================================================


class TestTranscript:
    """Tests for transcript management."""
    
    @pytest.mark.asyncio
    async def test_add_transcript(self, state_manager):
        """Test adding transcript entries."""
        await state_manager.add_transcript("Hello, world!")
        
        transcript = await state_manager.get_transcript()
        assert transcript == "Hello, world!"
    
    @pytest.mark.asyncio
    async def test_add_multiple_transcripts(self, state_manager):
        """Test adding multiple transcript entries."""
        await state_manager.add_transcript("First line")
        await state_manager.add_transcript("Second line")
        await state_manager.add_transcript("Third line")
        
        transcript = await state_manager.get_transcript()
        assert "First line" in transcript
        assert "Second line" in transcript
        assert "Third line" in transcript
        assert transcript == "First line\nSecond line\nThird line"
    
    @pytest.mark.asyncio
    async def test_transcript_limit(self, state_manager):
        """Test that transcript is limited to last 100 entries."""
        # Add 150 entries
        for i in range(150):
            await state_manager.add_transcript(f"Line {i}")
        
        transcript = await state_manager.get_transcript()
        lines = transcript.split('\n')
        
        # Should only have last 100 lines
        assert len(lines) == 100
        # First line should be Line 50
        assert lines[0] == "Line 50"
        # Last line should be Line 149
        assert lines[-1] == "Line 149"
    
    @pytest.mark.asyncio
    async def test_get_empty_transcript(self, state_manager):
        """Test getting transcript when empty."""
        transcript = await state_manager.get_transcript()
        assert transcript == ""


# =============================================================================
# Context Tests
# =============================================================================


class TestContext:
    """Tests for presentation context functionality."""
    
    @pytest.mark.asyncio
    async def test_get_context(self, state_manager):
        """Test getting presentation context."""
        await state_manager.set_current_slide(3)
        
        context = await state_manager.get_context()
        
        assert context["current_slide"] == 3
        assert context["total_slides"] == 10
        assert "session_metadata" in context
    
    @pytest.mark.asyncio
    async def test_context_includes_session_metadata(self, state_manager):
        """Test that context includes session metadata."""
        await state_manager.set_session_id("test-session-123")
        
        context = await state_manager.get_context()
        
        assert context["session_metadata"]["session_id"] == "test-session-123"
        assert "started_at" in context["session_metadata"]


# =============================================================================
# Session Management Tests
# =============================================================================


class TestSessionManagement:
    """Tests for session management functionality."""
    
    @pytest.mark.asyncio
    async def test_set_session_id(self, state_manager):
        """Test setting session ID."""
        await state_manager.set_session_id("abc123")
        
        context = await state_manager.get_context()
        assert context["session_metadata"]["session_id"] == "abc123"
    
    @pytest.mark.asyncio
    async def test_reset(self, state_manager):
        """Test resetting all state."""
        # Set up state
        await state_manager.set_current_slide(5)
        await state_manager.add_transcript("Test entry")
        await state_manager.set_session_id("test-session")
        
        # Reset
        await state_manager.reset()
        
        # Verify reset
        assert await state_manager.get_current_slide() == 0
        transcript = await state_manager.get_transcript()
        assert transcript == ""
        assert state_manager.session_metadata["session_id"] is None


# =============================================================================
# Concurrency Tests
# =============================================================================


class TestConcurrency:
    """Tests for concurrent access safety."""
    
    @pytest.mark.asyncio
    async def test_concurrent_navigation(self):
        """Test that state manager handles concurrent navigation safely."""
        manager = StateManager(total_slides=100)
        
        async def navigate_next():
            for _ in range(10):
                await manager.navigate("next")
                await asyncio.sleep(0.001)
        
        async def navigate_prev():
            for _ in range(5):
                await manager.navigate("prev")
                await asyncio.sleep(0.002)
        
        # Run both concurrently
        await asyncio.gather(navigate_next(), navigate_prev())
        
        # State should be consistent (exact value depends on timing)
        current = await manager.get_current_slide()
        assert 0 <= current < 100
    
    @pytest.mark.asyncio
    async def test_concurrent_transcript_and_navigation(self):
        """Test concurrent transcript and navigation operations."""
        manager = StateManager(total_slides=10)
        
        async def navigate_task():
            for _ in range(10):
                await manager.navigate("next")
                await asyncio.sleep(0.001)
        
        async def transcript_task():
            for i in range(10):
                await manager.add_transcript(f"Entry {i}")
                await asyncio.sleep(0.001)
        
        # Run tasks concurrently
        await asyncio.gather(navigate_task(), transcript_task())
        
        # Verify state is consistent
        current = await manager.get_current_slide()
        transcript = await manager.get_transcript()
        
        assert current >= 0
        assert len(transcript.split('\n')) == 10
    
    @pytest.mark.asyncio
    async def test_concurrent_reads_and_writes(self):
        """Test concurrent reads and writes don't cause issues."""
        manager = StateManager(total_slides=50)
        
        async def writer():
            for i in range(20):
                await manager.set_current_slide(i)
                await asyncio.sleep(0.001)
        
        async def reader():
            for _ in range(20):
                current = await manager.get_current_slide()
                context = await manager.get_context()
                assert context["current_slide"] == current
                await asyncio.sleep(0.001)
        
        # Run concurrently
        await asyncio.gather(writer(), reader())
