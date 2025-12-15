import React, { useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import './App.css';
import { UploadView } from './components/UploadView';
import { ProcessingView } from './components/ProcessingView';
import { ReadyView } from './components/ReadyView';
import { AudienceView } from './components/AudienceView';
import { PresenterView } from './components/PresenterView';

function App() {
  const [view, setView] = useState<'upload' | 'processing' | 'ready' | 'presenter' | 'audience'>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [slideUrl, setSlideUrl] = useState<string>('');
  const [error, setError] = useState<string>('');

  const handleTransform = async () => {
    if (!file) return;

    setView('processing');
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/upload', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (data.status === 'success') {
        // Add timestamp to prevent caching (use relative URL through proxy)
        setSlideUrl(`${data.url}?t=${Date.now()}`);
        // Simulate a small delay for the progress bar visual
        setTimeout(() => setView('ready'), 1500);
      } else {
        setError(data.message || 'Transformation failed');
        setView('upload');
      }
    } catch (err) {
      setError('Failed to connect to backend');
      setView('upload');
    }
  };

  const handleReset = () => {
    setFile(null);
    setView('upload');
    setError('');
  };

  return (
    <div className="App">
      <div className="background-gradient" />
      <div className="content-container">
        <AnimatePresence mode="wait">
          {view === 'upload' && (
            <UploadView 
              file={file} 
              setFile={setFile} 
              onTransform={handleTransform} 
              error={error} 
              setError={setError}
              onReset={handleReset}
            />
          )}
          {view === 'processing' && (
            <ProcessingView file={file} />
          )}
          {view === 'ready' && (
            <ReadyView 
              file={file} 
              onReset={handleReset}
              onStartPresenter={() => setView('presenter')}
              onStartAudience={() => setView('audience')}
            />
          )}
          {view === 'audience' && (
            <AudienceView 
              slideUrl={slideUrl} 
              onExit={() => setView('ready')} 
            />
          )}
          {view === 'presenter' && (
            <PresenterView 
              slideUrl={slideUrl} 
              onExit={() => setView('ready')} 
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default App;
