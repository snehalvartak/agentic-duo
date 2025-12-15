import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Mic, MicOff, Volume2, SkipBack, SkipForward, Image as ImageIcon, FileText } from 'lucide-react';
import { WebSocketMessage } from '../types/websocket';

interface PresenterViewProps {
  slideUrl: string;
  onExit: () => void;
}

interface LogEntry {
  timestamp: string;
  message: string;
  type: 'info' | 'success' | 'error' | 'command';
}

// Extend Window interface for Reveal.js access
declare global {
  interface Window {
    Reveal?: {
      next: () => void;
      prev: () => void;
      slide: (h: number, v?: number) => void;
      getIndices: () => { h: number; v: number };
      getTotalSlides: () => number;
      sync: () => void;
      getCurrentSlide: () => HTMLElement;
    };
  }
}

export const PresenterView: React.FC<PresenterViewProps> = ({ slideUrl, onExit }) => {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioPlayerRef = useRef<AudioContext | null>(null);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [statusMessage, setStatusMessage] = useState('Click to start voice control');

  // New state variables
  const [transcript, setTranscript] = useState<string[]>([]);
  const [aiStatus, setAiStatus] = useState<string>('Ready');
  const [detectedIntent, setDetectedIntent] = useState<{ tool: string; args: Record<string, unknown> } | null>(null);

  const [currentSlide, setCurrentSlide] = useState(0);
  const [totalSlides, setTotalSlides] = useState(0);
  const [isGeneratingSummary, setIsGeneratingSummary] = useState(false);

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  // Access the Reveal.js instance from the iframe
  const getReveal = useCallback(() => {
    try {
      return iframeRef.current?.contentWindow?.Reveal;
    } catch {
      return undefined;
    }
  }, []);

  // Send slide info to backend
  const sendSlideInfo = useCallback(() => {
    const Reveal = getReveal();
    if (!Reveal || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    const total = Reveal.getTotalSlides();
    const indices = Reveal.getIndices();

    wsRef.current.send(JSON.stringify({
      type: 'slide_info',
      total_slides: total,
      current_slide: indices.h,
    }));
  }, [getReveal]);

  // Sync current slide position with backend
  const syncSlidePosition = useCallback(() => {
    const Reveal = getReveal();
    if (!Reveal || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    const indices = Reveal.getIndices();
    wsRef.current.send(JSON.stringify({
      type: 'slide_sync',
      current_slide: indices.h,
    }));
  }, [getReveal]);

  // Navigate slides
  const navigateSlide = useCallback((action: string, slideIndex?: number) => {
    const Reveal = getReveal();
    if (!Reveal) return;

    try {
      switch (action) {
        case 'next':
          Reveal.next();
          break;
        case 'prev':
          Reveal.prev();
          break;
        case 'jump':
          if (slideIndex !== undefined) {
            Reveal.slide(slideIndex);
          }
          break;
      }

      // Update current slide state
      const indices = Reveal.getIndices();
      setCurrentSlide(indices.h);
      setTotalSlides(Reveal.getTotalSlides());

      // Sync with backend
      syncSlidePosition();
    } catch (e) {
      console.error(`Navigation error: ${e}`);
    }
  }, [getReveal, syncSlidePosition]);

  // Request summary generation
  const requestSummary = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setAiStatus('Error: Voice control must be active');
      return;
    }

    setIsGeneratingSummary(true);
    setAiStatus('Generating summary...');
    wsRef.current.send(JSON.stringify({ type: 'request_summary' }));
  }, []);



  // Inject summary slide
  const injectSummary = useCallback((html: string) => {
    if (!iframeRef.current?.contentDocument) {
      console.warn('injectSummary: contentDocument not available');
      return;
    }

    try {
      console.debug('injectSummary: Starting injection');
      const doc = iframeRef.current.contentDocument;
      const slidesContainer = doc.querySelector('.reveal .slides');

      if (slidesContainer) {
        const section = doc.createElement('section');
        section.innerHTML = html;
        slidesContainer.appendChild(section);
        console.debug('injectSummary: Slide appended to DOM');

        const Reveal = getReveal();
        if (Reveal) {
          Reveal.sync();
          // Jump to the new last slide
          Reveal.slide(Reveal.getTotalSlides() - 1);

          // Update local state
          setTotalSlides(Reveal.getTotalSlides());
          setCurrentSlide(Reveal.getIndices().h);
          console.debug('injectSummary: Reveal synced and navigated');
        } else {
          console.error('injectSummary: Reveal instance not found after DOM update');
        }
      } else {
        console.error('injectSummary: .reveal .slides container not found');
      }
    } catch (e) {
      console.error('injectSummary failed:', e);
    }
  }, [getReveal]);

  // Handle WebSocket messages
  const handleWebSocketMessage = useCallback(async (event: MessageEvent) => {
    if (event.data instanceof Blob) {
      // Handle audio from Gemini
      const arrayBuffer = await event.data.arrayBuffer();
      playAudio(arrayBuffer);
    } else {
      try {
        const message = JSON.parse(event.data) as WebSocketMessage;

        switch (message.type) {
          case 'status':
            setStatusMessage(message.message);
            break;

          case 'intent_detected':
            setDetectedIntent({ tool: message.tool, args: message.args });
            setAiStatus('Executing command...');
            break;

          case 'slide_command':
            navigateSlide(message.action, message.slide_index);
            setAiStatus(`Navigated: ${message.action}`);
            // Clear intent after delay
            setTimeout(() => setDetectedIntent(null), 3000);
            break;

          case 'tool_result':
            setAiStatus(`Tool complete: ${message.status}`);
            setTimeout(() => setDetectedIntent(null), 3000);
            break;

          case 'transcript':
            setTranscript(prev => [...prev.slice(-19), message.text]);
            setAiStatus('Processing speech...');
            break;

          case 'inject_summary':
            if ('html' in message) {
              injectSummary(message.html);
              setAiStatus('Summary Injected');
              setIsGeneratingSummary(false);
              setTimeout(() => setDetectedIntent(null), 5000);
            }
            break;

          default:
            console.log('Unknown message type:', message);
        }
      } catch (e) {
        console.error('Error parsing message:', e);
      }
    }
  }, [navigateSlide, injectSummary]);

  // Play audio from Gemini
  const playAudio = (audioData: ArrayBuffer) => {
    if (audioData.byteLength < 2) return;

    if (!audioPlayerRef.current) {
      audioPlayerRef.current = new AudioContext({ sampleRate: 24000 });
    }

    const audioBuffer = audioPlayerRef.current.createBuffer(
      1,
      audioData.byteLength / 2,
      24000
    );

    const channelData = audioBuffer.getChannelData(0);
    const int16Array = new Int16Array(audioData);

    for (let i = 0; i < int16Array.length; i++) {
      channelData[i] = int16Array[i] / 32768.0;
    }

    const source = audioPlayerRef.current.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioPlayerRef.current.destination);
    source.start();
  };

  // Start voice control
  const startVoiceControl = async () => {
    try {
      setStatusMessage('Connecting...');

      // Connect WebSocket (uses proxy)
      const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = async () => {
        setIsConnected(true);
        setStatusMessage('Connected! Starting audio capture...');

        // Send slide info to backend
        sendSlideInfo();

        // Start audio capture
        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
              sampleRate: 16000,
              channelCount: 1,
              echoCancellation: true,
              noiseSuppression: true,
            },
          });
          mediaStreamRef.current = stream;

          audioContextRef.current = new AudioContext({ sampleRate: 16000 });
          await audioContextRef.current.audioWorklet.addModule('/audio-processor.js');

          const source = audioContextRef.current.createMediaStreamSource(stream);
          workletNodeRef.current = new AudioWorkletNode(
            audioContextRef.current,
            'audio-processor'
          );

          workletNodeRef.current.port.onmessage = (event) => {
            if (wsRef.current?.readyState === WebSocket.OPEN) {
              wsRef.current.send(event.data);
            }
          };

          source.connect(workletNodeRef.current);
          setIsRecording(true);
          setStatusMessage('Listening...');
        } catch (e) {
          console.error(`Microphone error: ${e}`);
          setStatusMessage('Microphone access denied');
        }
      };

      wsRef.current.onmessage = handleWebSocketMessage;

      wsRef.current.onerror = (error) => {
        console.error(`WebSocket error: ${error}`);
        setStatusMessage('Connection error');
      };

      wsRef.current.onclose = () => {
        setIsConnected(false);
        setIsRecording(false);
        setStatusMessage('Disconnected');
      };
    } catch (error) {
      console.error(`Error: ${error}`);
      setStatusMessage('Failed to start');
    }
  };

  // Stop voice control
  const stopVoiceControl = () => {
    if (workletNodeRef.current) {
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }

    setIsRecording(false);
    setIsConnected(false);
    setStatusMessage('Voice control stopped');
  };

  // Update slide info when iframe loads
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    const handleLoad = () => {
      // Wait for Reveal.js to initialize
      setTimeout(() => {
        const Reveal = getReveal();
        if (Reveal) {
          setTotalSlides(Reveal.getTotalSlides());
          const indices = Reveal.getIndices();
          setCurrentSlide(indices.h);

          // If already connected, sync with backend
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            sendSlideInfo();
          }
        }
      }, 1000);
    };

    iframe.addEventListener('load', handleLoad);
    return () => iframe.removeEventListener('load', handleLoad);
  }, [getReveal, sendSlideInfo]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopVoiceControl();
    };
  }, []);

  return (
    <div className="presenter-view">
      <div className="presenter-dashboard">
        <div className="dashboard-header">
          <h2>Presenter Dashboard</h2>
          <button className="exit-btn-small" onClick={onExit}>Exit</button>
        </div>

        <div className="dashboard-content">
          {/* 1. Voice Control / Listening Status */}
          <div className="control-section listening-section">
            <div className="status-row">
              {isRecording ? (
                <>
                  <Volume2 className="pulse" size={20} color="#4caf50" />
                  <span className="listening-text">LISTENING...</span>
                  <div className="audio-visualizer">
                    {[...Array(8)].map((_, i) => (
                      <div key={i} className="bar" style={{ animationDelay: `${i * 0.1}s` }} />
                    ))}
                  </div>
                </>
              ) : (
                <span className="status-text">{statusMessage}</span>
              )}
            </div>
            <button
              className={`voice-btn ${isRecording ? 'recording' : ''}`}
              onClick={isRecording ? stopVoiceControl : startVoiceControl}
            >
              {isRecording ? <MicOff size={18} /> : <Mic size={18} />}
              {isRecording ? 'Stop' : 'Start'} Voice
            </button>
          </div>

          {/* 2. AI Response */}
          <div className="control-section transcript-section">
            <h3>AI Response</h3>
            <div className="transcript-box">
              {transcript.length === 0 ? (
                <div className="transcript-placeholder">AI responses will appear here...</div>
              ) : (
                transcript.map((text, i) => (
                  <div key={i} className="transcript-line">"{text}"</div>
                ))
              )}
              <div ref={transcriptEndRef} />
            </div>
          </div>

          {/* 3. AI Status */}
          <div className="control-section ai-status-section">
            <h3>AI Status</h3>
            <div className="ai-status-indicator">
              <div className={`status-dot ${aiStatus !== 'Ready' ? 'active' : ''}`} />
              <span>{aiStatus}</span>
            </div>
          </div>

          {/* 4. Detected Intent */}
          <div className="control-section intent-section">
            <h3>Detected Intent</h3>
            {detectedIntent ? (
              <div className="intent-card">
                <div className="intent-tool">→ {detectedIntent.tool}</div>
                <div className="intent-args">
                  {JSON.stringify(detectedIntent.args, null, 2)}
                </div>
              </div>
            ) : (
              <div className="intent-placeholder">Waiting for command...</div>
            )}
          </div>

          {/* 5. Manual Controls */}
          <div className="control-section manual-controls">
            <h3>Manual Controls</h3>

            <div className="slide-info-text">
              Slide {currentSlide + 1} of {totalSlides || '?'}
            </div>

            <div className="control-grid">
              <button className="control-btn" onClick={() => navigateSlide('prev')}>
                <SkipBack size={16} /> Prev
              </button>
              <button className="control-btn" onClick={() => navigateSlide('next')}>
                Next <SkipForward size={16} />
              </button>
              <button className="control-btn disabled" title="Coming Soon">
                <ImageIcon size={16} /> Inject
              </button>
              <button 
                className={`control-btn ${isGeneratingSummary ? 'loading' : ''}`}
                onClick={requestSummary}
                disabled={isGeneratingSummary}
                title={isGeneratingSummary ? 'Generating...' : 'Generate presentation summary'}
              >
                <FileText size={16} /> {isGeneratingSummary ? 'Generating...' : 'Summary'}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="presenter-slides">
        <iframe
          ref={iframeRef}
          src={slideUrl}
          title="Presenter Presentation"
          className="preview-iframe"
        />
      </div>
    </div>
  );
};
