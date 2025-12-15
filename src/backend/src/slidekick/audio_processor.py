"""
Audio Processor Module

Handles audio capture from multiple sources (PyAudio microphone or WebSocket)
and provides a unified interface for audio streaming.

This module provides:
- Unified audio processing for PyAudio and WebSocket sources
- PCM audio format configuration (16kHz, 16-bit, Mono)
- Queue-based audio streaming
- Lifecycle management (start/stop)
- Factory methods for creating source-specific instances
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class AudioSourceType(Enum):
    """Enumeration of supported audio source types."""
    PYAUDIO = "pyaudio"
    WEBSOCKET = "websocket"


class AudioProcessor(ABC):
    """
    Abstract base class for audio processing.
    
    Provides a unified interface for different audio sources (PyAudio, WebSocket).
    Audio is processed at 16kHz, 16-bit, Mono PCM format as required by Gemini Live API.
    """
    
    # Audio configuration constants
    SAMPLE_RATE = 16000  # 16kHz required by Gemini Live API
    CHANNELS = 1         # Mono
    SAMPLE_WIDTH = 2     # 16-bit = 2 bytes
    CHUNK_SIZE = 1600    # ~100ms of audio at 16kHz
    MIME_TYPE = "audio/pcm"
    
    def __init__(self, queue_maxsize: int = 5):
        """
        Initialize the audio processor.
        
        Args:
            queue_maxsize: Maximum size of the audio queue (default: 5)
        """
        self.audio_queue: asyncio.Queue = asyncio.Queue(maxsize=queue_maxsize)
        self._is_running = False
        self._source_type: AudioSourceType | None = None
    
    @classmethod
    def from_pyaudio(cls, queue_maxsize: int = 5) -> "PyAudioProcessor":
        """
        Create an AudioProcessor that captures from local microphone via PyAudio.
        
        Args:
            queue_maxsize: Maximum size of the audio queue
            
        Returns:
            PyAudioProcessor instance
        """
        return PyAudioProcessor(queue_maxsize=queue_maxsize)
    
    @classmethod
    def from_websocket(cls, queue_maxsize: int = 100) -> "WebSocketAudioProcessor":
        """
        Create an AudioProcessor that receives audio from a WebSocket connection.
        
        Args:
            queue_maxsize: Maximum size of the audio queue (larger default for network buffering)
            
        Returns:
            WebSocketAudioProcessor instance
        """
        return WebSocketAudioProcessor(queue_maxsize=queue_maxsize)
    
    @abstractmethod
    async def start(self) -> None:
        """Start the audio processor."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the audio processor and clean up resources."""
        pass
    
    def get_audio_queue(self) -> asyncio.Queue:
        """
        Get the audio queue for consuming audio chunks.
        
        Returns:
            asyncio.Queue containing audio messages in Gemini Live API format
        """
        return self.audio_queue
    
    async def get_audio(self) -> dict:
        """
        Get the next audio chunk from the queue.
        
        Returns:
            Audio message dict with 'data' and 'mime_type' keys
        """
        return await self.audio_queue.get()
    
    def package_audio(self, data: bytes) -> dict:
        """
        Package raw audio bytes into Gemini Live API format.
        
        Args:
            data: Raw PCM audio bytes
            
        Returns:
            Dict with 'data' and 'mime_type' keys
        """
        return {
            "data": data,
            "mime_type": self.MIME_TYPE
        }
    
    @property
    def is_running(self) -> bool:
        """Check if audio processing is currently active."""
        return self._is_running
    
    @property
    def source_type(self) -> AudioSourceType | None:
        """Get the type of audio source."""
        return self._source_type


class PyAudioProcessor(AudioProcessor):
    """
    Audio processor that captures from local microphone using PyAudio.
    
    Use this for local CLI applications or when running directly on a machine
    with microphone access.
    """
    
    def __init__(self, queue_maxsize: int = 5):
        """
        Initialize the PyAudio processor.
        
        Args:
            queue_maxsize: Maximum size of the audio queue
        """
        super().__init__(queue_maxsize=queue_maxsize)
        self._source_type = AudioSourceType.PYAUDIO
        self._capture_task: Optional[asyncio.Task] = None
        
        # Lazy import pyaudio to avoid import errors when not used
        try:
            import pyaudio
            self.pyaudio = pyaudio
            self.pya = pyaudio.PyAudio()
            self.FORMAT = pyaudio.paInt16
        except ImportError:
            logger.warning("PyAudio not installed. Install with: pip install pyaudio")
            self.pyaudio = None
            self.pya = None
            self.FORMAT = None
        
        self.audio_stream = None
    
    async def start(self) -> None:
        """
        Start capturing audio from the default microphone.
        
        Creates an audio stream and begins capturing audio chunks,
        placing them into the audio queue.
        
        Raises:
            RuntimeError: If PyAudio is not available
            Exception: If audio input setup fails
        """
        if self.pya is None:
            raise RuntimeError("PyAudio is not installed. Cannot capture from microphone.")
        
        if self._is_running:
            logger.warning("Audio capture is already running")
            return
        
        try:
            # Get default input device
            mic_info = self.pya.get_default_input_device_info()
            logger.info(f"Using microphone: {mic_info.get('name', 'Unknown')}")
            
            # Open audio stream
            self.audio_stream = await asyncio.to_thread(
                self.pya.open,
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.SAMPLE_RATE,
                input=True,
                input_device_index=mic_info["index"],
                frames_per_buffer=self.CHUNK_SIZE,
            )
            
            self._is_running = True
            
            # Start the capture loop
            self._capture_task = asyncio.create_task(self._capture_loop())
            logger.info("PyAudio capture started")
            
        except Exception as e:
            logger.exception(f"Error setting up audio input: {e}")
            raise
    
    async def _capture_loop(self) -> None:
        """
        Internal loop that continuously captures audio chunks.
        
        Runs until stop() is called.
        """
        # Suppress overflow exceptions in debug mode
        kwargs = {"exception_on_overflow": False} if __debug__ else {}
        
        try:
            while self._is_running:
                try:
                    # Read audio chunk from stream
                    data = await asyncio.to_thread(
                        self.audio_stream.read, 
                        self.CHUNK_SIZE, 
                        **kwargs
                    )
                    
                    # Package for Gemini Live API format
                    audio_msg = self.package_audio(data)
                    
                    # Put into queue for consumption
                    await self.audio_queue.put(audio_msg)
                    
                except Exception as e:
                    if self._is_running:  # Only log if not shutting down
                        logger.error(f"Error reading audio: {e}")
                        await asyncio.sleep(0.1)
                    continue
                    
        except asyncio.CancelledError:
            # Clean shutdown
            pass
    
    async def stop(self) -> None:
        """
        Stop capturing audio and clean up resources.
        
        Closes the audio stream and terminates pyaudio.
        """
        self._is_running = False
        
        # Cancel the capture task
        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass
        
        # Close audio stream
        if self.audio_stream:
            try:
                self.audio_stream.close()
            except Exception as e:
                logger.error(f"Error closing audio stream: {e}")
        
        # Terminate pyaudio
        if self.pya:
            try:
                self.pya.terminate()
            except Exception as e:
                logger.error(f"Error terminating pyaudio: {e}")
        
        logger.info("PyAudio capture stopped")
    
    # Backward compatibility aliases
    async def start_capture(self) -> None:
        """Alias for start() for backward compatibility."""
        await self.start()
    
    async def stop_capture(self) -> None:
        """Alias for stop() for backward compatibility."""
        await self.stop()


class WebSocketAudioProcessor(AudioProcessor):
    """
    Audio processor that receives audio from a WebSocket connection.
    
    Use this for web-based applications where audio is captured in the browser
    and streamed to the backend via WebSocket.
    """
    
    def __init__(self, queue_maxsize: int = 100):
        """
        Initialize the WebSocket audio processor.
        
        Args:
            queue_maxsize: Maximum size of the audio queue (larger for network buffering)
        """
        super().__init__(queue_maxsize=queue_maxsize)
        self._source_type = AudioSourceType.WEBSOCKET
        self._chunk_count = 0
    
    async def start(self) -> None:
        """
        Start the WebSocket audio processor.
        
        Unlike PyAudio, this doesn't start a capture loop since audio
        is pushed from the WebSocket handler via push_audio().
        """
        if self._is_running:
            logger.warning("WebSocket audio processor is already running")
            return
        
        self._is_running = True
        self._chunk_count = 0
        logger.info("WebSocket audio processor started")
    
    async def stop(self) -> None:
        """
        Stop the WebSocket audio processor.
        
        Clears any remaining audio in the queue.
        """
        self._is_running = False
        
        # Clear the queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        logger.info(f"WebSocket audio processor stopped (processed {self._chunk_count} chunks)")
    
    async def push_audio(self, data: bytes) -> bool:
        """
        Push audio data received from WebSocket into the processing queue.
        
        Args:
            data: Raw PCM audio bytes from WebSocket
            
        Returns:
            True if audio was queued successfully, False if processor is stopped or queue is full
        """
        if not self._is_running:
            return False
        
        try:
            audio_msg = self.package_audio(data)
            
            # Use put_nowait to avoid blocking the WebSocket handler
            # If queue is full, we drop the oldest chunk
            if self.audio_queue.full():
                try:
                    self.audio_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            
            await self.audio_queue.put(audio_msg)
            self._chunk_count += 1
            
            if self._chunk_count % 100 == 0:
                logger.debug(f"WebSocket audio chunks processed: {self._chunk_count}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error pushing audio to queue: {e}")
            return False
    
    def push_audio_sync(self, data: bytes) -> bool:
        """
        Synchronous version of push_audio for use in sync contexts.
        
        Args:
            data: Raw PCM audio bytes from WebSocket
            
        Returns:
            True if audio was queued successfully, False otherwise
        """
        if not self._is_running:
            return False
        
        try:
            audio_msg = self.package_audio(data)
            
            # Use put_nowait - drop oldest if full
            if self.audio_queue.full():
                try:
                    self.audio_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            
            self.audio_queue.put_nowait(audio_msg)
            self._chunk_count += 1
            
            return True
            
        except asyncio.QueueFull:
            logger.warning("Audio queue full, dropping chunk")
            return False
        except Exception as e:
            logger.error(f"Error pushing audio to queue: {e}")
            return False
    
    @property
    def chunk_count(self) -> int:
        """Get the number of audio chunks processed."""
        return self._chunk_count
