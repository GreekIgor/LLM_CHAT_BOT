"""Minimal OpenAI-compatible text chat API for Qwen3-VL on a Runpod Pod."""

import os
import time
import uuid
from contextlib import asynccontextmanager
from threading import Lock
from typing import Any

import torch
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoProcessor, Qwen3VLForConditionalGeneration


MODEL_ID = os.getenv("TATEK_MODEL_ID", "Qwen/Qwen3-VL-8B-Instruct")
SERVED_MODEL_NAME = os.getenv("TATEK_SERVED_MODEL", "tatek-qwen")
MODEL_API_KEY = os.getenv("TATEK_MODEL_API_KEY", "")
MAX_MODEL_TOKENS = int(os.getenv("TATEK_MAX_MODEL_TOKENS", "8192"))

model: Qwen3VLForConditionalGeneration | None = None
processor: AutoProcessor | None = None
generation_lock = Lock()


class ChatMessage(BaseModel):
    role: str
    content: str | list[dict[str, Any]]


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    max_tokens: int = Field(default=512, ge=1, le=2048)
    temperature: float = Field(default=0.1, ge=0, le=2)


def require_api_key(authorization: str | None) -> None:
    if MODEL_API_KEY and authorization != f"Bearer {MODEL_API_KEY}":
        raise HTTPException(status_code=401, detail="Invalid model API key")


def message_content_to_text(content: str | list[dict[str, Any]]) -> str:
    if isinstance(content, str):
        return content
    text_parts = [str(item.get("text", "")) for item in content if item.get("type") == "text"]
    if not text_parts:
        raise HTTPException(status_code=400, detail="Only text message content is supported by this endpoint")
    return "\n".join(text_parts)


def generate_response(request: ChatCompletionRequest) -> str:
    if model is None or processor is None:
        raise HTTPException(status_code=503, detail="Model is still loading")

    messages = [
        {
            "role": message.role,
            "content": [{"type": "text", "text": message_content_to_text(message.content)}],
        }
        for message in request.messages
    ]
    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)
    do_sample = request.temperature > 0
    generation_options: dict[str, Any] = {
        "max_new_tokens": request.max_tokens,
        "do_sample": do_sample,
    }
    if do_sample:
        generation_options["temperature"] = request.temperature
    with generation_lock, torch.inference_mode():
        generated = model.generate(**inputs, **generation_options)
    prompt_tokens = inputs["input_ids"].shape[1]
    answer_tokens = generated[:, prompt_tokens:]
    return processor.batch_decode(answer_tokens, skip_special_tokens=True)[0].strip()


@asynccontextmanager
async def lifespan(_: FastAPI):
    global model, processor
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for the Qwen server")
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        MODEL_ID,
        dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
    ).eval().cuda()
    yield


app = FastAPI(title="TATEK Qwen API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok" if model is not None else "loading", "model": SERVED_MODEL_NAME}


@app.get("/v1/models")
def list_models(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(authorization)
    return {
        "object": "list",
        "data": [{"id": SERVED_MODEL_NAME, "object": "model", "created": 0, "owned_by": "tatek"}],
    }


@app.post("/v1/chat/completions")
def chat_completions(
    request: ChatCompletionRequest, authorization: str | None = Header(default=None)
) -> dict[str, Any]:
    require_api_key(authorization)
    if request.model != SERVED_MODEL_NAME:
        raise HTTPException(status_code=404, detail=f"Model '{request.model}' is not available")
    started_at = time.monotonic()
    answer = generate_response(request)
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": SERVED_MODEL_NAME,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "system_fingerprint": f"generation-{time.monotonic() - started_at:.3f}s",
    }