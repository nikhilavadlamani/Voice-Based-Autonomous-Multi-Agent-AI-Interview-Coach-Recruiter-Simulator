from __future__ import annotations

import io

from openai import OpenAI

from app.core.config import settings


class STTService:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    async def transcribe_bytes(self, audio_bytes: bytes, filename: str = "chunk.webm") -> str:
        if self.client is None:
            return f"[fallback transcript unavailable for {filename}; configure OPENAI_API_KEY for Whisper STT]"
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename
        result = self.client.audio.transcriptions.create(
            model=settings.openai_whisper_model,
            file=audio_file,
        )
        return result.text


stt_service = STTService()
