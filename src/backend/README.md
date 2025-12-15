# Slidekick Backend

FastAPI backend for  **Slidekick** - Your A.I Presentation Companion

## Summary

The Slidekick backend provides a WebSocket-based API that processes real-time audio streams using the Gemini Live API. It handles voice commands for slide navigation, converts markdown files to Reveal.js presentations, and serves static presentation files. The backend integrates with Gemini's tool calling capabilities to execute commands like navigating slides, generating content, and managing presentation state.

## Features

- WebSocket endpoint for real-time audio streaming
- Gemini Live API integration for voice processing
- Tool calling for slide navigation and presentation control
- Markdown to Reveal.js presentation conversion
- Static file serving for generated presentations
- Audio response forwarding

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ (for reveal-md)
- [uv](https://docs.astral.sh/uv/) package manager
- Gemini API key

### Installation

```bash
# Create virtual environment and install Python dependencies
uv sync

# Install Node.js dependencies for reveal-md
npm install
```

> Note: When using `uv run`, you don't need to activate the virtual environment manually. The `uv run` command automatically uses the project's virtual environment.

### Environment Variables

1. Copy the `.env.example` file to create your own `.env` file:
   ```bash
   cp .env.example .env
   ```

2. Open the newly created `.env` file and update it with your valid Gemini API key:
   ```bash
   GEMINI_API_KEY="your-api-key-here"
   ```

### Running the Server

```bash
# Recommended: Using uv run (automatically uses the virtual environment)
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Alternative: If you prefer to activate the virtual environment manually
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```