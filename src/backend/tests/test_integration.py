"""
Integration tests for Slidekick components

Tests the integration between:
- StateManager
- SlideTools  
- ToolExecutor
- AudioProcessor

These tests verify that the components work together correctly.
"""

import asyncio
import pytest

from google.genai.types import FunctionDeclaration, Schema, Type

from slidekick import (
    StateManager,
    SlideTools,
    ToolExecutor,
    WebSocketAudioProcessor,
    AudioSourceType,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def state_manager():
    """Create a StateManager for testing."""
    return StateManager(total_slides=20)


@pytest.fixture
def slide_tools(state_manager):
    """Create SlideTools with a state manager."""
    return SlideTools(state_manager)


@pytest.fixture
def tool_executor(slide_tools):
    """Create a ToolExecutor with slide tools registered."""
    executor = ToolExecutor(verbose=False)
    
    # Register navigate_slide tool
    executor.register_tool(
        "navigate_slide",
        slide_tools.navigate_slide,
        FunctionDeclaration(
            name="navigate_slide",
            description="Navigate between slides",
            parameters=Schema(
                type=Type.OBJECT,
                properties={
                    "direction": Schema(
                        type=Type.STRING,
                        enum=["next", "prev", "jump"],
                        description="Navigation direction",
                    ),
                    "index": Schema(
                        type=Type.INTEGER,
                        description="Target slide index for jump",
                    ),
                },
                required=["direction"],
            ),
        ),
    )
    
    # Register get_presentation_context tool
    executor.register_tool(
        "get_presentation_context",
        slide_tools.get_presentation_context,
        FunctionDeclaration(
            name="get_presentation_context",
            description="Get current presentation state",
        ),
    )
    
    # Register trigger_summary tool
    executor.register_tool(
        "trigger_summary",
        slide_tools.trigger_summary,
        FunctionDeclaration(
            name="trigger_summary",
            description="Trigger summary generation",
            parameters=Schema(
                type=Type.OBJECT,
                properties={
                    "conversational_context": Schema(
                        type=Type.STRING,
                        description="Context from conversation",
                    ),
                },
            ),
        ),
    )
    
    return executor


@pytest.fixture
def audio_processor():
    """Create a WebSocket audio processor for testing."""
    return WebSocketAudioProcessor(queue_maxsize=10)


# =============================================================================
# Package Import Tests
# =============================================================================


class TestPackageImports:
    """Tests that verify package imports work correctly."""
    
    def test_import_main_components(self):
        """Test importing main components from slidekick package."""
        from slidekick import (
            AudioProcessor,
            AudioSourceType,
            PyAudioProcessor,
            WebSocketAudioProcessor,
            ToolExecutor,
            StateManager,
            SlideTools,
        )
        
        # Verify they are the correct types
        assert AudioSourceType.WEBSOCKET.value == "websocket"
        assert AudioSourceType.PYAUDIO.value == "pyaudio"
    
    def test_import_exceptions(self):
        """Test importing exception classes."""
        from slidekick.exceptions import BaseSlidekickError, ToolExecutorError
        
        # Test exception hierarchy
        assert issubclass(ToolExecutorError, BaseSlidekickError)
        assert issubclass(ToolExecutorError, Exception)


# =============================================================================
# StateManager + SlideTools Integration Tests
# =============================================================================


class TestStateManagerSlideToolsIntegration:
    """Integration tests for StateManager and SlideTools."""
    
    @pytest.mark.asyncio
    async def test_slide_tools_uses_shared_state(self, state_manager, slide_tools):
        """Test that SlideTools operations update shared StateManager."""
        # Navigate via slide_tools
        result = await slide_tools.navigate_slide("jump", index=5)
        assert result["current_slide"] == 5
        
        # Verify state_manager was updated
        current = await state_manager.get_current_slide()
        assert current == 5
    
    @pytest.mark.asyncio
    async def test_state_changes_reflected_in_context(self, state_manager, slide_tools):
        """Test that state changes are reflected in presentation context."""
        # Set up some state
        await state_manager.set_current_slide(10)
        await state_manager.add_transcript("Speaker said something important")
        
        # Get context via slide_tools
        context = await slide_tools.get_presentation_context()
        
        assert context["current_slide"] == 10
        assert context["total_slides"] == 20
    
    @pytest.mark.asyncio
    async def test_navigation_workflow(self, slide_tools, state_manager):
        """Test a complete navigation workflow."""
        # Start at beginning
        assert await state_manager.get_current_slide() == 0
        
        # Navigate forward
        for i in range(5):
            result = await slide_tools.navigate_slide("next")
            assert result["success"] is True
            assert result["current_slide"] == i + 1
        
        # Verify final state
        assert await state_manager.get_current_slide() == 5
        
        # Jump to specific slide
        result = await slide_tools.navigate_slide("jump", index=15)
        assert result["current_slide"] == 15
        
        # Navigate backward
        result = await slide_tools.navigate_slide("prev")
        assert result["current_slide"] == 14


# =============================================================================
# ToolExecutor + SlideTools Integration Tests  
# =============================================================================


class TestToolExecutorSlideToolsIntegration:
    """Integration tests for ToolExecutor with SlideTools."""
    
    @pytest.mark.asyncio
    async def test_execute_navigate_via_executor(self, tool_executor, state_manager):
        """Test executing navigate_slide tool through ToolExecutor."""
        response = await tool_executor.execute_tool(
            func_name="navigate_slide",
            func_id="gemini-call-123",
            args={"direction": "jump", "index": 7}
        )
        
        assert response.response["status"] == "success"
        data = response.response["data"]
        assert data["current_slide"] == 7
        
        # Verify state was updated
        assert await state_manager.get_current_slide() == 7
    
    @pytest.mark.asyncio
    async def test_execute_get_context_via_executor(self, tool_executor, state_manager):
        """Test executing get_presentation_context through ToolExecutor."""
        # Set up some state
        await state_manager.set_current_slide(12)
        
        response = await tool_executor.execute_tool(
            func_name="get_presentation_context",
            func_id="gemini-call-456",
            args={}
        )
        
        assert response.response["status"] == "success"
        data = response.response["data"]
        assert data["current_slide"] == 12
        assert data["total_slides"] == 20
    
    @pytest.mark.asyncio
    async def test_execute_trigger_summary_via_executor(self, tool_executor):
        """Test executing trigger_summary through ToolExecutor."""
        response = await tool_executor.execute_tool(
            func_name="trigger_summary",
            func_id="gemini-call-789",
            args={"conversational_context": "The speaker discussed AI applications."}
        )
        
        assert response.response["status"] == "success"
        data = response.response["data"]
        assert data["action"] == "start_background_summary"
        assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self, tool_executor, state_manager):
        """Test executing multiple tool calls in sequence."""
        # Get initial context
        response1 = await tool_executor.execute_tool(
            func_name="get_presentation_context",
            func_id="call-1",
            args={}
        )
        assert response1.response["data"]["current_slide"] == 0
        
        # Navigate to slide 5
        response2 = await tool_executor.execute_tool(
            func_name="navigate_slide",
            func_id="call-2",
            args={"direction": "jump", "index": 5}
        )
        assert response2.response["data"]["current_slide"] == 5
        
        # Navigate next
        response3 = await tool_executor.execute_tool(
            func_name="navigate_slide",
            func_id="call-3",
            args={"direction": "next"}
        )
        assert response3.response["data"]["current_slide"] == 6
        
        # Get final context
        response4 = await tool_executor.execute_tool(
            func_name="get_presentation_context",
            func_id="call-4",
            args={}
        )
        assert response4.response["data"]["current_slide"] == 6
    
    @pytest.mark.asyncio
    async def test_tool_declarations_for_gemini(self, tool_executor):
        """Test that tool declarations are properly formatted for Gemini."""
        declarations = tool_executor.tools
        
        assert len(declarations) == 3
        
        names = [d.name for d in declarations]
        assert "navigate_slide" in names
        assert "get_presentation_context" in names
        assert "trigger_summary" in names


# =============================================================================
# AudioProcessor Integration Tests
# =============================================================================


class TestAudioProcessorIntegration:
    """Integration tests for AudioProcessor with other components."""
    
    @pytest.mark.asyncio
    async def test_audio_processor_lifecycle(self, audio_processor):
        """Test audio processor start/stop lifecycle."""
        assert audio_processor.source_type == AudioSourceType.WEBSOCKET
        assert not audio_processor.is_running
        
        await audio_processor.start()
        assert audio_processor.is_running
        
        await audio_processor.stop()
        assert not audio_processor.is_running
    
    @pytest.mark.asyncio
    async def test_audio_queue_integration(self, audio_processor):
        """Test audio queue can be used by consumers."""
        await audio_processor.start()
        
        # Simulate audio from WebSocket
        for i in range(5):
            await audio_processor.push_audio(f'audio_chunk_{i}'.encode())
        
        # Consumer reads from queue
        received = []
        for _ in range(5):
            chunk = await asyncio.wait_for(
                audio_processor.get_audio(),
                timeout=1.0
            )
            received.append(chunk)
        
        assert len(received) == 5
        assert audio_processor.chunk_count == 5
        
        await audio_processor.stop()
    
    @pytest.mark.asyncio
    async def test_concurrent_audio_and_state(self, audio_processor, state_manager, slide_tools):
        """Test concurrent audio processing and state operations."""
        await audio_processor.start()
        
        async def audio_task():
            for i in range(10):
                await audio_processor.push_audio(f'chunk_{i}'.encode())
                await asyncio.sleep(0.01)
        
        async def navigation_task():
            for i in range(5):
                await slide_tools.navigate_slide("next")
                await asyncio.sleep(0.02)
        
        await asyncio.gather(audio_task(), navigation_task())
        
        # Verify both completed
        assert audio_processor.chunk_count == 10
        current_slide = await state_manager.get_current_slide()
        assert current_slide == 5
        
        await audio_processor.stop()


# =============================================================================
# Full System Integration Tests
# =============================================================================


class TestFullSystemIntegration:
    """Full system integration tests simulating real usage."""
    
    @pytest.mark.asyncio
    async def test_simulated_presentation_session(
        self, tool_executor, state_manager, audio_processor
    ):
        """Simulate a complete presentation session."""
        await audio_processor.start()
        
        # Session start - get initial context
        response = await tool_executor.execute_tool(
            func_name="get_presentation_context",
            func_id="init",
            args={}
        )
        assert response.response["status"] == "success"
        
        # Simulate some audio (as if user is speaking)
        for i in range(3):
            await audio_processor.push_audio(b'\x00\x01' * 100)
        
        # User says "next slide" - navigate
        response = await tool_executor.execute_tool(
            func_name="navigate_slide",
            func_id="nav-1",
            args={"direction": "next"}
        )
        assert response.response["data"]["current_slide"] == 1
        
        # More audio
        for i in range(3):
            await audio_processor.push_audio(b'\x00\x02' * 100)
        
        # User says "go to slide 10"
        response = await tool_executor.execute_tool(
            func_name="navigate_slide",
            func_id="nav-2",
            args={"direction": "jump", "index": 10}
        )
        assert response.response["data"]["current_slide"] == 10
        
        # Add transcript (simulating Gemini response)
        await state_manager.add_transcript("User requested slide 10 about architecture")
        
        # User asks for summary
        response = await tool_executor.execute_tool(
            func_name="trigger_summary",
            func_id="summary-1",
            args={"conversational_context": "Discussed architecture components"}
        )
        assert response.response["status"] == "success"
        
        # Final context check
        response = await tool_executor.execute_tool(
            func_name="get_presentation_context",
            func_id="final",
            args={}
        )
        assert response.response["data"]["current_slide"] == 10
        
        # Cleanup
        await audio_processor.stop()
        
        # Verify audio was processed
        assert audio_processor.chunk_count == 6
    
    @pytest.mark.asyncio
    async def test_error_recovery(self, tool_executor, state_manager):
        """Test system handles errors gracefully."""
        # Invalid navigation
        response = await tool_executor.execute_tool(
            func_name="navigate_slide",
            func_id="bad-nav",
            args={"direction": "jump"}  # Missing index
        )
        assert response.response["status"] == "success"  # Tool returns success=False in data
        assert response.response["data"]["success"] is False
        
        # State should be unchanged
        assert await state_manager.get_current_slide() == 0
        
        # Valid navigation still works after error
        response = await tool_executor.execute_tool(
            func_name="navigate_slide",
            func_id="good-nav",
            args={"direction": "next"}
        )
        assert response.response["data"]["current_slide"] == 1
    
    @pytest.mark.asyncio
    async def test_concurrent_tool_execution(self, tool_executor, state_manager):
        """Test concurrent tool execution is handled correctly."""
        async def navigate_calls():
            for i in range(5):
                await tool_executor.execute_tool(
                    func_name="navigate_slide",
                    func_id=f"nav-{i}",
                    args={"direction": "next"}
                )
        
        async def context_calls():
            for i in range(5):
                await tool_executor.execute_tool(
                    func_name="get_presentation_context",
                    func_id=f"ctx-{i}",
                    args={}
                )
        
        await asyncio.gather(navigate_calls(), context_calls())
        
        # State should be consistent (navigated 5 times)
        current = await state_manager.get_current_slide()
        assert current == 5

