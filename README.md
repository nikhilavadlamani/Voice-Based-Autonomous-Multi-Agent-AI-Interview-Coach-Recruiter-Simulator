# Voice-Based Autonomous Multi-Agent AI Interview Coach

This project is a resume-aware AI interviewer with real-time voice interaction, multi-agent interview orchestration, coaching feedback, and final score reports.

## Stack
- `frontend`: Next.js 15 + React 19
- `backend`: FastAPI + WebSockets
- `agent runtime`: LangGraph
- `resume retrieval`: FAISS
- `model providers`: Hugging Face Inference APIs for chat, embeddings, STT, and optional TTS

## Core Features
- Resume upload and indexing
- Resume-grounded interview questions
- HR, Technical, and Hiring Manager interviewer personas
- Voice mode with browser speech recognition and spoken responses
- Coaching and strict interview modes
- Final report with strengths, weaknesses, and roadmap

## Combined Deployment
This repo is configured for a single-service deployment:
- the Next.js frontend is exported as static files
- FastAPI serves the frontend, API, and WebSocket routes from one host
- Render can deploy the whole app from one `Dockerfile`

## Project Structure
```text
backend/
  app/
  requirements.txt
  runtime.txt
frontend/
  app/
  package.json
  next.config.ts
  .nvmrc
Dockerfile
.env.example
DEPLOYMENT.md
render.yaml
README.md
```

## Local Development

### Backend
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend
```powershell
cd frontend
npm install
$env:NEXT_PUBLIC_API_BASE="http://localhost:8000/api/v1"
npm run dev
```

## Environment Variables
Copy `.env.example` to `.env` for local development.

- `HF_TOKEN`
- `HF_PROVIDER`
- `HF_CHAT_MODEL`
- `HF_EMBEDDING_MODEL`
- `HF_TTS_MODEL`
- `HF_ASR_MODEL`
- `FEEDBACK_MODE_DEFAULT`
- `MAX_TURNS_PER_SESSION`
- `UPLOAD_DIR`
- `VECTOR_STORE_DIR`
- `FRONTEND_ORIGIN`

## Deployment
Deployment steps are documented in [DEPLOYMENT.md](DEPLOYMENT.md).

This repo includes deployment-ready support files:
- `Dockerfile`
- `render.yaml`
- `backend/runtime.txt`
- `frontend/.nvmrc`

## Final Hosted Shape
One Render URL will serve:
- frontend at `/`
- health route at `/health`
- REST API at `/api/v1/...`
- WebSocket interview route at `/api/v1/ws/interview/...`

## Smoke Test Checklist
- `GET /health` returns `200`
- home page loads
- resume upload works
- session creation works
- WebSocket interview flow connects
- voice mode works in Chrome or Edge
