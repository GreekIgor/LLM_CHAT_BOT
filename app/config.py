from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "TATEK AI Assistant"
    app_env: str = "development"
    admin_token: str = ""
    data_dir: Path = Path("data")
# Возможность переключения между локальным ollama и runpod
    llm_provider: Literal["ollama", "runpod", "runpod_pod", "openai_compatible"] = "ollama"
    ollama_base_url: str = "http://ollama:11434/v1"
    llm_model: str = ""
    llm_api_key: str = ""
    runpod_api_key: str = ""
    runpod_endpoint_id: str = ""
    runpod_pod_id: str = ""
    runpod_pod_port: int | None = None
    llm_base_url: str = ""

    milvus_uri: str = "http://localhost:19530"
    milvus_collection: str = "tatek_knowledge"

    corporate_api_base_url: str = "http://host.docker.internal:90"
    corporate_api_key: str = ""
    corporate_api_timeout_seconds: float = 15
    corporate_api_disconnections_path: str = "/api/disconnection/disconnections"
    corporate_api_technical_condition_path: str = "/api/technical_condition/save"
    corporate_api_subscriber_lookup_path: str = ""
    corporate_api_capacity_path: str = ""
    corporate_api_complaint_path: str = ""

    technical_condition_status_id: int | None = None
    technical_condition_object_id: int | None = None

    @field_validator("technical_condition_status_id", "technical_condition_object_id", mode="before")
    @classmethod
    def blank_ids_are_unset(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def resolved_llm_base_url(self) -> str:
        if self.llm_base_url:
            return self.llm_base_url.rstrip("/")
        if self.llm_provider == "ollama":
            return self.ollama_base_url.rstrip("/")
        if self.llm_provider == "runpod_pod" and self.runpod_pod_id and self.runpod_pod_port:
            return f"https://{self.runpod_pod_id}-{self.runpod_pod_port}.proxy.runpod.net/v1"
        if self.llm_provider == "runpod" and self.runpod_endpoint_id:
            return f"https://api.runpod.ai/v2/{self.runpod_endpoint_id}/openai/v1"
        return ""

    @property
    def resolved_llm_model(self) -> str:
        if self.llm_model:
            return self.llm_model
        return "qwen3-vl:8b" if self.llm_provider == "ollama" else "Qwen/Qwen3-VL-8B-Instruct"

    @property
    def resolved_llm_api_key(self) -> str:
        if self.llm_provider == "ollama":
            return "ollama"
        if self.llm_provider == "runpod_pod":
            return self.llm_api_key or "not-needed"
        return self.llm_api_key or self.runpod_api_key

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "tatek-assistant.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
