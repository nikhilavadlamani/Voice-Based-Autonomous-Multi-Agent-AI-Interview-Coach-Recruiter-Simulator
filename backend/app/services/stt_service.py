from __future__ import annotations

from app.core.config import settings
from app.services.hf_service import hf_service


class STTService:
    async def transcribe_bytes(self, audio_bytes: bytes, filename: str = "chunk.webm") -> str:
        if not hf_service.is_enabled():
            return f"[fallback transcript unavailable for {filename}; configure HF_TOKEN for Hugging Face ASR]"
        try:
            result = hf_service.client.automatic_speech_recognition(
                audio=audio_bytes,
                model=settings.hf_asr_model or None,
            )
            if hasattr(result, "text"):
                return result.text
            return str(result)
        except Exception:
            return f"[speech transcription unavailable for {filename}; Hugging Face ASR request failed]"


stt_service = STTService()
