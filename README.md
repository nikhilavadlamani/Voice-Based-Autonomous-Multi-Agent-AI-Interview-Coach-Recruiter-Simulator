# Voice-Based Autonomous Multi-Agent AI Interview Coach & Recruiter Simulator

## 1. Project Overview
This project simulates an end-to-end hiring loop with autonomous interview agents, a planner-controlled decision system, resume-aware question generation, confidence scoring, and a real-time voice interaction layer. It is designed to look and feel like a production AI recruiting platform rather than a demo chatbot.

Core outcomes:
- Real-time speech-to-speech interview flow using Whisper-compatible STT, WebSockets, and OpenAI TTS
- LangGraph-based multi-agent orchestration with HR, Technical, Hiring Manager, Planner, and Feedback agents
- Resume-grounded personalization via FAISS retrieval
- Adaptive interview difficulty, coaching mode, interruption hooks, and final report generation

## 2. Architecture Design
### High-Level Architecture
```text
[Next.js Frontend]
  |- Resume upload UI
  |- Live transcript + audio playback
  |- WebSocket client for bidirectional interview events
  v
[FastAPI Backend]
  |- REST APIs for resume ingestion and session bootstrap
  |- WebSocket endpoint for live interview turns
  |- Session manager for memory, transcript, and agent state
  v
[LangGraph Multi-Agent Runtime]
  |- Confidence Agent node
  |- Scoring node
  |- Planner Agent node
  |- HR / Technical / Hiring Manager speaking nodes
  |- Feedback node
  |- Final report node
  v
[Intelligence Services]
  |- Whisper STT
  |- OpenAI / ElevenLabs TTS
  |- FAISS vector store for resume retrieval
  |- OpenAI LLM for question generation and planning
  v
[Storage]
  |- Resume uploads
  |- FAISS index per candidate
  |- In-memory session state, extensible to Redis/Postgres
```

### Engineering Decisions
- `FastAPI + WebSockets`: low-latency full-duplex messaging for live interviews and agent voice responses.
- `LangGraph`: explicit decision graph fits planner-driven control loops better than ad hoc chains.
- `FAISS`: local, cheap, and resume-friendly for retrieval without extra infrastructure in v1.
- `Next.js`: recruiter-friendly UI with room for dashboards, analytics, and auth later.
- `SessionManager`: isolates runtime state and makes it easy to move to Redis for horizontal scaling.

## 3. Agent Design
### Planner Agent
This is the control tower. It observes transcript state, scores, difficulty, and resume context, then decides:
- whether to ask a follow-up
- when to increase difficulty
- when to switch from HR to Technical to Hiring Manager
- when to inject coaching feedback
- when to end the interview and trigger final reporting

### HR Agent
Focus:
- communication quality
- story structure
- role motivation
- leadership and ownership

### Technical Agent
Focus:
- ML fundamentals
- production system design
- coding depth
- MLOps and tradeoffs

### Hiring Manager Agent
Focus:
- business judgment
- prioritization
- cross-functional leadership
- hire / no-hire signal synthesis

### Feedback Agent
Focus:
- real-time improvement suggestions
- answer tightening
- concise coaching during weak moments

### Confidence Detection Agent
Implemented as a scoring node that tracks:
- filler words
- answer length
- communication clarity
- confidence trend

## 4. Voice System Design
### Realtime Flow
```text
Candidate speaks
-> client captures audio / transcript
-> WebSocket event to FastAPI
-> Whisper transcription
-> LangGraph processes answer
-> selected agent generates next response
-> TTS synthesizes agent-specific voice
-> frontend plays audio and renders transcript
```

### Voice Design Choices
- Whisper-compatible STT keeps the stack portable and resume-aligned.
- TTS voice is chosen by agent role so HR, Technical, and Hiring Manager feel distinct.
- WebSockets let us stream partials later without reworking the contract.
- The current code supports text events immediately and includes the hook for audio chunk transcription.

### Interruption Handling
Recommended production rule:
- if answer duration exceeds threshold or token count crosses a ceiling, trigger an interrupt event
- Planner decides whether to ask for a concise answer, redirect, or move on
- Keep this on the backend to avoid trust issues with the client

## 5. Step-by-Step Implementation Plan
1. Upload and parse the candidate resume.
2. Chunk the resume and build a FAISS index with embeddings.
3. Create a live interview session with target role, interview mode, and focus areas.
4. Stream candidate input over WebSocket.
5. Run confidence and scoring nodes.
6. Planner selects the next speaking agent and difficulty.
7. Speaking agent generates the next question.
8. Feedback agent optionally appends coaching guidance.
9. TTS synthesizes the selected agent response.
10. Final report is generated when the Planner ends the loop.

## 6. Code Snippets (modular)
### LangGraph control loop
See [backend/app/agents/graph.py](backend/app/agents/graph.py) and [backend/app/agents/nodes.py](backend/app/agents/nodes.py).

Key behavior:
- confidence and scoring happen before planning
- planner selects the next active interviewer
- coaching mode routes through the feedback node
- final report is emitted once the planner sets `should_end`

### FastAPI WebSocket streaming
See [backend/app/api/routes/sessions.py](backend/app/api/routes/sessions.py).

This route:
- accepts `candidate_text` and `candidate_audio` events
- appends transcript memory
- invokes the graph
- synthesizes agent voice
- returns the final report when the interview closes

### Resume-grounded RAG
See [backend/app/services/rag_service.py](backend/app/services/rag_service.py).

This service:
- stores uploaded resumes
- extracts PDF or text content
- embeds and indexes chunks with FAISS
- retrieves candidate-specific context for personalized questioning

## 7. Folder Structure
```text
Interview Agent/
├─ backend/
│  ├─ app/
│  │  ├─ api/routes/
│  │  │  ├─ resume.py
│  │  │  └─ sessions.py
│  │  ├─ agents/
│  │  │  ├─ graph.py
│  │  │  ├─ nodes.py
│  │  │  ├─ prompts.py
│  │  │  └─ state.py
│  │  ├─ core/config.py
│  │  ├─ models/schemas.py
│  │  └─ services/
│  │     ├─ rag_service.py
│  │     ├─ scoring_service.py
│  │     ├─ session_manager.py
│  │     ├─ stt_service.py
│  │     └─ tts_service.py
│  ├─ requirements.txt
│  └─ app/main.py
├─ frontend/
│  ├─ app/
│  │  ├─ globals.css
│  │  ├─ layout.tsx
│  │  └─ page.tsx
│  ├─ package.json
│  ├─ tsconfig.json
│  └─ next-env.d.ts
├─ .env.example
└─ README.md
```

## 8. Deployment Guide
### Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd frontend
npm install
$env:NEXT_PUBLIC_API_BASE="http://localhost:8000/api/v1"
npm run dev
```

### Environment Variables
Use [.env.example](.env.example) and configure:
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_EMBEDDING_MODEL`
- `OPENAI_WHISPER_MODEL`
- `OPENAI_TTS_MODEL`
- `ELEVENLABS_API_KEY` if swapping TTS provider
- per-agent voice names
- `FRONTEND_ORIGIN`

### Scaling Considerations
- Move session state from memory to Redis.
- Persist transcripts and reports in Postgres.
- Put FAISS indexes behind a document service or replace with a managed vector DB.
- Add worker queues for long-running audio and report tasks.
- Stream partial transcription chunks instead of full-turn uploads.
- Add auth, rate limiting, and tenant isolation for real users.

## 9. Resume Bullet Points
- Built a real-time multi-agent AI interview simulator using LangGraph, FastAPI, WebSockets, Whisper STT, OpenAI TTS, and FAISS-based resume retrieval.
- Designed an autonomous Planner Agent that dynamically controlled round switching, adaptive difficulty, coaching interventions, and interview termination based on live candidate performance.
- Engineered a speech-to-speech recruiting workflow with role-specific interviewer personas, confidence scoring, transcript memory, and final hiring reports for HR and technical evaluation.
- Developed a Next.js front end for resume upload, live interview streaming, transcript visualization, and final scorecard review across strict and coaching interview modes.

## 10. Future Enhancements
- Add browser-side PCM streaming and server-side incremental Whisper decoding for lower latency.
- Use Redis Streams or Kafka for event-driven agent communication.
- Add code-editor interview rounds with sandboxed execution and rubric-based grading.
- Persist agent memory across sessions for longitudinal coaching.
- Add video sentiment analysis and richer prosody scoring.
- Introduce recruiter dashboards, candidate analytics, and team calibration views.
