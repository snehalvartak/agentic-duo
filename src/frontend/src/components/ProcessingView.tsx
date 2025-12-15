import React from 'react';
import { FileText, Loader2, X } from 'lucide-react';
import { motion } from 'framer-motion';

interface ProcessingViewProps {
  file: File | null;
}

export const ProcessingView: React.FC<ProcessingViewProps> = ({ file }) => {
  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="card"
    >
      <div className="card-header">
        <h2>Slidekick - Processing</h2>
      </div>
      <div className="processing-state">
        <div className="file-info disabled">
          <FileText size={32} className="file-icon" />
          <div className="file-details">
            <span className="file-name">{file?.name}</span>
            <span className="file-size">{file ? (file.size / 1024).toFixed(1) : 0} KB</span>
          </div>
          <button className="remove-btn" disabled>
            <X size={20} />
          </button>
        </div>
        
        <div className="progress-container">
          <div className="loading-spinner">
            <Loader2 size={24} className="spin" />
            <span>Processing...</span>
          </div>
          <div className="progress-bar">
            <motion.div 
              className="progress-fill"
              initial={{ width: "0%" }}
              animate={{ width: "100%" }}
              transition={{ duration: 1.5 }}
            />
          </div>
          <p className="status-text">Converting {file?.name} to Reveal.js format...</p>
        </div>
      </div>
    </motion.div>
  );
};

