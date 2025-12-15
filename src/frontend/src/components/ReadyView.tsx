import React from 'react';
import { FileText, CheckCircle2, Monitor, Users, X } from 'lucide-react';
import { motion } from 'framer-motion';

interface ReadyViewProps {
  file: File | null;
  onReset: () => void;
  onStartPresenter: () => void;
  onStartAudience: () => void;
}

export const ReadyView: React.FC<ReadyViewProps> = ({ 
  file, 
  onReset, 
  onStartPresenter, 
  onStartAudience 
}) => {
  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="card"
    >
      <div className="card-header">
        <h2>Slidekick - Ready</h2>
      </div>
      
      <div className="ready-state">
        <div className="file-info disabled">
          <FileText size={32} className="file-icon" />
          <div className="file-details">
            <span className="file-name">{file?.name}</span>
            <span className="file-size">{file ? (file.size / 1024).toFixed(1) : 0} KB</span>
          </div>
          <button className="remove-btn" onClick={onReset}>
            <X size={20} />
          </button>
        </div>

        <div className="success-message">
          <CheckCircle2 size={32} className="success-icon" />
          <h3>Presentation Ready!</h3>
        </div>

        <div className="action-buttons">
          <button className="mode-btn primary" onClick={onStartPresenter}>
            <Monitor size={20} />
            Start Presenter View
          </button>
          <button className="mode-btn secondary" onClick={onStartAudience}>
            <Users size={20} />
            Start Audience View
          </button>
        </div>
      </div>
    </motion.div>
  );
};

