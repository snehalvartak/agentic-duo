# `Agentic Duo`'s OSDC AI 2025 Agentic AI Hackathon Submission

<div align="center">
  <img src="images/osdc-agentic-ai-hackathon.png" alt="OSDC 2025 Agentic AI App Hackathon" />
</div>

Hello! We are **Agentic Duo** 👋🏾. Our team is proud to introduce you to our submission Slidekick - Your A.I Presentation Companion.

### What is Slidekick?

Slidekick is an AI-powered presentation companion that enables voice-controlled slide navigation. Using Google's Gemini Live API, it processes real-time audio streams to understand natural voice commands and automatically navigate through your presentation slides. Simply speak commands like "next slide" or "go to slide 5" and Slidekick handles the rest. The system converts markdown files to Reveal.js presentations and provides a seamless, hands-free presentation experience.


## 📂 Folder Layout

Our solution is split between backend and frontend with the following general layout:

```
agentic-duo/
├── src/
│   ├── backend/
│   │   ├── main.py
│   │   ├── pyproject.toml
│   │   ├── src/slidekick/        # Core backend modules
│   │   ├── tests/                # Backend tests
│   │   ├── playground/           # Sample scripts
│   │   ├── public/               # Static files & uploads
│   │   └── logs/                 # Application logs
│   │
│   └── frontend/
│       ├── src/
│       │   ├── components/       # React components
│       │   ├── types/            # TypeScript types
│       │   ├── App.tsx
│       │   └── index.tsx
│       ├── public/               # Static assets
│       ├── dist/                 # Build output
│       ├── package.json
│       └── vite.config.ts
│
├── demo_slide_decks/             # Sample slide decks to try out
├── images/
└── README.md
```

## How to Get Started

To get started with Slidekick, please refer to the setup instructions in the respective README files:

- **Backend Setup**: See [`src/backend/README.md`](src/backend/README.md) for installation and running instructions
- **Frontend Setup**: See [`src/frontend/README.md`](src/frontend/README.md) for installation and running instructions

> **💡 Tip**: It's best to run the backend and frontend in separate terminals side by side. This can be done easily in VS Code-like IDEs by splitting the terminal view, allowing you to monitor both services simultaneously.


## 📋 Submission Checklist

- [x] `src/` folder contains main code logic with some basic tests
- [x] `ARCHITECTURE.md` contains a clear diagram sketch and explanation  
- [x] `EXPLANATION.md` covers planning, tool use, memory, and limitations  
- [x] `DEMO.md` links to a 3–5 min video with timestamped highlights  


## 🏅 Judging Criteria

- **Technical Excellence**  
  This criterion evaluates the robustness, functionality, and overall quality of the technical implementation. Judges will assess the code's efficiency, the absence of critical bugs, and the successful execution of the project's core features.

- **Solution Architecture & Documentation**  
  This focuses on the clarity, maintainability, and thoughtful design of the project's architecture. This includes assessing the organization and readability of the codebase, as well as the comprehensiveness and conciseness of documentation (e.g., GitHub README, inline comments) that enables others to understand and potentially reproduce or extend the solution.

- **Innovative Gemini Integration**  
  This criterion specifically assesses how effectively and creatively the Google Gemini API has been incorporated into the solution. Judges will look for novel applications, efficient use of Gemini's capabilities, and the impact it has on the project's functionality or user experience. You are welcome to use additional Google products.

- **Societal Impact & Novelty**  
  This evaluates the project's potential to address a meaningful problem, contribute positively to society, or offer a genuinely innovative and unique solution. Judges will consider the originality of the idea, its potential real‑world applicability, and its ability to solve a challenge in a new or impactful way.


