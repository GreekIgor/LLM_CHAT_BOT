#!/usr/bin/env bash
# Start the Qwen OpenAI-compatible server on a Runpod Pod.
# Everything lives on the persistent volume mounted at /workspace, so after
# Stop/Start of the Pod it is enough to run: bash /workspace/tatek-qwen-server/start_server.sh
set -euo pipefail

SERVER_DIR=/workspace/tatek-qwen-server
ENV_DIR=/workspace/tatek-qwen-env
KEY_FILE="$SERVER_DIR/.model_api_key"
PORT="${TATEK_PORT:-19123}"

if [ ! -x "$ENV_DIR/bin/python" ]; then
    echo "Python environment $ENV_DIR is missing; install it first (see README)." >&2
    exit 1
fi

if [ ! -s "$KEY_FILE" ]; then
    echo "Model API key file $KEY_FILE is missing; put LLM_API_KEY from .env there." >&2
    exit 1
fi

if ss -lptn "sport = :$PORT" | grep -q LISTEN; then
    echo "Port $PORT is already in use:" >&2
    ss -lptn "sport = :$PORT" >&2
    exit 1
fi

nohup env \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/workspace/hf_cache \
    HF_XET_HIGH_PERFORMANCE=1 \
    TATEK_MODEL_API_KEY="$(cat "$KEY_FILE")" \
    TATEK_SERVED_MODEL=tatek-qwen \
    TATEK_MAX_MODEL_TOKENS=8192 \
    "$ENV_DIR/bin/python" -m uvicorn qwen_openai_server:app \
    --app-dir "$SERVER_DIR" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --log-level info \
    > "$SERVER_DIR/server.log" 2>&1 < /dev/null &

echo "Started PID $! on port $PORT; log: $SERVER_DIR/server.log"
