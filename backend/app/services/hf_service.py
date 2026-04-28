from __future__ import annotations

from huggingface_hub import InferenceClient

from app.core.config import settings


class HuggingFaceService:
    def __init__(self) -> None:
        self.client = (
            InferenceClient(provider=settings.hf_provider, api_key=settings.hf_token)
            if settings.hf_token
            else None
        )

    def is_enabled(self) -> bool:
        return self.client is not None


hf_service = HuggingFaceService()

