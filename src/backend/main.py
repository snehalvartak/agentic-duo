"""
Agentic Slide Deck Backend

FastAPI server providing:
- WebSocket endpoint for real-time voice control via Gemini Live API
- Static file serving for Reveal.js presentations
- Markdown to Reveal.js conversion via reveal-md
"""

import asyncio
import json
import logging
import shutil
import subprocess
import tempfile
import websockets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types as genai_types

import slidekick.config as config
from slidekick import AudioProcessor, SlideTools, StateManager, ToolExecutor
from slidekick.content_processor import ContentProcessor

logger = logging.getLogger(__name__)

# Store latest summary in memory (for hackathon demo simplicity)
LATEST_SLIDE_SUMMARY = None


# =============================================================================
# Application Setup
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup/shutdown."""
    logger.info("Starting Slidekick server")

    config.SLIDES_DIR.mkdir(parents=True, exist_ok=True)

    yield

    # Cleanup on shutdown
    logger.info("Cleaning up temporary directories")
    for file in config.SLIDES_DIR.glob("reveal-md-*"):
        if file.is_dir():
            shutil.rmtree(file)
        else:
            file.unlink()


app = FastAPI(lifespan=lifespan, title="Agentic Slide Deck API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for the generated slides
app.mount("/slides", StaticFiles(directory=config.SLIDES_DIR, html=True), name="slides")


# =============================================================================
# Dependency Factories
# =============================================================================


def create_gemini_client() -> genai.Client:
    """Create a Gemini client."""
    return genai.Client(api_key=config.GEMINI_API_KEY)


def create_session_components() -> tuple[ToolExecutor, StateManager, SlideTools]:
    """
    Create session-scoped components for a WebSocket connection.
    
    Returns:
        Tuple of (executor, state_manager, slide_tools)
    """
    # Initialize state manager - total_slides will be updated by frontend
    state = StateManager(total_slides=0)
    tools = SlideTools(state)
    executor = ToolExecutor(verbose=config.VERBOSE_TOOL_LOGS)

    # Wrapper for 1-based indexing (LLM-friendly)
    async def navigate_slide_wrapper(direction: str, index: int | None = None):
        """Convert 1-based LLM index to 0-based backend index."""
        if direction == "jump" and index is not None:
            backend_index = max(0, index - 1)
            return await tools.navigate_slide(direction, backend_index)
        return await tools.navigate_slide(direction, index)

    # Register navigation tool
    executor.register_tool(
        "navigate_slide",
        navigate_slide_wrapper,
        genai_types.FunctionDeclaration(
            name="navigate_slide",
            description="Move to next/prev slide or jump to specific slide number.",
            parameters=genai_types.Schema(
                type=genai_types.Type.OBJECT,
                properties={
                    "direction": genai_types.Schema(
                        type=genai_types.Type.STRING,
                        enum=["next", "prev", "jump"],
                        description="Navigation direction: 'next', 'prev', or 'jump'",
                    ),
                    "index": genai_types.Schema(
                        type=genai_types.Type.INTEGER,
                        description="Target slide number (1-based). Required for 'jump'.",
                    ),
                },
                required=["direction"],
            ),
        ),
    )

    # Register trigger_summary tool
    executor.register_tool(
        "trigger_summary",
        tools.trigger_summary,
        genai_types.FunctionDeclaration(
            name="trigger_summary",
            description="Trigger the background generation of a presentation summary.",
            parameters=genai_types.Schema(
                type=genai_types.Type.OBJECT,
                properties={
                    "conversational_context": genai_types.Schema(
                        type=genai_types.Type.STRING,
                        description="A detailed summary of what the SPEAKER has said during the presentation so far. Be comprehensive.",
                    ),
                },
                required=["conversational_context"],
            ),
        ),
    )

    return executor, state, tools


def create_gemini_config(executor: ToolExecutor, slide_summary: str | None = None) -> genai_types.LiveConnectConfig:
    """Create Gemini Live API configuration with tools."""
    
    system_instruction = config.GEMINI_LIVE_SYSTEM_INSTRUCTION
    if slide_summary:
        system_instruction += f"\n\nCONTEXT: Slide Summary\n{slide_summary}"
        logger.info("Injected slide summary into system instruction")
        
    return genai_types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        tools=[genai_types.Tool(function_declarations=executor.tools)],
        system_instruction=system_instruction,
    )


# =============================================================================
# HTTP Endpoints
# =============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/upload")
async def upload_slides(file: UploadFile = File(...)):
    """Upload and convert markdown slides to Reveal.js format."""
    try:
        file_path = config.UPLOADS_DIR / file.filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"Saved {file.filename}, size: {file_path.stat().st_size} bytes")

        # Create temp directory for reveal-md output
        if config.USE_TEMP_DIR:
            # Create a random temporary directory
            temp_dir = tempfile.mkdtemp(prefix="reveal-md-")
        else:
            # Create a temporary directory in the slides directory (mostly for debugging purposes)
            temp_dir = tempfile.mkdtemp(dir=config.SLIDES_DIR, prefix="reveal-md-")

        # Run reveal-md to generate static site
        command = ["npx", "-y", "reveal-md", str(file_path), "--static", temp_dir]
        result = subprocess.run(command, capture_output=True, text=True, check=True)

        # Create symbolic link to mermaid in static slides
        mermaid_src = config.BASE_DIR / "node_modules" / "mermaid"
        mermaid_dest = Path(temp_dir) / "mermaid"

        if mermaid_src.exists() and not mermaid_dest.exists():
            mermaid_dest.symlink_to(mermaid_src.resolve(), target_is_directory=True)
            logger.info("Created symbolic link to mermaid")
        elif not mermaid_src.exists():
            logger.warning("mermaid node_module not found, skipping symlink")

        logger.debug(f"reveal-md stdout: \n{result.stdout}")
        if result.stderr:
            logger.debug(f"reveal-md stderr: \n{result.stderr}")

        relative_path = Path(temp_dir).name
        logger.info(f"Conversion complete: {relative_path}")
        
        # Generate AI summary of slides
        logger.info("Processing slides for AI summary...")
        try:
            processor = ContentProcessor()
            # Use the original markdown file for summary generation
            summary = await processor.process_slides(file_path) 
            
            # Store in global variable for new sessions
            global LATEST_SLIDE_SUMMARY
            LATEST_SLIDE_SUMMARY = summary
            logger.info(f"Slide summary generated ({len(summary)} chars)")
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
        
        return {"status": "success", "url": f"/slides/{relative_path}/index.html"}

    except subprocess.CalledProcessError as e:
        logger.error(f"reveal-md failed: {e.stderr}")
        return {"status": "error", "message": f"Conversion failed: {e.stderr}"}
    except Exception as e:
        logger.exception(f"Upload failed: {e}")
        return {"status": "error", "message": str(e)}


# =============================================================================
# WebSocket Endpoint
# =============================================================================


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client: Annotated[genai.Client, Depends(create_gemini_client)],
):
    """WebSocket endpoint for real-time voice control and slide navigation."""
    await websocket.accept()
    session_id = id(websocket)

    logger.info("WebSocket connected", extra={"session_id": session_id})

    # Create session-scoped components
    executor, state_manager, slide_tools = create_session_components()
    await state_manager.set_session_id(session_id)
    
    # Inject latest summary if available
    gemini_config = create_gemini_config(executor, slide_summary=LATEST_SLIDE_SUMMARY)

    # Create audio processor for WebSocket audio
    audio_processor = AudioProcessor.from_websocket()
    await audio_processor.start()

    # Shared state
    is_connected = True
    allow_interruption = asyncio.Event()
    allow_interruption.set()

    # -------------------------------------------------------------------------
    # Helper Functions
    # -------------------------------------------------------------------------

    async def safe_send_json(data: dict):
        """Safely send JSON to the WebSocket client."""
        nonlocal is_connected
        if not is_connected:
            return
        try:
            await websocket.send_json(data)
            logger.debug(f"Sent: {data.get('type', 'unknown')}", extra={"session_id": session_id})
        except Exception as e:
            logger.warning(f"Send failed: {e}", extra={"session_id": session_id})
            is_connected = False

    async def safe_send_bytes(data: bytes):
        """Safely send bytes to the WebSocket client."""
        nonlocal is_connected
        if not is_connected:
            return
        try:
            await websocket.send_bytes(data)
        except Exception as e:
            logger.warning(f"Send bytes failed: {e}", extra={"session_id": session_id})
            is_connected = False

    async def handle_frontend_message(message: dict):
        """Handle JSON messages from the frontend."""
        msg_type = message.get("type")
        
        if msg_type == "slide_info":
            # Frontend reporting slide count
            total = message.get("total_slides", 0)
            current = message.get("current_slide", 0)
            await state_manager.set_total_slides(total)
            await state_manager.set_current_slide(current)
            logger.info(f"Slide info: {current + 1}/{total}", extra={"session_id": session_id})
            
        elif msg_type == "slide_sync":
            # Frontend syncing current slide position
            current = message.get("current_slide", 0)
            await state_manager.set_current_slide(current)
            logger.debug(f"Slide synced: {current + 1}", extra={"session_id": session_id})
            
        elif msg_type == "request_summary":
            # Manual summary request from frontend
            logger.info("Manual summary requested", extra={"session_id": session_id})
            await safe_send_json({"type": "status", "message": "Generating summary..."})
            asyncio.create_task(run_background_summary(""))
            
        else:
            logger.debug(f"Unknown message type: {msg_type}", extra={"session_id": session_id})

    # -------------------------------------------------------------------------
    # WebSocket Tasks
    # -------------------------------------------------------------------------

    async def receive_websocket_data():
        """Receive data from WebSocket - handles both audio and JSON messages."""
        nonlocal is_connected
        try:
            while is_connected:
                message = await websocket.receive()
                
                if message["type"] != "websocket.receive":
                    continue

                if "bytes" in message:
                    # Audio data
                    await audio_processor.push_audio(message["bytes"])
                elif "text" in message:
                    # JSON message from frontend
                    try:
                        data = json.loads(message["text"])
                        await handle_frontend_message(data)
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON received", extra={"session_id": session_id})
                            
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected", extra={"session_id": session_id})
            is_connected = False
        except RuntimeError as e:
            if "Cannot call \"receive\" once a disconnect message has been received" in str(e):
                logger.info("WebSocket connection closed during receive", extra={"session_id": session_id})
                is_connected = False
            else:
                logger.exception(f"RuntimeError receiving data: {e}", extra={"session_id": session_id})
                is_connected = False
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(f"Error receiving data: {e}", extra={"session_id": session_id})
            is_connected = False

    async def forward_audio_to_gemini(session):
        """Forward audio from processor queue to Gemini session."""
        nonlocal is_connected
        try:
            while is_connected:
                # Wait if interruption is not allowed (e.g. during tool execution)
                if not allow_interruption.is_set():
                     logger.debug("Audio forwarding paused (Gate Closed)", extra={"session_id": session_id})
                await allow_interruption.wait()

                try:
                    audio_msg = await asyncio.wait_for(
                        audio_processor.get_audio(),
                        timeout=1.0,
                    )
                    await session.send_realtime_input(audio=audio_msg)
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            raise
        except Exception as e:
            error_str = str(e).lower()
            if "1011" in error_str or "closed" in error_str or "1008" in error_str:
                logger.info(f"Gemini connection closed: {e}", extra={"session_id": session_id})
            else:
                logger.exception(f"Audio forward error: {e}", extra={"session_id": session_id})
            is_connected = False

    async def handle_gemini_responses(session):
        """Handle responses from Gemini: audio, text, and tool calls."""
        nonlocal is_connected

        try:
            while is_connected:
                try:
                    turn = session.receive()

                    async for response in turn:
                        if not is_connected:
                            break

                        # Handle tool calls
                        if hasattr(response, "tool_call") and response.tool_call:
                            await process_tool_calls(response.tool_call)

                        # NOTE: Audio forwarding disabled - Gemini voice confirmations were distracting
                        # We keep response_modalities=["AUDIO"] to avoid WebSocket errors,
                        # but don't send the audio to the frontend
                        # if hasattr(response, "data") and response.data:
                        #     await safe_send_bytes(response.data)

                        # Log text responses and capture transcript
                        if response.server_content and response.server_content.model_turn:
                            for part in response.server_content.model_turn.parts:
                                if hasattr(part, "text") and part.text:
                                    text = part.text.strip()
                                    if text:
                                        logger.info(f"Gemini: {text[:100]}...", extra={"session_id": session_id})
                                        # Buffer transcript for summary generation
                                        await state_manager.add_transcript(text)
                                        
                                        await safe_send_json({
                                            "type": "transcript",
                                            "text": text,
                                        })

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    error_str = str(e).lower()
                    if "1011" in error_str or "closed" in error_str or "1008" in error_str:
                        logger.warning(f"Connection closed (likely interruption): {e}", extra={"session_id": session_id})
                        break
                    logger.exception(f"Response error: {e}", extra={"session_id": session_id})
                    await asyncio.sleep(0.1)
                
                # Finally block removed as we are not toggling allow_interruption here anymore

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Fatal response error: {e}", extra={"session_id": session_id})
        finally:
            is_connected = False

    async def run_background_summary(context_from_live_session: str = ""):
        """Backend task to generate and inject summary asynchronously."""
        try:
            logger.info("Starting background summary generation...", extra={"session_id": session_id})
            
            # Combine sourced transcripts. 
            # If we have live context, it's prioritized as it contains the "hearing" of the model.
            transcript_buffer = await state_manager.get_transcript()
            
            full_transcript_context = f"""
            [Live Model Memory (Speaker's Words)]:
            {context_from_live_session}
            
            [System Log (AI Responses)]:
            {transcript_buffer}
            """
            
            slide_context = LATEST_SLIDE_SUMMARY or "No slide content available."
            
            # Create a fresh processor instance
            processor = ContentProcessor()
            summary_text = await processor.generate_presentation_summary(full_transcript_context, slide_context)
            
            if not summary_text or "Error" in summary_text:
                logger.warning("Summary generation returned empty or error", extra={"session_id": session_id})
                return

            # Use slide_tools to format the injection payload
            # We call inject_summary which returns the command dict (including HTML)
            injection_result = await slide_tools.inject_summary(summary_text)
            
            if injection_result.get("success"):
                 html_content = injection_result.get("html", "")
                 logger.info("Background summary ready, injecting...", extra={"session_id": session_id})
                 
                 await safe_send_json({
                    "type": "inject_summary",
                    "html": html_content,
                    "summary": summary_text,
                })
            else:
                logger.error(f"Injection formatting failed: {injection_result.get('error')}", extra={"session_id": session_id})

        except Exception as e:
            logger.error(f"Background summary task failed: {e}", extra={"session_id": session_id})

    async def process_tool_calls(tool_call):
        """Process tool calls from Gemini."""
        # Pause audio transmission during tool execution to prevent interruptions
        allow_interruption.clear()
        
        try:
            logger.info("Tool call detected", extra={"session_id": session_id})

            function_responses = []
            if hasattr(tool_call, "function_calls"):
                for fc in tool_call.function_calls:
                    name = fc.name
                    args = dict(fc.args) if hasattr(fc, "args") and fc.args else {}

                    logger.info(f"Executing: {name}({json.dumps(args)})", extra={"session_id": session_id})

                    # Notify frontend of detected intent
                    await safe_send_json({
                        "type": "intent_detected",
                        "tool": name,
                        "args": args,
                    })

                    # Execute the tool
                    result = await executor.execute_tool(name, fc.id, args)
                    function_responses.append(result)

                    # Send result to frontend
                    try:
                        res_data = result.response.get("data", {})
                        status = result.response.get("status", "unknown")

                        if name == "navigate_slide":
                            current_slide = res_data.get("current_slide", 0)
                            direction = args.get("direction", "unknown")

                            logger.info(
                                f"✓ {direction} -> Slide {current_slide + 1}", extra={"session_id": session_id}
                            )

                            await safe_send_json({
                                "type": "slide_command",
                                "action": direction,
                                "slide_index": current_slide,
                                "status": status,
                            })
                        elif name == "trigger_summary" or res_data.get("action") == "start_background_summary":
                            logger.info(f"✓ Summary Triggered (Async)", extra={"session_id": session_id})
                            
                            # Extract context from tool args via the result data (since we passed it through)
                            context = res_data.get("conversational_context", "")
                            
                            # Launch background task with the context
                            asyncio.create_task(run_background_summary(context))
                            
                            await safe_send_json({
                                "type": "tool_result",
                                "tool": name,
                                "status": status,
                                "data": res_data,
                            })
                        else:
                            logger.info(f"✓ {name}: {status}", extra={"session_id": session_id})
                            await safe_send_json({
                                "type": "tool_result",
                                "tool": name,
                                "status": status,
                                "data": res_data,
                            })
                    except Exception as e:
                        logger.warning(f"Error processing result: {e}", extra={"session_id": session_id})

            # Send tool responses back to Gemini
            if function_responses:
                await session.send_tool_response(function_responses=function_responses)
                logger.debug(f"Sent {len(function_responses)} tool response(s)", extra={"session_id": session_id})
        
        finally:
            # Resume audio transmission
            allow_interruption.set()

    # -------------------------------------------------------------------------
    # Main Session Loop
    # -------------------------------------------------------------------------

    try:
        logger.info("Connecting to Gemini Live API...", extra={"session_id": session_id})

        async with client.aio.live.connect(
            model=config.LIVE_GEMINI_MODEL,
            config=gemini_config,
        ) as session:
            logger.info("Connected to Gemini", extra={"session_id": session_id})

            await safe_send_json({
                "type": "status",
                "status": "connected",
                "message": "Voice control active",
            })

            # Run all tasks concurrently
            async with asyncio.TaskGroup() as tg:
                tg.create_task(receive_websocket_data())
                tg.create_task(forward_audio_to_gemini(session))
                tg.create_task(handle_gemini_responses(session))

    except* WebSocketDisconnect:
        logger.info("Client disconnected", extra={"session_id": session_id})
    except* Exception as eg:
        for exc in eg.exceptions:
            logger.exception(f"Task error: {exc}", extra={"session_id": session_id})
    finally:
        is_connected = False
        await audio_processor.stop()
        
        logger.info(
            f"Session ended ({audio_processor.chunk_count} audio chunks)", extra={"session_id": session_id}
        )

        try:
            await websocket.close()
        except Exception:
            pass


# =============================================================================
# Entry Point
# =============================================================================


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
