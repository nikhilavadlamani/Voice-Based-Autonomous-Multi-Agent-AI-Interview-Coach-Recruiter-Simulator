from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import UploadFile

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.core.config import settings


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


class RagService:
    def __init__(self) -> None:
        self.upload_dir = Path(settings.upload_dir)
        self.vector_dir = Path(settings.vector_store_dir)

    def ensure_directories(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.vector_dir.mkdir(parents=True, exist_ok=True)

    def _embeddings(self) -> Embeddings:
        if settings.openai_api_key:
            return OpenAIEmbeddings(
                api_key=settings.openai_api_key,
                model=settings.openai_embedding_model,
            )
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
        vectorstore.save_local(str(self.vector_dir / candidate_id))
        summary = " ".join(text.split()[:80])
        return {
            "candidate_id": candidate_id,
            "filename": file.filename or "resume.pdf",
            "chunks_indexed": len(chunks),
            "extracted_summary": summary,
        }

    def retrieve_context(self, candidate_id: str, query: str) -> str:
        path = self.vector_dir / candidate_id
        if not path.exists():
            return ""
        vectorstore = FAISS.load_local(
            str(path),
            self._embeddings(),
            allow_dangerous_deserialization=True,
        )
        docs = vectorstore.similarity_search(query, k=4)
        return "\n".join(doc.page_content for doc in docs)

    def _extract_text(self, path: Path) -> str:
        if path.suffix.lower() == ".pdf":
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        return path.read_text(encoding="utf-8", errors="ignore")


rag_service = RagService()
