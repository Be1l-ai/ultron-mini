#!/bin/bash
pip install nanobot-ai fastapi uvicorn

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
      "model": "bartowski/mlabonne_Qwen3-14B-abliterated-GGUF:Q5_K_M",
      "provider": "custom",
      "maxTokens": 512
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

# Patch custom_provider to use streaming so responses actually come back
python3 << 'PATCHSCRIPT'
import os
import nanobot.providers.custom_provider as m

path = os.path.abspath(m.__file__)

new_content = '''"""Direct OpenAI-compatible provider — streaming enabled."""
from __future__ import annotations
import uuid
from typing import Any
import json_repair
from openai import AsyncOpenAI
from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


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
            "stream": True,
        }
        if tools:
            kwargs.update(tools=tools, tool_choice="none")
        try:
            content = ""
            finish_reason = "stop"
            tool_calls_raw = []
            async with self._client.chat.completions.stream(**kwargs) as stream:
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    delta = choice.delta
                    if delta and delta.content:
                        content += delta.content
                    if choice.finish_reason:
                        finish_reason = choice.finish_reason
            return LLMResponse(content=content or "", finish_reason=finish_reason, usage={})
        except Exception as e:
            body = getattr(e, "doc", None) or getattr(getattr(e, "response", None), "text", None)
            if body and body.strip():
                return LLMResponse(content=f"Error: {body.strip()[:500]}", finish_reason="error")
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
HEALTH

uvicorn health:app --host 0.0.0.0 --port ${PORT:-10000} --app-dir /tmp &

nanobot gateway
