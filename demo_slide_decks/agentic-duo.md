# Slidekick
## Your A.I Presentation Companion  
**Hackathon Submission by Agentic Duo (Nick + Snehal)**

- Voice-controlled slide navigation
- Markdown → Reveal.js presentations
- Powered by **Google Gemini Live API**

---

## Who We Are: Agentic Duo

**Two builders. One goal:** keep presenters in flow with an AI companion.

- **Snehal Vartak** — Senior Data Scientist @ Trimble (data science + software engineering)
- **Uzoma “Nick” Muoh** — Data Scientist @ SketchUp (Trimble) — “your friendly neighborhood data nerd”
- We built **Slidekick** to make presentations *hands-free*, *fast*, and *natural*

---

## What is Slidekick?

Slidekick is an AI-powered presentation companion that:
- Understands natural voice commands like **“next slide”** and **“go to slide 5”**
- Uses **real-time audio streaming** to detect intent
- Navigates your Reveal.js deck automatically

**Deck format:** Markdown → Reveal.js (portable, versionable, AI-friendly)

---

## The MVP Demo Experience

**Presenter says:** “Next slide please”  
**Slidekick does:**

1. Captures mic audio (browser)
2. Streams audio to backend (WebSocket)
3. Gemini Live detects intent + calls tools
4. Reveal.js navigates slides instantly

Goal: **Polished, reliable, demo-ready voice navigation**

---

# Architecture
## High-Level System

**Voice → WebSocket → Gemini Live (intent) → Tool call → Slide navigation**

- Frontend (React + Vite) streams mic audio + plays AI audio
- Backend (FastAPI) forwards audio to Gemini Live + executes tools
- Slides served as Reveal.js, generated from Markdown (reveal-md)

---

## Frontend (React + Vite) — The Presenter Experience

Key UI modes:
- **UploadView**: drag/drop Markdown
- **PresenterView**: mic capture, transcript, AI status, slide controls
- **AudienceView**: clean, view-only

Key technical choices:
- **AudioWorklet** captures **16kHz PCM** audio
- **WebSocket** streams audio bi-directionally (audio + JSON)
- Reveal.js runs in an **iframe** (programmatic navigation)

---

## Backend (FastAPI) — The Agent Core

Core modules:
- **WebSocket Handler**: session + bidirectional streaming
- **AudioProcessor**: queues audio for Gemini
- **ToolExecutor**: registry + tool dispatch
- **SlideTools**: domain actions (e.g., `navigate_slide`)
- **StateManager**: slide index, total slides, session metadata (async-safe)

---

## Observability + Data Flow

Frontend shows the agent is working via real-time messages:
- `status` (connected / active)
- `transcript` (what Gemini heard)
- `intent_detected` (tool chosen)
- `slide_command` (result → triggers navigation)

Data flow:
1) capture audio → 2) stream → 3) Gemini intent → 4) tool executes → 5) UI updates + slide moves

---

# Explanation
## Reactive Agent (Why It’s Fast)

Slidekick uses a **reactive agent model**:
- No explicit “planning” phase
- Gemini Live does **speech-to-intent** directly
- Commands are **atomic** (navigation is one tool call)
- Minimal memory: mostly **slide position**

Result: low-latency, presenter-friendly behavior.

---

## End-to-End Workflow (When user says “Next slide please”)

1. **Capture**: AudioWorklet records 16kHz PCM
2. **Stream**: WebSocket sends ~100ms chunks to backend
3. **Queue/Forward**: backend packages audio for Gemini Live
4. **Recognize**: Gemini maps speech → `tool_call(navigate_slide, {direction:"next"})`
5. **Execute**: ToolExecutor → SlideTools → StateManager
6. **Respond**: backend sends `slide_command` to frontend
7. **Navigate**: frontend calls Reveal.js next()
8. **Confirm**: Gemini speaks “Moving to the next slide”

---

## Gemini as Planner + “Personality” via System Instruction

**Gemini is the planner**:
- It decides *when* to call tools
- It distinguishes **commands** vs **presentation content**

System instruction concept (simplified):
- Execute slide commands immediately
- If presenter is just talking about the topic: **do nothing**
- If unsure: **stay silent**

This prevents interruptions during normal speaking.

---

## Tool Calling + Verification

Tool integration:
- Tools are registered with a **schema** (FunctionDeclaration)
- Gemini returns `tool_call(name, args)`
- ToolExecutor runs the async handler and returns a structured response

Verification (demo confidence):
- Run backend tests (`pytest`)
- Trace decisions by `session_id` in logs
- Be transparent about limitations (network latency, noise, English-first)
