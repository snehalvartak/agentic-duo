# Agentic Duo Backend

FastAPI backend for the Gemini Live Joke Assistant.

## Features

- WebSocket endpoint for real-time audio streaming
- Gemini Live API integration for voice processing
- Tool calling for joke detection and generation
- Audio response forwarding

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Gemini API key

### Installation

```bash
# Create virtual environment and install dependencies
uv sync
```

Note: When using `uv run`, you don't need to activate the virtual environment manually. The `uv run` command automatically uses the project's virtual environment.

### Environment Variables

```bash
export GEMINI_API_KEY="your-api-key-here"
```

### Running the Server

```bash
# Recommended: Using uv run (automatically uses the virtual environment)
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Alternative: If you prefer to activate the virtual environment manually
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### WebSocket `/ws`

Real-time audio streaming endpoint. Accepts PCM audio data and returns:
- Audio responses from Gemini
- JSON messages with jokes when detected

### GET `/health`

Health check endpoint.

## Architecture

```
Frontend (React) <--WebSocket--> FastAPI <--Live API--> Gemini
                                    |
                                    +--> generate_joke tool
```

When Gemini detects a joke request, it calls the `generate_joke` tool, which:
1. Generates a joke using the Gemini API
2. Sends the joke to the frontend as a JSON message
3. Returns the result to Gemini for acknowledgment

