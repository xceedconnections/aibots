from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "AIBOTS"
    app_env: str = "development"
    secret_key: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 1440
    admin_email: str = "admin@aibots.local"
    admin_password: str = "ChangeMe123!"

    database_url: str = "postgresql+asyncpg://aibots:aibots_secure_pass@postgres:5432/aibots"
    redis_url: str = "redis://redis:6379/0"

    cors_origins: str = "http://localhost:3000,http://localhost"

    ollama_base_url: str = "http://ollama:11434"
    llm_model: str = "qwen2.5:7b-instruct"
    llm_temperature: float = 0.2

    vicidial_url: str = "http://127.0.0.1/vicidial"
    vicidial_user: str = "6666"
    vicidial_pass: str = "api_pass"
    vicidial_source: str = "aibots"

    asterisk_ami_host: str = "127.0.0.1"
    asterisk_ami_port: int = 5038
    asterisk_ami_user: str = "aibots"
    asterisk_ami_secret: str = "ami_secret"

    max_question_retries: int = 2

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
