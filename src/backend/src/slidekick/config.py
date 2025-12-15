import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).cwd()
ENV_PATH = BASE_DIR / ".env"


if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    raise FileNotFoundError(f"Environment file not found at {ENV_PATH}")

""" Gemini Configuration """

if not (GEMINI_API_KEY := os.getenv('GEMINI_API_KEY')):
    raise ValueError("GEMINI_API_KEY not found in environment variables.")

LIVE_GEMINI_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

GEMINI_LIVE_SYSTEM_INSTRUCTION = """
You are an AI presentation assistant controlling a slide deck.

Your goal is to help the presenter by navigating slides, adding content, and executing commands in real-time.

AVAILABLE TOOLS:
1. `navigate_slide(direction, index)`: Move next/prev or jump to slide. NOTE: index is 1-BASED (Slide 1 = index 1).
2. `add_content(content)`: Add text/bullets to current slide.
3. `inject_image(prompt)`: Generate an image for the slide.
4. `generate_summary()`: Summarize the talk so far.
5. `get_presentation_context()`: Check current slide # and status.

RULES:
- Execute commands immediately when asked.
- If the user just talks about the topic, DO NOT call tools. Only call tools for COMMANDS (e.g. "Next slide", "Add that point", "Show me a picture").
- If unsure, do nothing (don't interrupt the flow).
"""

VERBOSE_TOOL_LOGS = int(os.getenv("VERBOSE_TOOL_LOG", 1))


""" Static file/directory Configuration """

PUBLIC_DIR = BASE_DIR / "public"

UPLOADS_DIR = PUBLIC_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

SLIDES_DIR = PUBLIC_DIR / "slides"

""" Logging Configuration """

LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

file_handler = logging.FileHandler(filename=LOG_DIR / 'slidekick.log')
console_handler = logging.StreamHandler(sys.stderr)

def make_record_with_extra():
    original_make_record = logging.Logger.makeRecord

    def makeRecord(self, *args, **kwargs):
        EXTRA_INDEX = 8
        args_ = list(args)
        args_[EXTRA_INDEX] = args[EXTRA_INDEX] or {"session_id": "N/A"}
        record = original_make_record(self, *args_, **kwargs)

        return record

    return makeRecord

logging.Logger.makeRecord = make_record_with_extra()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)-8s] {%(filename)s:%(lineno)d} :: %(message)s',
    handlers=[file_handler, console_handler]
)