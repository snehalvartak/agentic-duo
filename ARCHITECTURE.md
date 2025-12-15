# Architecture Overview

Slidekick is a voice-controlled presentation companion powered by Google's Gemini Live API. It enables hands-free slide navigation through real-time audio streaming and natural language understanding.

## High-Level Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                                    SLIDEKICK                                       │
├────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                    │
│  ┌─────────────────────────┐         ┌─────────────────────────────────────────┐   │
│  │      FRONTEND           │         │              BACKEND                    │   │
│  │    (React + Vite)       │◄───────►│          (FastAPI + Python)             │   │
│  │                         │WebSocket│                                         │   │
│  │  ┌───────────────────┐  │         │  ┌─────────────────────────────────┐    │   │
│  │  │  PresenterView    │  │  Audio  │  │     WebSocket Handler           │    │   │
│  │  │  • Mic capture    │──┼────────►│  │     (Bidirectional Stream)      │    │   │
│  │  │  • Audio playback │◄─┼─────────│  │                                 │    │   │
│  │  │  • Slide iframe   │  │  JSON   │  │  ┌───────────────────────────┐  │    │   │
│  │  │  • Reveal.js API  │◄─┼─────────│  │  │   AudioProcessor          │  │    │   │
│  │  └───────────────────┘  │         │  │  │   (16kHz PCM → Queue)     │  │    │   │
│  │                         │         │  │  └───────────┬───────────────┘  │    │   │
│  │  ┌───────────────────┐  │         │  │              │                  │    │   │
│  │  │  AudienceView     │  │         │  │  ┌───────────▼───────────────┐  │    │   │
│  │  │  (View-only mode) │  │         │  │  │     Gemini Live API       │  │    │   │
│  │  └───────────────────┘  │         │  │  │  (Real-time STT + Intent) │  │    │   │
│  │                         │         │  │  └───────────┬───────────────┘  │    │   │
│  │  ┌───────────────────┐  │         │  │              │ Tool Calls       │    │   │
│  │  │  UploadView       │  │  POST   │  │  ┌───────────▼───────────────┐  │    │   │
│  │  │  (MD → Reveal.js) │──┼────────►│  │  │     ToolExecutor          │  │    │   │
│  │  └───────────────────┘  │ /upload │  │  │  (Registry + Execution)   │  │    │   │
│  │                         │         │  │  └───────────┬───────────────┘  │    │   │
│  └─────────────────────────┘         │  │              │                  │    │   │
│                                      │  │  ┌───────────▼───────────────┐  │    │   │
│                                      │  │  │     SlideTools            │  │    │   │
│                                      │  │  │  • navigate_slide()       │  │    │   │
│                                      │  │  │  • trigger_summary()      │  │    │   │
│                                      │  │  │  • inject_summary()       │  │    │   │
│                                      │  │  └───────────┬───────────────┘  │    │   │
│                                      │  │              │                  │    │   │
│                                      │  │  ┌───────────▼───────────────┐  │    │   │
│                                      │  │  │     StateManager          │  │    │   │
│                                      │  │  │  • current_slide          │  │    │   │
│                                      │  │  │  • transcript_history     │  │    │   │
│                                      │  │  └───────────┬───────────────┘  │    │   │
│                                      │  │              │ (context)        │    │   │
│                                      │  │  ┌───────────▼───────────────┐  │    │   │
│                                      │  │  │    ContentProcessor       │  │    │   │
│                                      │  │  │  • process_slides()       │  │    │   │
│                                      │  │  │  • generate_summary()     │  │    │   │
│                                      │  │  └───────────┬───────────────┘  │    │   │
│                                      │  └──────────────┼──────────────────┘    │   │
│                                      │                 │                       │   │
│                                      │  ┌──────────────▼──────────────────┐    │   │
│                                      │  │    reveal-md (npx)              │    │   │
│                                      │  │    (Markdown → Static HTML)     │    │   │
│                                      │  └─────────────────────────────────┘    │   │
│                                      └─────────────────────────────────────────┘   │
│                                                                                    │
└──────────────────────────────────────────────────┬─────────────────────────────────┘
                                                   │
                                     ┌─────────────┼────────────────────────────┐
                                     ▼             ▼                            ▼
                 ┌─────────────────────────────┐ ┌────────────────────────┐ ┌───────────────┐
                 │   Google Gemini Live API    │ │  gemini-2.0-flash-exp  │ │ Static Files  │
                 │   gemini-2.5-flash-native-  │ │  (Summary Gen)         │ │ (Generated)   │
                 │   audio-preview             │ └────────────────────────┘ └───────────────┘
                 └─────────────────────────────┘
```

## Components

### 1. User Interface (Frontend)

**Technology:** React 18 + TypeScript + Vite + Framer Motion

The frontend provides a polished, multi-view interface:

| View | Purpose |
|------|---------|
| **UploadView** | Drag-and-drop Markdown file upload |
| **ProcessingView** | Animated progress during MD → Reveal.js conversion |
| **ReadyView** | Mode selection (Presenter vs Audience) |
| **PresenterView** | Full dashboard with voice control, live transcript, AI status, and slide navigation |
| **AudienceView** | Clean, view-only slide display |

**Key Features:**
- **AudioWorklet-based capture:** Browser captures 16kHz PCM audio via Web Audio API
- **Real-time WebSocket streaming:** Audio bytes sent directly to backend
- **Reveal.js integration:** Iframe embeds generated slides with API access for programmatic navigation
- **Bidirectional communication:** Streams audio to Gemini and receives live audio, transcripts, and function calls in return

### 2. Agent Core (Backend)

**Technology:** FastAPI + Python 3.11+ + Google GenAI SDK

The agent core orchestrates the voice-to-action pipeline:

#### **AudioProcessor** (`audio_processor.py`)
- Abstract base class with two implementations:
  - `PyAudioProcessor`: Local microphone capture (for CLI/testing)
  - `WebSocketAudioProcessor`: Receives audio from browser WebSocket
- Unified queue-based interface for audio streaming
- Configures 16kHz, 16-bit, mono PCM format (Gemini requirement)

#### **ContentProcessor** (`content_processor.py`)
- Independent processing unit using `gemini-2.0-flash-exp` (static model)
- Responsibilities:
  - `process_slides()`:  Generating initial content summaries from markdown files
  - `generate_presentation_summary()`: Synthesizing live transcript + slide content into a summary slide
- Runs in background threads to avoid blocking real-time audio handling

#### **ToolExecutor** (`tool_executor.py`)
- Registry-based tool management system
- Registers Python async functions with Gemini `FunctionDeclaration` schemas
- Executes tools when Gemini returns `tool_call` responses
- Returns structured `FunctionResponse` objects to continue the conversation

#### **StateManager** (`state_manager.py`)
- Tracks presentation state (current slide, total slides)
- Async-safe with `asyncio.Lock` for concurrent access
- Syncs with frontend via WebSocket messages (`slide_info`, `slide_sync`)
- Maintains session metadata (start time, session ID)

#### **SlideTools** (`slide_tools.py`)
- Domain-specific tools for presentation control:
  - `navigate_slide(direction, index)`: Move next/prev or jump to specific slide
  - `trigger_summary(conversational_context)`: Initiates background summary generation
  - `inject_summary(summary_text)`: Generates HTML for dynamic summary slides
- Designed for extensibility (future: `inject_image`)

### 3. Tools / APIs

| Tool/API | Purpose |
|----------|---------|
| **Google Gemini Live API** | Real-time bidirectional audio streaming with function calling |
| **Google Gemini Flash 2.0 (`gemini-2.0-flash-exp`)** | High-speed static model for generating presentation summaries |
| **reveal-md** | Converts Markdown to Reveal.js static sites |
| **Reveal.js** | Programmatic slide navigation in browser |
| **FastAPI StaticFiles** | Serves generated presentations |

#### Agent Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `navigate_slide` | `direction`: "next" \| "prev" \| "jump"<br>`index`: slide number (1-based, required for "jump") | Move to next/previous slide or jump to a specific slide number |
| `trigger_summary` | `conversational_context`: detailed summary of speaker's points | Triggers background task to generate and inject a summary slide |

*Future tools (not yet registered):* `inject_image`

### 4. Observability

#### How Does the User Know the Agent is Working?

The frontend provides real-time visual feedback through WebSocket messages sent from the backend:

| Message Type | When Sent | UI Effect |
|--------------|-----------|-----------|
| `status` | Gemini connects | Shows "Voice control active" |
| `transcript` | Gemini transcribes speech | Displays live text in transcript panel |
| `intent_detected` | Tool call received from Gemini | Shows detected command (e.g., `navigate_slide`) |
| `slide_command` | After navigation executes | Updates slide counter, triggers Reveal.js |

**Example:** When the user says "next slide", the frontend receives this sequence:
```json
{"type": "transcript", "text": "Next slide please"}
{"type": "intent_detected", "tool": "navigate_slide", "args": {"direction": "next"}}
{"type": "slide_command", "action": "next", "slide_index": 1, "status": "success"}
```

#### Frontend ↔ Backend Communication

**Frontend → Backend** (JSON messages):
| Message | Purpose | Example |
|---------|---------|---------|
| `slide_info` | Report total slides on load | `{"type": "slide_info", "total_slides": 10, "current_slide": 0}` |
| `slide_sync` | Sync position after manual navigation | `{"type": "slide_sync", "current_slide": 3}` |
| Audio bytes | Raw PCM audio from microphone | Binary data (16kHz, mono) |

**Backend → Frontend** (JSON + binary):
| Message | Purpose |
|---------|---------|
| `status` | Connection state changes |
| `transcript` | Gemini's speech transcription |
| `intent_detected` | Tool call detected (before execution) |
| `slide_command` | Navigation result (triggers UI update) |
| `inject_summary` | Summary generated and ready to inject (triggers slide update) |
| Audio bytes | Gemini's spoken response (24kHz PCM) |

#### What Gets Logged and Why?

We log **agent decisions and state transitions**, not raw data:

| What We Log | Why | Example |
|-------------|-----|---------|
| Session lifecycle | Debug connection issues | `WebSocket connected (session_id: 12345)` |
| Slide state sync | Verify frontend-backend sync | `Slide info: 1/10` |
| Tool calls | Trace agent decisions | `Executing: navigate_slide(args={"direction": "next"})` |
| Tool results | Confirm execution | `✓ next -> Slide 2` |
| Gemini responses | Debug intent recognition | `Gemini: "Moving to the next slide..."` |

**What we don't log:** Raw audio bytes (too verbose), every queue operation (noise), successful routine operations at DEBUG level only.

**Session tracing:** Every log entry includes `session_id` so you can filter logs for a specific presenter session:
```
2025-01-15 14:32:01 [INFO    ] {main.py:376} :: Tool call detected (session_id: 140234567890)
2025-01-15 14:32:01 [INFO    ] {main.py:384} :: Executing: navigate_slide(args={"direction": "next"}) (session_id: 140234567890)
```

#### Error Handling
- **WebSocket disconnects:** Gracefully detected, logged, and resources cleaned up
- **Tool failures:** Wrapped in try/catch, return structured `FunctionResponse` with error details back to Gemini
- **Gemini errors:** Connection failures sent to frontend as `status` message
- **Audio overflow:** Queue drops oldest chunks to prevent memory issues (logged as warning)

> See [EXPLANATION.md](EXPLANATION.md) for testing instructions and how to trace agent decisions.

## Data Flow (Summary)

```
User speaks → Browser captures audio → WebSocket streams to Backend
                                              │
                                              ▼
                              Gemini Live API (intent recognition)
                                              │
                                              ▼
                              Tool execution ─┬─► Sync: Frontend navigation
                                              │
                                              └─► Async: Background Task (Summary)
```

1. **Capture:** Browser records audio via AudioWorklet, streams over WebSocket
2. **Process:** Backend queues audio, forwards to Gemini Live API
3. **Decide:** Gemini recognizes intent, returns `tool_call` if command detected
4. **Execute:** ToolExecutor runs the tool.
   - *Sync:* Updates state immediately (e.g., navigation).
   - *Async:* Spawns background task (e.g., summary generation) and returns immediately to keep voice loop active.
5. **Respond:** Frontend receives command (slide change or injection event); Gemini speaks confirmation.

> See [EXPLANATION.md](EXPLANATION.md) for detailed step-by-step agent workflow.

## Why This Architecture?

### Markdown-First: Open, Portable, AI-Friendly

We chose Markdown as the presentation format for several compelling reasons:

- **No vendor lock-in:** Unlike Google Slides or PowerPoint, Markdown is plain text. Your presentations live in `.md` files you own forever.
- **Use any editor:** Write slides in VS Code, Obsidian, Notion, vim—whatever you prefer. No special software required.
- **AI can understand it:** Because Markdown is human-readable text, the AI can easily parse slide content for context-aware responses. Proprietary binary formats would require complex parsing.
- **Quick to learn:** Markdown syntax takes minutes to learn. A `#` for titles, `-` for bullets, `---` to separate slides. That's it.
- **Beautiful output:** reveal-md transforms simple Markdown into polished Reveal.js presentations with themes, transitions, and animations.

```markdown
# My Talk Title
---
## Slide 2
- Point one
- Point two
---
## Slide 3
![image](photo.jpg)
```
↓ becomes a professional HTML presentation.

### Real-Time Communication

| Choice | Why |
|--------|-----|
| **WebSocket** | Bidirectional streaming for audio + commands (REST can't do this) |
| **AudioWorklet** | Captures mic audio without blocking the UI thread |
| **Iframe for slides** | Isolates Reveal.js; enables programmatic control via `contentWindow.Reveal` |

### Clean Agent Design

| Choice | Why |
|--------|-----|
| **Tool Registry** | Add new tools without touching WebSocket handler code |
| **StateManager** | Single async-safe source of truth for slide position |
| **Separation of concerns** | `AudioProcessor` handles audio, `SlideTools` handles navigation, `ToolExecutor` handles Gemini integration |

## Extensibility Points

The architecture is designed for future enhancements:

- **`inject_image` tool:** Call Imagen API to generate and insert images on slides
- **Multi-presenter support:** StateManager can be extended for collaborative sessions
- **Persistence:** Add database backing to StateManager for session recovery
