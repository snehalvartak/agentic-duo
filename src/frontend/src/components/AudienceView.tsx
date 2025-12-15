import React from 'react';

interface AudienceViewProps {
  slideUrl: string;
  onExit: () => void;
}

export const AudienceView: React.FC<AudienceViewProps> = ({ slideUrl, onExit }) => {
  return (
    <div className="audience-view">
      <iframe src={slideUrl} title="Audience Presentation" className="fullscreen-iframe" />
      <button className="exit-btn" onClick={onExit}>Exit</button>
    </div>
  );
};

