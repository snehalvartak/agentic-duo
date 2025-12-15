import React, { useRef, useState } from 'react';
import { Upload, FileText, X } from 'lucide-react';
import { motion } from 'framer-motion';

interface UploadViewProps {
  file: File | null;
  setFile: (file: File | null) => void;
  onTransform: () => void;
  error: string;
  setError: (error: string) => void;
  onReset: () => void;
}

export const UploadView: React.FC<UploadViewProps> = ({ 
  file, 
  setFile, 
  onTransform, 
  error, 
  setError,
  onReset 
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.name.endsWith('.md')) {
        setFile(droppedFile);
        setError('');
      } else {
        setError('Please upload a .md file');
      }
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (selectedFile.name.endsWith('.md')) {
        setFile(selectedFile);
        setError('');
      } else {
        setError('Please upload a .md file');
      }
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="card"
    >
      <div className="card-header">
        <h2>Slidekick - Upload Presentation</h2>
      </div>
      
      {!file ? (
        <div 
          className={`drop-zone ${isDragging ? 'dragging' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input 
            type="file" 
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept=".md"
            style={{ display: 'none' }}
          />
          <Upload size={48} className="upload-icon" />
          <h3>Drag & Drop your slides.md file here</h3>
          <p>or click to browse</p>
          <button className="select-btn">Select File</button>
        </div>
      ) : (
        <div className="file-selected">
          <div className="file-info">
            <FileText size={32} className="file-icon" />
            <div className="file-details">
              <span className="file-name">{file.name}</span>
              <span className="file-size">{(file.size / 1024).toFixed(1)} KB</span>
            </div>
            <button className="remove-btn" onClick={onReset}>
              <X size={20} />
            </button>
          </div>
          
          <button className="transform-btn" onClick={onTransform}>
            Transform to Presentation
          </button>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}
    </motion.div>
  );
};

