from typing import Literal

from pydantic import BaseModel, Field

#Схема данных для взаимодействия с чат-агентом и проверки состояния системы

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=80)


class Source(BaseModel):
    document: str
    excerpt: str


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    workflow: Literal["general", "outage", "technical_conditions", "complaint"] = "general"
    requires_confirmation: bool = False
    sources: list[Source] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    llm_configured: bool
    llm_provider: str
    llm_model: str
    corporate_api_configured: bool
    rag_ready: bool
