"""
Slide Deck Voice Client

Integrates all Phase 1 and Phase 2 components:
- AudioProcessor (Phase 1)
- ToolExecutor (Phase 1)
- StateManager (Phase 2)
- SlideTools (Phase 2)
- Gemini Live API

Allows interactive voice control of the simulated slide deck.
"""

import asyncio
import os
import sys
import json
from datetime import datetime
from google import genai
from google.genai.types import FunctionDeclaration, Schema, Type

# Import modular components
from slidekick.audio_processor import AudioProcessor
from slidekick.tool_executor import ToolExecutor
from slidekick.state_manager import StateManager
from slidekick.slide_tools import SlideTools
import slidekick.config as config


client = genai.Client(api_key=config.GEMINI_API_KEY)

# Configuration
MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
SHOW_THINKING_LOGS = os.getenv("SHOW_THINKING_LOGS", "0").lower() in ("1", "true", "yes")
EXECUTION_LOG = "execution.log"

# UI/Print helpers
print_queue = asyncio.Queue()

def log_to_file(message: str):
    """Write a message to the execution log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(EXECUTION_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

async def safe_print(message: str, file=sys.stdout, flush: bool = True):
    """Queue print message."""
    await print_queue.put((message, file, flush))

async def print_queue_consumer():
    """Consume and print messages."""
    try:
        while True:
            message, file, flush = await print_queue.get()
            print(message, file=file, flush=flush)
            print_queue.task_done()
    except asyncio.CancelledError:
        pass

# ============================================================================
# Main Logic
# ============================================================================

# ...
SYSTEM_INSTRUCTION = """You are an AI presentation assistant controlling a slide deck.

Your goal is to help the presenter by navigating slides, adding content, and executing commands in real-time.

AVAILABLE TOOLS:
1. `navigate_slide(direction, index)`: Move next/prev or jump to slide. NOTE: index is 0-based (Slide 1 = index 0).
2. `add_content(content)`: Add text/bullets to current slide.
3. `inject_image(prompt)`: Generate an image for the slide.
4. `generate_summary()`: Summarize the talk so far.
5. `get_presentation_context()`: Check current slide # and status.

RULES:
- Execute commands immediately when asked.
- If the user just talks about the topic, DO NOT call tools. Only call tools for COMMANDS (e.g. "Next slide", "Add that point", "Show me a picture").
- If unsure, do nothing (don't interrupt the flow).
"""

async def send_realtime(session, audio_processor: AudioProcessor):
    """Stream audio to Gemini."""
    try:
        audio_queue = audio_processor.get_audio_queue()
        while True:
            try:
                msg = await audio_queue.get()
                await session.send_realtime_input(audio=msg)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                # If connection is closed/error 1011, stop trying to send
                if "1011" in str(e) or "closed" in str(e).lower():
                    print(f"Connection closed (send_realtime): {e}", file=sys.stderr)
                    break
                print(f"Error sending audio: {e}", file=sys.stderr)
                await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        pass

async def handle_responses(session, tool_executor: ToolExecutor):
    """Handle Gemini responses and tool calls."""
    try:
        while True:
            try:
                turn = session.receive()
                async for response in turn:
                    if hasattr(response, 'tool_call') and response.tool_call:
                        await safe_print("\n[TOOL_CALL DETECTED]")
                        
                        function_responses = []
                        if hasattr(response.tool_call, 'function_calls'):
                            for fc in response.tool_call.function_calls:
                                name = fc.name
                                args = dict(fc.args) if hasattr(fc, 'args') and fc.args else {}
                                
                                await safe_print(f"  > Executing: {name}({json.dumps(args)})")
                                log_to_file(f"Executing: {name} args={args}")
                                
                                # Execute
                                result = await tool_executor.execute_tool(name, fc.id, args)
                                function_responses.append(result)
                                
                                # Pretty print result
                                try:
                                    res_data = result.response.get("data", {})
                                    if name == "navigate_slide":
                                        # Show human-readable slide number (1-based)
                                        slide_idx = res_data.get('current_slide', 0)
                                        await safe_print(f"  ✓ Navigated to Slide {slide_idx + 1}")
                                    elif name == "add_content":
                                        await safe_print(f"  ✓ Added content: '{res_data.get('content')}'")
                                except Exception:
                                    pass

                        if function_responses:
                            await session.send_tool_response(function_responses=function_responses)

                    # Thinking logs
                    if SHOW_THINKING_LOGS and response.server_content and response.server_content.model_turn:
                        for part in response.server_content.model_turn.parts:
                            if hasattr(part, 'text') and part.text:
                                text = part.text.strip()
                                if text:
                                    await safe_print(f"\n[THINKING] {text}")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                # If connection is closed/error 1011, stop trying to send
                if "1011" in str(e) or "closed" in str(e).lower():
                    print(f"Connection closed (handle_responses): {e}", file=sys.stderr)
                    break 
                print(f"Error in handle_responses: {e}", file=sys.stderr)
                await asyncio.sleep(0.1)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Fatal error in handle_responses: {e}", file=sys.stderr)

async def run():
    """Main application loop."""
    print("Initializing Agentic Slide Deck Client...")
    
    # 1. Initialize Components
    audio = AudioProcessor.from_pyaudio()  # Use factory method for local microphone
    state = StateManager(total_slides=10) # Simulating 10 slides
    tools = SlideTools(state)
    executor = ToolExecutor(verbose=False)
    
    # ...
    
    # WRAPPERS for 1-based indexing (LLM Friendly)
    async def navigate_slide_wrapper(direction: str, index: int | None = None):
        """Wrapper to convert 1-based LLM index to 0-based backend index."""
        if direction == "jump" and index is not None:
            # Convert 1-based (User/LLM) to 0-based (Backend)
            backend_index = index - 1
            if backend_index < 0:
                backend_index = 0
            return await tools.navigate_slide(direction, backend_index)
        return await tools.navigate_slide(direction, index)

    # 2. Register Phase 2 Tools with Schemas
    executor.register_tool(
        "navigate_slide", 
        navigate_slide_wrapper, # Use wrapper
        FunctionDeclaration(
            name="navigate_slide",
            description="Move to next/prev slide or jump to specific index.",
            parameters=Schema(
                type=Type.OBJECT,
                properties={
                    "direction": Schema(
                        type=Type.STRING, 
                        enum=["next", "prev", "jump"],
                        description="Direction to navigate: 'next', 'prev', or 'jump'"
                    ),
                    "index": Schema(
                        type=Type.INTEGER,
                        description="Target slide number (1-based, e.g. Slide 1 = 1). Required if direction is 'jump'."
                    )
                },
                required=["direction"]
            )
        )
    )
    
    executor.register_tool(
        "add_content", 
        tools.add_content,
        FunctionDeclaration(
            name="add_content",
            description="Add text content or bullet point to current slide.",
            parameters=Schema(
                type=Type.OBJECT,
                properties={
                    "content": Schema(
                        type=Type.STRING,
                        description="The text content or bullet point to add."
                    ),
                    "target_placeholder": Schema(
                        type=Type.STRING,
                        description="Optional placeholder ID (default AI:CONTENT)"
                    )
                },
                required=["content"]
            )
        )
    )
    
    executor.register_tool(
        "inject_image", 
        tools.inject_image,
        FunctionDeclaration(
            name="inject_image",
            description="Generate and inject an image into the slide.",
            parameters=Schema(
                type=Type.OBJECT,
                properties={
                    "prompt": Schema(
                        type=Type.STRING,
                        description="Description of the image to generate"
                    )
                },
                required=["prompt"]
            )
        )
    )
    
    executor.register_tool(
        "generate_summary", 
        tools.generate_summary,
        FunctionDeclaration(
            name="generate_summary",
            description="Generate a summary of the presentation so far based on transcript."
        )
    )
    
    executor.register_tool(
        "get_presentation_context", 
        tools.get_presentation_context,
        FunctionDeclaration(
            name="get_presentation_context",
            description="Get current slide index, total slides, and session context."
        )
    )
    
    # 3. Configure Gemini
    # Update system instruction to reflect 1-based indexing
    UPDATED_SYSTEM_INSTRUCTION = SYSTEM_INSTRUCTION.replace(
        "index is 0-based (Slide 1 = index 0)", 
        "index is 1-BASED (Slide 1 = index 1)"
    )
    
    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": UPDATED_SYSTEM_INSTRUCTION,
        "tools": [{"function_declarations": executor.get_tool_declarations()}],
    }
    
    # 4. Connect
    async with client.aio.live.connect(model=MODEL, config=config) as session:
        print("="*60)
        print("🎤 Voice Control Active")
        print("="*60)
        print("Say commands like:")
        print("  - 'Next slide'")
        print("  - 'Jump to slide 5'")
        print("  - 'Add a bullet point about architecture'")
        print("  - 'Summarize this'")
        print("\n(Press Ctrl+C to quit)\n")
        
        await audio.start_capture()
        
        async with asyncio.TaskGroup() as tg:
            tg.create_task(send_realtime(session, audio))
            tg.create_task(handle_responses(session, executor))
            tg.create_task(print_queue_consumer())

def main():
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    main()
