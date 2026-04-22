from fastapi import APIRouter, File, UploadFile

from app.models.schemas import ResumeUploadResponse
from app.services.rag_service import rag_service

router = APIRouter(tags=["resume"])


@router.post("/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(file: UploadFile = File(...)) -> ResumeUploadResponse:
    result = await rag_service.ingest_resume(file)
    return ResumeUploadResponse(**result)

