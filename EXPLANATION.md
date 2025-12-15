# Technical Explanation

This document explains how Slidekick's AI agent works, how it integrates with Google Gemini, and how to verify its behavior. For system architecture and component details, see [ARCHITECTURE.md](ARCHITECTURE.md).

## 1. Agent Workflow

Slidekick uses a **reactive agent model** rather than traditional planning patterns like ReAct or BabyAGI. Here's why this matters:

| Traditional Agent | Slidekick's Reactive Agent |
|-------------------|----------------------------|
| Receives discrete input, plans steps, executes | Continuously listens to audio stream |
| Explicit planning phase | Gemini Live API handles intent recognition implicitly |
| Multi-step task decomposition | Single-command execution (navigation is atomic) |
| Memory retrieval before action | Minimal state (just slide position) |

### Detailed Step-by-Step Flow

When the presenter says "Next slide please":

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. CAPTURE                                                                  │
│    Browser's AudioWorklet captures 16kHz PCM audio from microphone          │
│    └── Runs in separate thread, non-blocking                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. STREAM                                                                   │
│    WebSocket sends raw audio bytes to FastAPI backend                       │
│    └── Binary frames, ~100ms chunks                                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 3. QUEUE                                                                    │
│    WebSocketAudioProcessor packages audio into Gemini-compatible format     │
│    └── {"data": bytes, "mime_type": "audio/pcm"}                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 4. FORWARD                                                                  │
│    Audio chunks sent to Gemini Live API session via send_realtime_input()   │
│    └── Gemini processes audio in real-time, no batching                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 5. RECOGNIZE                                                                │
│    Gemini Live API performs speech-to-intent:                               │
│    └── "Next slide please" → tool_call(navigate_slide, {direction: "next"}) │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 6. EXECUTE                                                                  │
│    ToolExecutor receives function call, dispatches to SlideTools            │
│    └── SlideTools.navigate_slide() updates StateManager                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 7. RESPOND                                                                  │
│    Backend sends slide_command to frontend via WebSocket                    │
│    └── {"type": "slide_command", "action": "next", "slide_index": 1}        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 8. NAVIGATE                                                                 │
│    Frontend calls Reveal.next() to advance the slide                        │
│    └── User sees slide change immediately                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 9. CONFIRM                                                                  │
│    Gemini sends audio response: "Moving to the next slide"                  │
│    └── Played through browser speakers (24kHz PCM)                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key insight:** Steps 4-6 happen inside Gemini's processing. There's no explicit "planning" step—Gemini's model directly maps speech to function calls based on the system instruction.
    
### Summary Generation Workflow (Async Pattern)

When the user says "Summarize what I've said so far":

```
┌───────────────────────────┐         ┌──────────────────────────────────────────────┐
│  Gemini Live API          │         │  Backend (FastAPI)                           │
│  (Planner)                │         │  (Coordinator)                               │
│                           │         │                                              │
│  1. Detects "summarize"   │         │                                              │
│  2. Calls trigger_summary │────────►│  1. Receives tool call                       │
│     (context="...")       │         │  2. Returns "started" immediately            │
│                           │◄────────│     (Non-blocking)                           │
└───────────────────────────┘         │                                              │
            ▲                         │  3. Spawns Background Task                   │
            │                         │     │                                        │
            │                         │     ▼                                        │
┌───────────────────────────┐         │  ┌─────────────────────────────────────┐     │
│  Frontend (React)         │         │  │ ContentProcessor                    │     │
│                           │         │  │ (using gemini-2.0-flash-exp)        │     │
│  1. Receives "Summary     │◄──JSON──│  │ 1. Fetches full transcript          │     │
│     ready" event          │         │  │ 2. Synthesizes with slide context   │     │
│  2. Renders new slide     │         │  │ 3. Generates HTML summary slide     │     │
└───────────────────────────┘         └──────────────────────────────────────────────┘
```

This **two-model architecture** avoids blocking the real-time voice loop. The lightweight `trigger_summary` tool hands off the heavy lifting to a background process using a stronger static model (`gemini-2.0-flash-exp`).

## 2. Key Modules


Mapping Slidekick's modules to agentic roles (see [ARCHITECTURE.md](ARCHITECTURE.md) for implementation details):

| Agentic Role | Module           | Responsibility                                 |
|--------------|------------------|------------------------------------------------|
| **Planner**  | Gemini Live API  | Listens to audio, recognizes intent, decides when to call tools |
| **Executor** | ToolExecutor     | Receives function calls from Gemini, dispatches to handlers |
| **Memory**   | StateManager     | Tracks session state (current slide, total slides) |
| **Tools**    | SlideTools       | Domain-specific actions (navigate_slide) |

### Why Gemini is the Planner

Unlike traditional agents where you implement a planner module, Slidekick delegates planning entirely to Gemini Live API:

- **No explicit intent classification:** Gemini understands "next slide", "go to slide 5", "previous" natively
- **No NLU pipeline:** Audio → Intent happens in one model call
- **Context from system instruction:** The prompt tells Gemini when to act vs. stay silent

## 3. Innovative Gemini Integration

Slidekick leverages **Gemini Live API** (`gemini-2.5-flash-native-audio-preview`) in ways that differentiate it from typical chatbot integrations:

### Native Audio Processing

Traditional approach:
```
Audio → STT Service → Text → LLM → Response
         (latency)           (latency)
```

Slidekick's approach:
```
Audio → Gemini Live API → Function Call + Audio Response
              (single round-trip)
```

**Why this matters:** No intermediate STT step means lower latency and better accuracy for natural speech patterns.

### System Instruction (The Agent's "Personality")

The system instruction in `config.py` shapes how Gemini behaves:

```
You are an AI presentation assistant controlling a slide deck.

AVAILABLE TOOLS:
1. `navigate_slide(direction, index)`
2. `trigger_summary(conversational_context)`
...

RULES:
- Action over words! Call tools IMMEDIATELY when asked.
- When asked to "summarize":
  1. Think about what the SPEAKER has said so far.
  2. Call `trigger_summary` with a detailed summary of points.
  3. Tell the user you started the summary.
  4. Do NOT stay silent.
```

This instruction is critical—it teaches Gemini to distinguish between:
- **Commands:** "Next slide" → call `navigate_slide`
- **Complex Tasks:** "Summarize this" → call `trigger_summary` (handoff)
- **Content:** "Let me explain this chart..." → stay silent

### Bidirectional Audio

Gemini doesn't just receive audio—it responds with audio:
- Confirms actions: "Moving to slide 3"
- Handles errors gracefully: "I couldn't do that, you're already on the last slide"
- Creates a conversational UX without text overlays

## 4. Tool Integration

### How Tools Are Registered

Tools are registered with both a Python function and a Gemini `FunctionDeclaration`, here is an example of one of the registered tools:

```python
executor.register_tool(
    "navigate_slide",           # Tool name
    navigate_slide_wrapper,     # Async Python function
    FunctionDeclaration(        # Schema for Gemini
        name="navigate_slide",
        description="Move to next/prev slide or jump to specific slide number.",
        parameters=Schema(
            type=Type.OBJECT,
            properties={
                "direction": Schema(type=Type.STRING, enum=["next", "prev", "jump"]),
                "index": Schema(type=Type.INTEGER, description="1-based slide number"),
            },
            required=["direction"],
        ),
    ),
)
```

### Function Calling Flow

```
Gemini detects command
        │
        ▼
Returns tool_call with function name + args
        │
        ▼
ToolExecutor.execute_tool() looks up registered function
        │
        ▼
Calls async function with unpacked args
        │
        ▼
Returns FunctionResponse to Gemini (enables follow-up)
```

The `FunctionResponse` goes back to Gemini so it can:
- Confirm the action in its audio response
- Handle errors gracefully
- Chain multiple actions if needed (future capability)

## 5. Observability and Testing

### Running Tests

```bash
cd src/backend
uv run pytest -v
```

### Test Coverage

| Test File                          | What It Verifies                                    |
|------------------------------------|-----------------------------------------------------|
| `test_audio_processor.py`          | Audio capture, queue management, format conversion  |
| `test_state_manager.py`            | Slide navigation, state updates, async safety       |
| `test_slide_tools.py`              | Navigation tool behavior, error handling            |
| `test_tool_executor.py`            | Tool registration, execution, response generation   |
| `test_intent_client_integration.py`| End-to-end Gemini integration (requires API key)    |

### Tracing Agent Decisions

All agent decisions are logged with `session_id` for filtering. To trace a specific session:

```bash
grep "session_id: 140234567890" logs/slidekick.log
```

Example trace:
```
[INFO] WebSocket connected (session_id: 140234567890)
[INFO] Slide info: 1/10 (session_id: 140234567890)
[INFO] Tool call detected (session_id: 140234567890)
[INFO] Executing: navigate_slide(args={"direction": "next"}) (session_id: 140234567890)
[INFO] ✓ next -> Slide 2 (session_id: 140234567890)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for full logging configuration and message types.

## 6. Known Limitations

Being honest about edge cases and bottlenecks:

| Limitation | Impact | Potential Mitigation |
|------------|--------|----------------------|
| **Network latency** | Audio streaming depends on connection quality; high latency = delayed response | Optimize chunk size, add local buffering |
| **Ambient noise** | May trigger false positives or miss commands in noisy environments | Add wake word detection, noise filtering |
| **Single command at a time** | Can't chain commands ("skip three slides") | Future: parse compound commands |
| **English only** | System instruction and testing focused on English | Localize prompts, test with other languages |
| **Limited content awareness** | Agent has summary context but full detailed slide content is outside context window | Future: RAG or larger context window injection |
| **Browser-only audio** | Requires browser with Web Audio API support | Provide fallback or native app option |

## 7. Societal Impact and Novelty

### Accessibility

Slidekick enables **hands-free presentation control** for:
- Speakers who need to move freely during talks
- Anyone who wants a more natural presentation flow
- With more development, Slidekick can understand your presentation provide more assistant like adding new content or summarizing.

### Open Format

By using **Markdown** instead of proprietary formats:
- Anyone can create presentations with free tools
- Content is portable, version-controllable, and AI-readable
- No vendor lock-in to Google Slides, PowerPoint, or Keynote

### Novel Application

Slidekick is maximizes the amazing capabilities of Gemini Live API:
- Real-time audio streaming (not batch STT)
- Native function calling for control
- Bidirectional audio for conversational UX

This demonstrates a new category of agentic applications: **AI as invisible infrastructure** that augments human capabilities without demanding attention.
