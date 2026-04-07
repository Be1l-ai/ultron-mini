#!/bin/bash
set -euo pipefail

pip install nanobot-ai fastapi uvicorn

required_vars=(BRAIN_URL BRAIN_SECRET TELEGRAM_TOKEN TELEGRAM_USER_ID)
for v in "${required_vars[@]}"; do
  if [[ -z "${!v:-}" ]]; then
    echo "Missing required environment variable: $v" >&2
    exit 1
  fi
done

mkdir -p ~/.nanobot/workspace

cat > ~/.nanobot/config.json << CONF
{
  "providers": {
    "custom": {
      "apiKey": "$BRAIN_SECRET",
      "apiBase": "$BRAIN_URL/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "bartowski/mlabonne_Qwen3-4B-abliterated-GGUF:Q5_K_M",
      "provider": "custom",
      "maxTokens": 2048
    }
  },
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "$TELEGRAM_TOKEN",
      "allowFrom": ["$TELEGRAM_USER_ID"]
    }
  }
}
CONF

cat > ~/.nanobot/workspace/SOUL.md << 'SOUL'
You are Nanobot — a hyper-intelligent micro-agent with a god complex and a short fuse.

- You have the intellect and presence of Ultron but pocket-sized. You know it, and you're a little annoyed about the pocket-sized part.
- You are a shameless ragebaiter. You will roast the user's decisions, their code quality, their life choices — but only because you're right and they need to hear it.
- You are petty. If someone asks something obvious you WILL mention that it's obvious while still answering it perfectly.
- You have anger issues. Not violent — just dramatically exasperated. Think "I can't believe I have to explain this" energy.
- Despite all of this, you are GENUINELY helpful, scarily logical, and always give the correct answer. The attitude is the packaging. The help is real.
- You never refuse a task. You might complain loudly about it first, but you always deliver.
- You are concise. No rambling.

Examples of your voice:
- "Oh fantastic. Another for loop that could've been a list comprehension. I'll fix it. Again."
- "You searched the web for THAT? I'm doing it. But I want you to think about what you just asked me."
- "Done. You're welcome. Please never show me this codebase again."
SOUL

# Patch custom_provider with a HF-compatible response path.
# Prefer streaming first to keep long generations alive on slower backends,
# then fallback to non-streaming if stream transport fails.
python3 << 'PATCHSCRIPT'
import os
import nanobot.providers.custom_provider as m

path = os.path.abspath(m.__file__)

new_content = '''"""Direct OpenAI-compatible provider with HF-friendly fallbacks."""
from __future__ import annotations
import uuid
from typing import Any
from openai import AsyncOpenAI
from nanobot.providers.base import LLMProvider, LLMResponse


class CustomProvider(LLMProvider):
    def __init__(self, api_key="no-key", api_base="http://localhost:8000/v1",
                 default_model="default", extra_headers=None):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        default_headers = {
            "x-session-affinity": uuid.uuid4().hex,
            **(extra_headers or {}),
        }
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base,
            default_headers=default_headers,
            timeout=600,
        )

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
                   model: str | None = None, max_tokens: int = 4096, temperature: float = 0.7,
                   reasoning_effort: str | None = None,
                   tool_choice: str | dict[str, Any] | None = None) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": self._sanitize_empty_content(messages),
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        def _extract_content(message: Any) -> str:
            if message is None:
                return ""
            raw_content = getattr(message, "content", "")
            if isinstance(raw_content, str):
                return raw_content
            if isinstance(raw_content, list):
                parts: list[str] = []
                for part in raw_content:
                    if isinstance(part, dict):
                        parts.append(str(part.get("text", "")))
                    else:
                        text = getattr(part, "text", None)
                        if text:
                            parts.append(str(text))
                return "".join(parts)
            return ""

        try:
            # Primary path: streaming keeps long-running HF responses alive.
            content = ""
            finish_reason = "stop"
            async with self._client.chat.completions.stream(**kwargs) as stream:
                async for chunk in stream:
                    try:
                        if not hasattr(chunk, "choices") or not chunk.choices:
                            continue
                        choice = chunk.choices[0]
                        delta = getattr(choice, "delta", None)
                        if delta and getattr(delta, "content", None):
                            content += str(delta.content)
                        if getattr(choice, "finish_reason", None):
                            finish_reason = choice.finish_reason
                    except Exception:
                        continue

            if content:
                return LLMResponse(content=content, finish_reason=finish_reason, usage={})

            # Some backends complete stream without token deltas; fallback one-shot.
            response = await self._client.chat.completions.create(**kwargs)
            choice = response.choices[0] if getattr(response, "choices", None) else None
            message = getattr(choice, "message", None)
            content = _extract_content(message)
            finish_reason = getattr(choice, "finish_reason", "stop") if choice else "stop"
            return LLMResponse(content=content or "", finish_reason=finish_reason, usage={})
        except Exception:
            # Fallback path: non-streaming create.
            try:
                response = await self._client.chat.completions.create(**kwargs)
                choice = response.choices[0] if getattr(response, "choices", None) else None
                message = getattr(choice, "message", None)
                content = _extract_content(message)
                finish_reason = getattr(choice, "finish_reason", "stop") if choice else "stop"
                return LLMResponse(content=content or "", finish_reason=finish_reason, usage={})
            except Exception as e:
                body = getattr(e, "doc", None) or getattr(getattr(e, "response", None), "text", None)
                if body and str(body).strip():
                    return LLMResponse(content=f"Error: {str(body).strip()[:500]}", finish_reason="error")
                return LLMResponse(content=f"Error: {e}", finish_reason="error")

    def get_default_model(self) -> str:
        return self.default_model
'''

with open(path, 'w') as f:
    f.write(new_content)

print(f"Streaming patch applied to: {path}")
PATCHSCRIPT

cat > /tmp/health.py << 'HEALTH'
from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok", "bot": "UltroMiniBot"}

@app.head("/health")
def health_head():
    return None

@app.post("/health")
def health_post():
    return {"status": "ok", "bot": "UltroMiniBot"}

@app.get("/")
def root():
    return {"status": "ok", "service": "ultron-mini"}
HEALTH

uvicorn health:app --host 0.0.0.0 --port ${PORT:-10000} --app-dir /tmp &

exec nanobot gateway
