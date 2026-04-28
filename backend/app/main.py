from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.resume import router as resume_router
from app.api.routes.sessions import router as session_router
from app.core.config import settings
from app.services.rag_service import rag_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    rag_service.ensure_directories()
    yield


app = FastAPI(
    title="Voice-Based Autonomous Multi-Agent AI Interview Coach & Recruiter Simulator",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": app.title}


app.include_router(resume_router, prefix="/api/v1")
app.include_router(session_router, prefix="/api/v1")

frontend_out_dir = Path(__file__).resolve().parents[3] / "frontend" / "out"
if frontend_out_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_out_dir, html=True), name="frontend")
