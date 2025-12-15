"""
Unit tests for AudioProcessor classes

Tests both PyAudioProcessor and WebSocketAudioProcessor:
- Audio capture and queue management
- Lifecycle operations (start/stop)
- Audio packaging for Gemini API
"""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock

from slidekick.audio_processor import (
    AudioProcessor,
    AudioSourceType,
    PyAudioProcessor,
    WebSocketAudioProcessor,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_pyaudio():
    """Mock pyaudio for testing without actual audio hardware."""
    with patch.object(PyAudioProcessor, '__init__', lambda self, queue_maxsize=5: None):
        processor = object.__new__(PyAudioProcessor)
        processor.audio_queue = asyncio.Queue(maxsize=5)
        processor._is_running = False
        processor._source_type = AudioSourceType.PYAUDIO
        processor._capture_task = None
        processor.MIME_TYPE = "audio/pcm"
        processor.SAMPLE_RATE = 16000
        processor.CHANNELS = 1
        processor.SAMPLE_WIDTH = 2
        processor.CHUNK_SIZE = 1600
        
        # Mock pyaudio internals
        processor.pyaudio = Mock()
        processor.pya = Mock()
        processor.FORMAT = 8  # paInt16
        processor.audio_stream = None
        
        # Mock the PyAudio instance
        processor.pya.get_default_input_device_info.return_value = {
            "index": 0,
            "name": "Test Microphone"
        }
        
        # Mock the audio stream
        mock_stream = Mock()
        mock_stream.read = Mock(return_value=b'\x00\x01' * 1600)
        mock_stream.close = Mock()
        processor.pya.open.return_value = mock_stream
        processor.pya.terminate = Mock()
        
        yield processor


@pytest.fixture
def websocket_processor():
    """Create a WebSocketAudioProcessor for testing."""
    return WebSocketAudioProcessor(queue_maxsize=10)


# =============================================================================
# Abstract Base Class Tests
# =============================================================================


class TestAudioProcessorBase:
    """Tests for the AudioProcessor base class."""
    
    def test_audio_constants(self):
        """Test that audio constants are correctly defined."""
        assert AudioProcessor.SAMPLE_RATE == 16000
        assert AudioProcessor.CHANNELS == 1
        assert AudioProcessor.SAMPLE_WIDTH == 2
        assert AudioProcessor.CHUNK_SIZE == 1600
        assert AudioProcessor.MIME_TYPE == "audio/pcm"
    
    def test_factory_from_pyaudio(self):
        """Test factory method creates PyAudioProcessor."""
        with patch.object(PyAudioProcessor, '__init__', return_value=None):
            processor = AudioProcessor.from_pyaudio(queue_maxsize=5)
            assert isinstance(processor, PyAudioProcessor)
    
    def test_factory_from_websocket(self):
        """Test factory method creates WebSocketAudioProcessor."""
        processor = AudioProcessor.from_websocket(queue_maxsize=50)
        assert isinstance(processor, WebSocketAudioProcessor)
        assert processor.audio_queue.maxsize == 50


# =============================================================================
# PyAudioProcessor Tests
# =============================================================================


class TestPyAudioProcessor:
    """Tests for PyAudioProcessor."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, mock_pyaudio):
        """Test that PyAudioProcessor initializes correctly."""
        processor = mock_pyaudio
        
        assert processor.source_type == AudioSourceType.PYAUDIO
        assert not processor.is_running
        assert processor.audio_stream is None
    
    @pytest.mark.asyncio
    async def test_get_audio_queue(self, mock_pyaudio):
        """Test getting the audio queue."""
        processor = mock_pyaudio
        
        queue = processor.get_audio_queue()
        assert isinstance(queue, asyncio.Queue)
        assert queue.maxsize == 5
    
    @pytest.mark.asyncio
    async def test_package_audio(self, mock_pyaudio):
        """Test audio packaging for Gemini API."""
        processor = mock_pyaudio
        
        raw_data = b'\x00\x01\x02\x03'
        packaged = processor.package_audio(raw_data)
        
        assert packaged["data"] == raw_data
        assert packaged["mime_type"] == "audio/pcm"
    
    @pytest.mark.asyncio
    async def test_start_capture_alias(self, mock_pyaudio):
        """Test that start_capture is an alias for start."""
        processor = mock_pyaudio
        
        # Mock the start method
        processor.start = AsyncMock()
        
        await processor.start_capture()
        processor.start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_capture_alias(self, mock_pyaudio):
        """Test that stop_capture is an alias for stop."""
        processor = mock_pyaudio
        
        # Mock the stop method
        processor.stop = AsyncMock()
        
        await processor.stop_capture()
        processor.stop.assert_called_once()


# =============================================================================
# WebSocketAudioProcessor Tests
# =============================================================================


class TestWebSocketAudioProcessor:
    """Tests for WebSocketAudioProcessor."""
    
    @pytest.mark.asyncio
    async def test_initialization(self, websocket_processor):
        """Test that WebSocketAudioProcessor initializes correctly."""
        assert websocket_processor.source_type == AudioSourceType.WEBSOCKET
        assert not websocket_processor.is_running
        assert websocket_processor.audio_queue.maxsize == 10
        assert websocket_processor.chunk_count == 0
    
    @pytest.mark.asyncio
    async def test_start(self, websocket_processor):
        """Test starting the WebSocket processor."""
        await websocket_processor.start()
        
        assert websocket_processor.is_running
        assert websocket_processor.chunk_count == 0
    
    @pytest.mark.asyncio
    async def test_stop(self, websocket_processor):
        """Test stopping the WebSocket processor."""
        await websocket_processor.start()
        assert websocket_processor.is_running
        
        await websocket_processor.stop()
        assert not websocket_processor.is_running
    
    @pytest.mark.asyncio
    async def test_double_start_warning(self, websocket_processor, caplog):
        """Test that starting twice shows a warning."""
        await websocket_processor.start()
        await websocket_processor.start()  # Second start
        
        assert "already running" in caplog.text
    
    @pytest.mark.asyncio
    async def test_push_audio(self, websocket_processor):
        """Test pushing audio data to the processor."""
        await websocket_processor.start()
        
        audio_data = b'\x00\x01' * 100
        result = await websocket_processor.push_audio(audio_data)
        
        assert result is True
        assert not websocket_processor.audio_queue.empty()
        assert websocket_processor.chunk_count == 1
        
        # Verify audio message format
        audio_msg = await websocket_processor.audio_queue.get()
        assert audio_msg["data"] == audio_data
        assert audio_msg["mime_type"] == "audio/pcm"
    
    @pytest.mark.asyncio
    async def test_push_audio_when_stopped(self, websocket_processor):
        """Test that push_audio returns False when stopped."""
        # Not started, so should fail
        result = await websocket_processor.push_audio(b'\x00\x01')
        
        assert result is False
        assert websocket_processor.audio_queue.empty()
    
    @pytest.mark.asyncio
    async def test_push_audio_queue_overflow(self, websocket_processor):
        """Test that old audio is dropped when queue is full."""
        # Create processor with small queue
        processor = WebSocketAudioProcessor(queue_maxsize=2)
        await processor.start()
        
        # Fill the queue
        await processor.push_audio(b'chunk1')
        await processor.push_audio(b'chunk2')
        
        # Queue should be full now, push another chunk
        await processor.push_audio(b'chunk3')
        
        # Should still have 2 items, oldest dropped
        assert processor.audio_queue.qsize() == 2
        assert processor.chunk_count == 3
    
    def test_push_audio_sync(self, websocket_processor):
        """Test synchronous audio push."""
        # Need to create event loop context for the async queue
        async def run_test():
            await websocket_processor.start()
            
            result = websocket_processor.push_audio_sync(b'\x00\x01' * 50)
            
            assert result is True
            assert websocket_processor.chunk_count == 1
        
        asyncio.run(run_test())
    
    def test_push_audio_sync_when_stopped(self, websocket_processor):
        """Test sync push returns False when not running."""
        result = websocket_processor.push_audio_sync(b'\x00\x01')
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_audio(self, websocket_processor):
        """Test getting audio from the processor."""
        await websocket_processor.start()
        
        # Push some audio
        test_data = b'\x00\x01\x02\x03'
        await websocket_processor.push_audio(test_data)
        
        # Get it back
        audio_msg = await websocket_processor.get_audio()
        
        assert audio_msg["data"] == test_data
        assert audio_msg["mime_type"] == "audio/pcm"
    
    @pytest.mark.asyncio
    async def test_stop_clears_queue(self, websocket_processor):
        """Test that stopping clears the audio queue."""
        await websocket_processor.start()
        
        # Push some audio
        await websocket_processor.push_audio(b'data1')
        await websocket_processor.push_audio(b'data2')
        
        assert not websocket_processor.audio_queue.empty()
        
        await websocket_processor.stop()
        
        assert websocket_processor.audio_queue.empty()
    
    @pytest.mark.asyncio
    async def test_chunk_count_tracking(self, websocket_processor):
        """Test that chunk count is tracked correctly."""
        await websocket_processor.start()
        
        assert websocket_processor.chunk_count == 0
        
        for i in range(5):
            await websocket_processor.push_audio(f'chunk{i}'.encode())
        
        assert websocket_processor.chunk_count == 5
    
    @pytest.mark.asyncio
    async def test_package_audio(self, websocket_processor):
        """Test audio packaging for Gemini API."""
        raw_data = b'\x00\x01\x02\x03'
        packaged = websocket_processor.package_audio(raw_data)
        
        assert packaged["data"] == raw_data
        assert packaged["mime_type"] == "audio/pcm"


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestAudioProcessorIntegration:
    """Integration-style tests for audio processors."""
    
    @pytest.mark.asyncio
    async def test_websocket_producer_consumer(self, websocket_processor):
        """Test producer-consumer pattern with WebSocket processor."""
        await websocket_processor.start()
        
        received_chunks = []
        
        async def producer():
            for i in range(10):
                await websocket_processor.push_audio(f'chunk{i}'.encode())
                await asyncio.sleep(0.01)
        
        async def consumer():
            for _ in range(10):
                chunk = await asyncio.wait_for(
                    websocket_processor.get_audio(),
                    timeout=1.0
                )
                received_chunks.append(chunk)
        
        await asyncio.gather(producer(), consumer())
        
        assert len(received_chunks) == 10
        assert websocket_processor.chunk_count == 10
    
    @pytest.mark.asyncio
    async def test_websocket_concurrent_pushes(self, websocket_processor):
        """Test concurrent audio pushes."""
        await websocket_processor.start()
        
        async def pusher(prefix: str):
            for i in range(5):
                await websocket_processor.push_audio(f'{prefix}_{i}'.encode())
        
        await asyncio.gather(
            pusher('a'),
            pusher('b'),
            pusher('c'),
        )
        
        assert websocket_processor.chunk_count == 15
