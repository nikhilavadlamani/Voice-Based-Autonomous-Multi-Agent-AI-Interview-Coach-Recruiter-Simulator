# Deployment Guide

## Recommended Deployment
This project is now configured for a single-service deployment:
- `frontend` is built as a static export
- `backend` serves the exported frontend, REST API, and WebSocket routes
- the whole app runs behind one Render service and one URL

## What To Commit To GitHub
- Commit the source code, `README.md`, `.env.example`, `Dockerfile`, `render.yaml`, `backend/runtime.txt`, and `frontend/.nvmrc`.
- Do not commit `.env`, `uploads/`, `data/faiss/`, `.next/`, `frontend/out/`, `node_modules/`, or log files.

## Required Environment Variables
Set these in Render, not in Git.

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

## One-Service Deploy On Render
This repo includes:
- `Dockerfile`
- `render.yaml`

### Steps
1. Push the repo to GitHub.
2. Rotate your exposed Hugging Face token first.
3. In Render, choose `New +` -> `Blueprint`.
4. Select your GitHub repository.
5. Render will detect `render.yaml` and create one service:
   - `interview-agent`
6. Set the secret env vars:
   - `HF_TOKEN`
   - `HF_TTS_MODEL` if you want provider-side TTS
7. Set `FRONTEND_ORIGIN` to your final Render URL, for example:
   - `https://interview-agent.onrender.com`
8. Deploy.

## Final URL Shape
You will get one website URL like:
- `https://interview-agent.onrender.com`

That single URL will serve:
- the frontend UI at `/`
- the health endpoint at `/health`
- the backend API at `/api/v1/...`
- the interview WebSocket at `/api/v1/ws/interview/...`

## Local Pre-Deploy Checks

### Backend
```powershell
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend
```powershell
cd frontend
npm ci
npm run build
```

## Smoke Test After Deploy
Check these:
- home page loads
- `GET /health` returns `200`
- resume upload works
- session creation works
- WebSocket interview flow connects
- voice mode works in Chrome or Edge

## Notes
- If `HF_TTS_MODEL` is blank, the app falls back to browser speech synthesis when available.
- Uploaded resumes and FAISS indexes are stored on the service filesystem by default.
- On Render free/ephemeral storage, uploaded data will not be durable across rebuilds or redeploys.
- For production durability, move uploads and vector data to persistent storage.
