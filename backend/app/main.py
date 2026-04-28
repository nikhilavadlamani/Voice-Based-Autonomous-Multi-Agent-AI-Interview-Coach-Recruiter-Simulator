from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
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

frontend_out_dir = Path(__file__).resolve().parents[2] / "frontend" / "out"
frontend_index_file = frontend_out_dir / "index.html"
frontend_next_dir = frontend_out_dir / "_next"

if frontend_next_dir.exists():
    app.mount("/_next", StaticFiles(directory=frontend_next_dir), name="frontend-next")


@app.get("/", include_in_schema=False)
async def serve_frontend_root():
    if frontend_index_file.exists():
        return FileResponse(frontend_index_file)
    return {"detail": "Frontend build not found"}


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend_app(full_path: str):
    if full_path.startswith("api/") or full_path == "health":
        return {"detail": "Not Found"}

    target = frontend_out_dir / full_path
    if target.is_file():
        return FileResponse(target)

    if frontend_index_file.exists():
        return FileResponse(frontend_index_file)

    return {"detail": "Frontend build not found"}
