from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from fastapi import UploadFile

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import numpy as np
from pypdf import PdfReader

from app.core.config import settings
from app.services.hf_service import hf_service


class LocalHashEmbeddings(Embeddings):
    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * 64
        for index, char in enumerate(text[:4000]):
            vector[index % 64] += (ord(char) % 31) / 31.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class HuggingFaceEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        try:
            result = hf_service.client.feature_extraction(
                text=text,
                model=settings.hf_embedding_model or None,
            )
            array = np.array(result, dtype=float)
            if array.ndim > 1:
                array = array.mean(axis=0)
            return array.astype(float).tolist()
        except Exception:
            return LocalHashEmbeddings().embed_query(text)


class RagService:
    def __init__(self) -> None:
        self.upload_dir = Path(settings.upload_dir)
        self.vector_dir = Path(settings.vector_store_dir)

    def ensure_directories(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.vector_dir.mkdir(parents=True, exist_ok=True)

    def _candidate_dir(self, candidate_id: str) -> Path:
        return self.vector_dir / candidate_id

    def _embeddings(self) -> Embeddings:
        if hf_service.is_enabled():
            return HuggingFaceEmbeddings()
        return LocalHashEmbeddings()

    async def ingest_resume(self, file: UploadFile) -> dict:
        self.ensure_directories()
        candidate_id = str(uuid.uuid4())
        target_path = self.upload_dir / f"{candidate_id}_{file.filename}"
        content = await file.read()
        target_path.write_bytes(content)

        text = self._extract_text(target_path)
        splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=120)
        chunks = splitter.split_text(text)
        docs = [Document(page_content=chunk, metadata={"candidate_id": candidate_id}) for chunk in chunks]
        vectorstore = FAISS.from_documents(docs, self._embeddings())
        candidate_dir = self._candidate_dir(candidate_id)
        vectorstore.save_local(str(candidate_dir))

        profile = self._build_profile(text)
        profile["filename"] = file.filename or "resume.pdf"
        profile["source_path"] = str(target_path)
        (candidate_dir / "profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")

        return {
            "candidate_id": candidate_id,
            "filename": file.filename or "resume.pdf",
            "chunks_indexed": len(chunks),
            "extracted_summary": profile["summary"],
            "resume_highlights": profile["highlights"],
        }

    def retrieve_context(self, candidate_id: str, query: str) -> str:
        path = self._candidate_dir(candidate_id)
        if not path.exists():
            return ""
        vectorstore = FAISS.load_local(
            str(path),
            self._embeddings(),
            allow_dangerous_deserialization=True,
        )
        docs = vectorstore.similarity_search(query, k=4)
        return "\n".join(doc.page_content for doc in docs)

    def get_profile(self, candidate_id: str) -> dict:
        profile_path = self._candidate_dir(candidate_id) / "profile.json"
        if not profile_path.exists():
            return {"summary": "", "highlights": [], "skills": []}
        try:
            return json.loads(profile_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"summary": "", "highlights": [], "skills": []}

    def _build_profile(self, text: str) -> dict:
        lines = [self._clean_line(line) for line in text.splitlines()]
        lines = [line for line in lines if line]
        summary = " ".join(text.split()[:90]).strip()

        section_keywords = {
            "experience": {"experience", "employment", "work history", "professional experience"},
            "projects": {"project", "projects"},
            "skills": {"skills", "technical skills", "technologies", "stack"},
            "education": {"education"},
        }
        current_section = ""
        section_lines: dict[str, list[str]] = {key: [] for key in section_keywords}

        for line in lines:
            normalized = line.lower().rstrip(":")
            matched_section = next(
                (section for section, aliases in section_keywords.items() if normalized in aliases),
                None,
            )
            if matched_section:
                current_section = matched_section
                continue
            if current_section in section_lines:
                section_lines[current_section].append(line)

        experience = self._pick_highlights(section_lines["experience"], limit=3)
        projects = self._pick_highlights(section_lines["projects"], limit=3)
        education = self._pick_highlights(section_lines["education"], limit=1)
        fallback_highlights = self._pick_highlights(lines, limit=4)
        highlights = (experience + projects + education)[:5] or fallback_highlights
        skills = self._extract_skills(section_lines["skills"] or lines)

        return {
            "summary": summary,
            "highlights": highlights,
            "skills": skills[:12],
        }

    def _pick_highlights(self, lines: list[str], limit: int) -> list[str]:
        highlights: list[str] = []
        for line in lines:
            lowered = line.lower()
            if len(line.split()) < 4:
                continue
            if lowered.endswith(":"):
                continue
            if line in highlights:
                continue
            highlights.append(line)
            if len(highlights) >= limit:
                break
        return highlights

    def _extract_skills(self, lines: list[str]) -> list[str]:
        skills: list[str] = []
        for line in lines:
            for part in line.replace("|", ",").replace("/", ",").split(","):
                skill = part.strip(" -:\t")
                if 1 < len(skill) <= 30 and skill.lower() not in {item.lower() for item in skills}:
                    skills.append(skill)
                if len(skills) >= 16:
                    return skills
        return skills

    def _clean_line(self, line: str) -> str:
        return " ".join(line.replace("\x00", " ").split()).strip(" -\t")

    def _extract_text(self, path: Path) -> str:
        if path.suffix.lower() == ".pdf":
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        return path.read_text(encoding="utf-8", errors="ignore")


rag_service = RagService()
