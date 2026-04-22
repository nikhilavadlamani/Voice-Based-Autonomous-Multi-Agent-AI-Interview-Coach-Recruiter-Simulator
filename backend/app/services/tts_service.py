from __future__ import annotations

import base64

from openai import OpenAI

from app.core.config import settings


VOICE_BY_AGENT = {
    "hr": settings.hr_voice,
    "technical": settings.technical_voice,
    "hiring_manager": settings.hiring_manager_voice,
    "feedback": settings.feedback_voice,
}


class TTSService:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def synthesize(self, text: str, agent: str) -> str:
        if self.client is None:
            return ""
        response = self.client.audio.speech.create(
            model=settings.openai_tts_model,
            voice=VOICE_BY_AGENT.get(agent, settings.feedback_voice),
            input=text,
        )
        audio_bytes = response.read()
        return base64.b64encode(audio_bytes).decode("utf-8")


tts_service = TTSService()
