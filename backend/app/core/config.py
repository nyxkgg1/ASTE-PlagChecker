from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FTER Plagiarism and AI Detection System"
    app_env: str = "development"
    debug: bool = True

    database_url: str

    upload_dir: str = "../uploads"
    model_dir: str = "../models"

    embedding_model_path: str = "../models/Qwen3-0.6B-Base"
    embedding_dimension: int = 1024

    secret_key: str
    response_encryption_key: str
    access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    ai_source_type: str = "DUMMY_LLAMA"
    ai_dummy_model_name: str = "llama"
    ai_source_database_url: str = ""
    ai_source_table: str = "ai_generated_content"
    ai_source_text_column: str = "generated_text"
    ai_source_id_column: str = "id"
    ai_source_metadata_column: str = "metadata"
    ai_source_search_limit: int = 10
    ai_source_min_similarity: float = 0.55
        # Local Ollama configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:4b"
    ollama_timeout_seconds: int = 120
    qwen_analysis_timeout_seconds: int = 300
    ollama_keep_alive: str = "10m"


settings = Settings()