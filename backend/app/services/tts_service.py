from __future__ import annotations

import base64

from app.core.config import settings
from app.services.hf_service import hf_service


class TTSService:
    def synthesize(self, text: str, agent: str) -> str:
        if not hf_service.is_enabled():
            return ""
        try:
            audio_bytes = hf_service.client.text_to_speech(
                text=text,
                model=settings.hf_tts_model or None,
            )
            return base64.b64encode(audio_bytes).decode("utf-8")
        except Exception:
            return ""


tts_service = TTSService()
