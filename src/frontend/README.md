# Slidekick Frontend

React + TypeScript frontend for **Slidekick** - Your A.I Presentation Companion

## Summary

The Slidekick frontend provides a real-time presentation interface with voice-controlled navigation. It connects to the backend via WebSocket to stream audio, receive AI-generated responses, and control slide navigation through natural voice commands. The interface displays presentation slides, live transcripts, and AI status updates.

## Features

- Real-time voice control for slide navigation
- WebSocket-based audio streaming to backend
- Live transcript display
- AI status and intent detection
- Reveal.js presentation integration
- Audio playback for AI responses

## Setup

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

```bash
# Install dependencies
npm install
```

### Running the Development Server

```bash
# Start the development server
npm start
```

The app will be available at [http://localhost:3000](http://localhost:3000).

The page will reload automatically when you make edits.

### Building for Production

```bash
# Build the app for production
npm run build
```

The production build will be created in the `dist` folder.
