from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_CANDIDATES = [
    ROOT_DIR / ".env",
    Path.cwd() / ".env",
]


class Settings(BaseSettings):
    hf_token: str = ""
    hf_provider: str = "hf-inference"
    hf_chat_model: str = "Qwen/Qwen2.5-72B-Instruct"
    hf_embedding_model: str = "thenlper/gte-large"
    hf_tts_model: str = ""
    hf_asr_model: str = "openai/whisper-large-v3"
    feedback_mode_default: str = "coaching"
    max_turns_per_session: int = 12
    upload_dir: str = "./uploads"
    vector_store_dir: str = "./data/faiss"
    frontend_origin: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=ENV_CANDIDATES,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
