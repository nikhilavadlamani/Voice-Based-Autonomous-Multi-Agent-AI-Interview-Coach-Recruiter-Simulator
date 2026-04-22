from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1"
    openai_embedding_model: str = "text-embedding-3-large"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_whisper_model: str = "whisper-1"
    elevenlabs_api_key: str = ""
    hr_voice: str = "alloy"
    technical_voice: str = "echo"
    hiring_manager_voice: str = "fable"
    feedback_voice: str = "nova"
    feedback_mode_default: str = "coaching"
    max_turns_per_session: int = 12
    upload_dir: str = "./uploads"
    vector_store_dir: str = "./data/faiss"
    frontend_origin: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

