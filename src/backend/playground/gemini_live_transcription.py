import asyncio
import os

import pyaudio
from dotenv import load_dotenv
from google import genai

# Load environment variables from .env file
load_dotenv()

# Get API key from environment variable
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables. Please set it in your .env file.")

# --- pyaudio config ---
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
CHUNK_SIZE = 1024

pya = pyaudio.PyAudio()

client = genai.Client(api_key=api_key)
MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

CONFIG = {
    "response_modalities": ["AUDIO"],
    "input_audio_transcription": {}
}

audio_queue_mic: asyncio.Queue[dict[str, bytes]] = asyncio.Queue(maxsize=5)
audio_stream: pyaudio.Stream | None = None

async def listen_audio():
    """Listens for audio and puts it into the mic audio queue."""
    global audio_stream
    mic_info = pya.get_default_input_device_info()
    audio_stream = await asyncio.to_thread(
        pya.open,
        format=FORMAT,
        channels=CHANNELS,
        rate=SEND_SAMPLE_RATE,
        input=True,
        input_device_index=mic_info["index"],
        frames_per_buffer=CHUNK_SIZE,
    )
    kwargs = {"exception_on_overflow": False} if __debug__ else {}
    while True:
        data = await asyncio.to_thread(audio_stream.read, CHUNK_SIZE, **kwargs)
        await audio_queue_mic.put({"data": data, "mime_type": "audio/pcm;rate=16000"})

async def send_realtime(session):
    """Sends audio from the mic audio queue to the GenAI session."""
    while True:
        msg = await audio_queue_mic.get()
        await session.send_realtime_input(audio=msg)

async def receive_transcription(session):
    """Receives input audio transcriptions from GenAI and prints them to stdout."""
    while True:
        turn = session.receive()
        async for response in turn:
            if (response.server_content and 
                response.server_content.input_transcription and
                response.server_content.input_transcription.text):
                print('Transcript:', response.server_content.input_transcription.text, flush=True)

async def run():
    """Main function to run the audio transcription loop."""
    try:
        async with client.aio.live.connect(
            model=MODEL, config=CONFIG
        ) as live_session:
            print("Connected to Gemini. Start speaking! (Transcriptions will appear below)")
            async with asyncio.TaskGroup() as tg:
                tg.create_task(send_realtime(live_session))
                tg.create_task(listen_audio())
                tg.create_task(receive_transcription(live_session))
    except asyncio.CancelledError:
        pass
    finally:
        if audio_stream:
            audio_stream.close()
        pya.terminate()
        print("\nConnection closed.")

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Interrupted by user.")