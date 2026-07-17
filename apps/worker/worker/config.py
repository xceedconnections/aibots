from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://redis:6379/0"
    api_internal_url: str = "http://api:8000"
    ollama_base_url: str = "http://ollama:11434"
    whisper_model: str = "base.en"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    piper_model_path: str = "/models/piper/en_US-lessac-medium.onnx"
    piper_config_path: str = "/models/piper/en_US-lessac-medium.onnx.json"
    audio_sample_rate: int = 16000
    silence_timeout_ms: int = 1200
    max_concurrent_calls: int = 4
    simulate_mode: bool = True  # True until Asterisk RTP bridge is wired

    class Config:
        env_file = ".env"
        extra = "ignore"
        # Allow SIMULATE_MODE from environment
        populate_by_name = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
