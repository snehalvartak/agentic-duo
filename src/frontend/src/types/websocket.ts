// Frontend -> Backend
export interface SlideInfoMessage {
  type: 'slide_info';
  total_slides: number;
  current_slide: number;
}

export interface SlideSyncMessage {
  type: 'slide_sync';
  current_slide: number;
}

export interface TriggerToolMessage {
  type: 'trigger_tool';
  tool: string;
  args: Record<string, unknown>;
}

// Backend -> Frontend
export interface StatusMessage {
  type: 'status';
  status: string;
  message: string;
}

export interface IntentDetectedMessage {
  type: 'intent_detected';
  tool: string;
  args: Record<string, unknown>;
}

export interface SlideCommandMessage {
  type: 'slide_command';
  action: 'next' | 'prev' | 'jump';
  slide_index: number;
  status: string;
}

export interface TranscriptMessage {
  type: 'transcript';
  text: string;
}

export interface ToolResultMessage {
  type: 'tool_result';
  tool: string;
  status: string;
  data: Record<string, unknown>;
}

export type WebSocketMessage = 
  | StatusMessage 
  | IntentDetectedMessage 
  | SlideCommandMessage 
  | TranscriptMessage 
  | ToolResultMessage;

