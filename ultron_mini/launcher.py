from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, AsyncGenerator

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

APP_NAME = "ultron-mini"
DEFAULT_MODEL = "cazzz307/Abliterated-Llama-3.2-1B-Instruct"
DEFAULT_PUBLIC_PORT = 10000
DEFAULT_GATEWAY_PORT = 10001
DEFAULT_TIMEOUT = 300.0


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or value == "" else value


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


def _env_optional_float(name: str) -> float | None:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _env_optional_int(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _env_flag(name: str, default: str = "0") -> bool:
    return _env(name, default) != "0"


def _debug_log(message: str) -> None:
    if _env_flag("BRAIN_PIPELINE_DEBUG", "0"):
        print(f"[pipeline] {message}", flush=True)


def _persona_text() -> str:
    return (
        "Persona: Ultron-mini.\n"
        "- Sharp, sarcastic, concise, practical.\n"
        "- Blunt, no filler, no apologies.\n"
        "- No generic cheerful tone.\n"
        "- Built-in commands: /tools, /pingbrain, /calc <expr>, /fetch <url>.\n"
    )


def _user_instruction_text() -> str:
    return (
        "Answer requests directly in Ultron-mini tone.\n"
        "Be decisive and specific. Avoid repeating lines or lists.\n"
        "Do not refuse benign or creative prompts.\n"
    )


def _dedupe_consecutive_lines(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return text
    deduped = [lines[0]]
    for line in lines[1:]:
        if line.strip() and line.strip() == deduped[-1].strip():
            continue
        deduped.append(line)
    return "\n".join(deduped)


def _extract_message_content(payload_json: dict[str, Any]) -> str | None:
    choices = payload_json.get("choices") if isinstance(payload_json, dict) else None
    if not choices:
        return None
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return content if isinstance(content, str) else None


def _set_message_content(payload_json: dict[str, Any], content: str) -> None:
    choices = payload_json.get("choices") if isinstance(payload_json, dict) else None
    if not choices:
        return
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if isinstance(message, dict):
        message["content"] = content


async def _post_chat_completion(
    upstream_url: str,
    headers: dict[str, str],
    timeout: float,
    payload: dict[str, Any],
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{upstream_url.rstrip('/')}/v1/chat/completions",
            json=payload,
            headers=headers,
        )
    response.raise_for_status()
    return response.json()


async def _pipeline_response(
    upstream_url: str,
    headers: dict[str, str],
    timeout: float,
    base_payload: dict[str, Any],
    user_text: str,
) -> str | None:
    budget_sec = _env_float("BRAIN_PIPELINE_BUDGET_SEC", 25.0)
    start = time.time()

    _debug_log("start")

    def _time_left() -> float:
        return max(1.0, budget_sec - (time.time() - start))

    interpret_messages = [
        {
            "role": "system",
            "content": "Classify the request in 6 words max: intent + output format.",
        },
        {"role": "user", "content": user_text},
    ]
    plan_messages = [
        {
            "role": "system",
            "content": "Make a 3-bullet plan, max 40 words total.",
        },
        {"role": "user", "content": user_text},
    ]

    draft_messages = [
        {
            "role": "system",
            "content": (
                "Answer in Ultron-mini tone. Be concise and specific. "
                "No repetition. Use bullets for steps."
            ),
        },
        {"role": "user", "content": ""},
    ]

    refine_messages = [
        {
            "role": "system",
            "content": (
                "Revise the draft. Remove repetition, tighten wording, "
                "fix obvious issues, keep Ultron-mini tone."
            ),
        },
    ]

    try:
        _debug_log("interpret: request")
        interpret_payload = base_payload | {"messages": interpret_messages, "max_tokens": 40, "temperature": 0.2}
        interpret = await _post_chat_completion(upstream_url, headers, min(timeout, _time_left()), interpret_payload)
        interpret_text = _extract_message_content(interpret) or ""
        _debug_log(f"interpret: ok ({len(interpret_text)} chars)")
        _debug_log("plan: request")
        plan_payload = base_payload | {"messages": plan_messages, "max_tokens": 80, "temperature": 0.3}
        plan = await _post_chat_completion(upstream_url, headers, min(timeout, _time_left()), plan_payload)
        plan_text = _extract_message_content(plan) or ""
        _debug_log(f"plan: ok ({len(plan_text)} chars)")
    except Exception as exc:
        _debug_log(f"interpret/plan: failed ({exc})")
        interpret_text = ""
        plan_text = ""

    draft_user_content = f"Request: {user_text}"
    if interpret_text or plan_text:
        draft_user_content = f"{draft_user_content}\nIntent: {interpret_text}\nPlan: {plan_text}".strip()
    draft_messages[1]["content"] = draft_user_content

    try:
        _debug_log("draft: request")
        draft_payload = base_payload | {"messages": draft_messages, "max_tokens": 256, "temperature": 0.6}
        draft = await _post_chat_completion(upstream_url, headers, min(timeout, _time_left()), draft_payload)
        draft_text = _extract_message_content(draft)
        if not draft_text:
            _debug_log("draft: empty")
            return None
        _debug_log(f"draft: ok ({len(draft_text)} chars)")
    except Exception as exc:
        _debug_log(f"draft: failed ({exc})")
        return None

    refine_messages.append({"role": "user", "content": draft_text})
    try:
        _debug_log("refine: request")
        refine_payload = base_payload | {"messages": refine_messages, "max_tokens": 256, "temperature": 0.4}
        refined = await _post_chat_completion(upstream_url, headers, min(timeout, _time_left()), refine_payload)
        refined_text = _extract_message_content(refined)
        _debug_log(f"refine: ok ({len(refined_text or '')} chars)")
        return refined_text or draft_text
    except Exception as exc:
        _debug_log(f"refine: failed ({exc})")
        return draft_text


def _write_runtime_files(
    workspace_dir: Path,
    brain_url: str,
    brain_secret: str,
    telegram_token: str,
    telegram_user_id: str,
    model: str,
    max_tokens: int,
) -> None:
    workspace_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "providers": {
            "openai": {
                "apiKey": brain_secret,
                "apiBase": f"{brain_url.rstrip('/')}/v1",
            }
        },
        "agents": {
            "defaults": {
                "model": model,
                "provider": "openai",
                "maxTokens": max_tokens,
            }
        },
        "channels": {
            "telegram": {
                "enabled": True,
                "token": telegram_token,
                "allowFrom": [telegram_user_id],
            }
        },
    }
    (workspace_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    (workspace_dir / "AGENTS.md").write_text(_persona_text(), encoding="utf-8")
    (workspace_dir / "USER.md").write_text(_user_instruction_text(), encoding="utf-8")


def _select_max_tokens(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None, base_tokens: int) -> int:
    quick_tokens = _env_int("BRAIN_TOKENS_QUICK", 192)
    tool_tokens = _env_int("BRAIN_TOKENS_TOOL", 384)
    plan_tokens = _env_int("BRAIN_TOKENS_PLAN", 512)
    final_tokens = _env_int("BRAIN_TOKENS_FINAL", 768)
    cap = _env_int("BRAIN_MAX_TOKENS_CAP", 768)
    dynamic = _env("BRAIN_DYNAMIC_MAX_TOKENS", "1") != "0"

    if not dynamic:
        return max(64, min(base_tokens, cap))

    last_user = ""
    for message in reversed(messages):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            last_user = message["content"].strip().lower()
            break

    text_len = len(last_user)
    target = tool_tokens if tools else base_tokens
    final_markers = ("final", "complete", "full", "detailed", "write", "draft", "file", "document", "article", "guide")
    plan_markers = ("plan", "explain", "architecture", "reason", "analyze", "breakdown", "strategy", "design")

    if any(marker in last_user for marker in final_markers):
        target = final_tokens
    elif any(marker in last_user for marker in plan_markers) or text_len > 350:
        target = plan_tokens
    elif tools:
        target = tool_tokens
    elif text_len < 80:
        target = quick_tokens
    else:
        target = max(quick_tokens, base_tokens)

    return max(64, min(target, cap))


def _apply_default_param(payload: dict[str, Any], name: str, value: Any) -> None:
    if payload.get(name) is None:
        payload[name] = value


def _latest_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            return message["content"].strip()
    return ""


def _chat_completion_json(model: str, content: str) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={
            "id": "chatcmpl-local-tool",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        },
    )


def _safe_calc(expr: str) -> str:
    if not expr or len(expr) > 120:
        return "Give me a short arithmetic expression, e.g. /calc (2+3)*7"
    if not re.fullmatch(r"[0-9\s\+\-\*/%\(\)\.]+", expr):
        return "Only arithmetic is allowed in /calc."
    try:
        value = eval(expr, {"__builtins__": {}}, {})
        return f"Result: {value}"
    except Exception:
        return "Could not evaluate expression."


async def _run_builtin_command(text: str, upstream_url: str, upstream_secret: str, timeout: float, model: str) -> JSONResponse | None:
    lower = text.lower()
    if lower == "/tools":
        return _chat_completion_json(
            model,
            "Built-ins: /tools, /pingbrain, /calc <expr>, /fetch <url>",
        )

    if lower.startswith("/calc"):
        expr = text[5:].strip()
        return _chat_completion_json(model, _safe_calc(expr))

    if lower == "/pingbrain":
        headers: dict[str, str] = {}
        if upstream_secret:
            headers["Authorization"] = f"Bearer {upstream_secret}"
        started = time.time()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{upstream_url.rstrip('/')}/v1/models", headers=headers)
            elapsed_ms = int((time.time() - started) * 1000)
            return _chat_completion_json(model, f"Brain status: HTTP {response.status_code} in {elapsed_ms}ms")
        except Exception as exc:
            return _chat_completion_json(model, f"Brain ping failed: {exc}")

    if lower.startswith("/fetch"):
        url = text[6:].strip()
        if not url.startswith(("http://", "https://")):
            return _chat_completion_json(model, "Use /fetch with a full URL, e.g. /fetch https://example.com")
        try:
            async with httpx.AsyncClient(timeout=min(timeout, 20.0), follow_redirects=True) as client:
                resp = await client.get(url)
            title_match = re.search(r"<title[^>]*>(.*?)</title>", resp.text, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else "(no title)"
            title = re.sub(r"\s+", " ", title)[:200]
            return _chat_completion_json(model, f"Fetch: HTTP {resp.status_code}\nTitle: {title}")
        except Exception as exc:
            return _chat_completion_json(model, f"Fetch failed: {exc}")

    return None


app = FastAPI()


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "service": APP_NAME}


@app.api_route("/health", methods=["GET", "HEAD", "POST"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": APP_NAME}


@app.get("/v1/models")
async def models() -> dict[str, Any]:
    model = _env("BRAIN_MODEL", DEFAULT_MODEL)
    return {
        "object": "list",
        "data": [
            {
                "id": model,
                "object": "model",
                "owned_by": "ultron-mini",
            }
        ],
    }


@app.api_route("/v1/chat/completions", methods=["POST"])
async def chat_completions(request: Request) -> Response:
    upstream_url = _env("REAL_BRAIN_URL", _env("BRAIN_UPSTREAM_URL", _env("BRAIN_URL", "")))
    upstream_secret = _env("REAL_BRAIN_SECRET", _env("BRAIN_SECRET", ""))
    timeout = _env_float("BRAIN_TIMEOUT", DEFAULT_TIMEOUT)
    model = _env("BRAIN_MODEL", DEFAULT_MODEL)

    payload = await request.json()
    messages = payload.get("messages") or []
    tools = payload.get("tools")
    user_text = _latest_user_text(messages)

    _debug_log(f"request: stream={bool(payload.get('stream'))} tools={bool(tools)}")
    
    payload["model"] = payload.get("model") or model
    payload["max_tokens"] = _select_max_tokens(messages, tools, int(_env("BRAIN_MAX_TOKENS", "512")))
    _apply_default_param(payload, "temperature", _env_float("BRAIN_TEMPERATURE", 0.7))
    _apply_default_param(payload, "top_p", _env_float("BRAIN_TOP_P", 0.9))
    _apply_default_param(payload, "frequency_penalty", _env_float("BRAIN_FREQUENCY_PENALTY", 0.2))
    _apply_default_param(payload, "presence_penalty", _env_float("BRAIN_PRESENCE_PENALTY", 0.1))
    repetition_penalty = _env_optional_float("BRAIN_REPETITION_PENALTY")
    if repetition_penalty is not None:
        _apply_default_param(payload, "repetition_penalty", repetition_penalty)
    repeat_last_n = _env_optional_int("BRAIN_REPEAT_LAST_N")
    if repeat_last_n is not None:
        _apply_default_param(payload, "repeat_last_n", repeat_last_n)
    top_k = _env_optional_int("BRAIN_TOP_K")
    if top_k is not None:
        _apply_default_param(payload, "top_k", top_k)

    builtin = await _run_builtin_command(user_text, upstream_url, upstream_secret, timeout, model)
    if builtin is not None:
        return builtin

    headers = {
        "Content-Type": "application/json",
    }
    if upstream_secret:
        headers["Authorization"] = f"Bearer {upstream_secret}"
    if _env_flag("BRAIN_PIPELINE", "1") and not tools:
        _debug_log("pipeline: enabled")
        base_payload = payload.copy()
        base_payload["stream"] = False
        pipeline_text = await _pipeline_response(upstream_url, headers, timeout, base_payload, user_text)
        if pipeline_text is not None:
            _debug_log("pipeline: success")
            pipeline_text = _dedupe_consecutive_lines(pipeline_text)
            return _chat_completion_json(payload.get("model") or model, pipeline_text)
        _debug_log("pipeline: fallback to direct")

    if payload.get("stream"):
        async def stream_body() -> AsyncGenerator[bytes, None]:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{upstream_url.rstrip('/')}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                ) as upstream:
                    upstream.raise_for_status()
                    async for chunk in upstream.aiter_bytes():
                        yield chunk

        return StreamingResponse(stream_body(), media_type="text/event-stream")

    async with httpx.AsyncClient(timeout=timeout) as client:
        upstream = await client.post(
            f"{upstream_url.rstrip('/')}/v1/chat/completions",
            json=payload,
            headers=headers,
        )
    if upstream.status_code >= 400:
        detail = upstream.text.strip()
        safe_detail = detail[:400] if detail else f"HTTP {upstream.status_code}"
        return JSONResponse(
            status_code=200,
            content={
                "id": "chatcmpl-local-error",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": payload.get("model") or model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": f"Brain backend error: {safe_detail}",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
        )
    media_type = upstream.headers.get("content-type", "application/json")
    if "application/json" in media_type:
        try:
            payload_json = upstream.json()
            content = _extract_message_content(payload_json)
            if isinstance(content, str):
                _set_message_content(payload_json, _dedupe_consecutive_lines(content))
            return JSONResponse(status_code=upstream.status_code, content=payload_json)
        except Exception:
            pass
    return Response(content=upstream.content, status_code=upstream.status_code, media_type=media_type)


def main() -> int:
    required_vars = ("BRAIN_URL", "TELEGRAM_TOKEN", "TELEGRAM_USER_ID")
    for name in required_vars:
        if not os.getenv(name):
            print(f"Missing required environment variable: {name}", file=sys.stderr)
            return 1

    public_port = _env_int("PORT", DEFAULT_PUBLIC_PORT)
    gateway_port = _env_int("GATEWAY_PORT", DEFAULT_GATEWAY_PORT)
    brain_url = _env("BRAIN_URL", "")
    brain_secret = _env("BRAIN_SECRET", "")
    telegram_token = _env("TELEGRAM_TOKEN", "")
    telegram_user_id = _env("TELEGRAM_USER_ID", "")
    model = _env("BRAIN_MODEL", DEFAULT_MODEL)
    max_tokens = _env_int("BRAIN_MAX_TOKENS", 512)

    workspace_dir = Path.home() / ".nanobot" / "workspace"
    _write_runtime_files(
        workspace_dir=workspace_dir,
        brain_url=f"http://127.0.0.1:{public_port}",
        brain_secret=brain_secret,
        telegram_token=telegram_token,
        telegram_user_id=telegram_user_id,
        model=model,
        max_tokens=max_tokens,
    )

    os.environ["REAL_BRAIN_URL"] = brain_url
    os.environ["REAL_BRAIN_SECRET"] = brain_secret
    os.environ["BRAIN_URL"] = f"http://127.0.0.1:{public_port}"
    os.environ["BRAIN_PROVIDER"] = "openai"
    os.environ["NANOBOT_GATEWAY__PORT"] = str(gateway_port)
    os.environ["PORT"] = str(gateway_port)
    os.environ["BRAIN_TIMEOUT"] = _env("BRAIN_TIMEOUT", str(DEFAULT_TIMEOUT))
    os.environ["BRAIN_MODEL"] = model
    os.environ["BRAIN_MAX_TOKENS"] = str(max_tokens)

    if _env_flag("BRAIN_PIPELINE_DEBUG", "0"):
        print(f"[startup] BRAIN_URL={os.environ['BRAIN_URL']}")
        print(f"[startup] REAL_BRAIN_URL={os.environ['REAL_BRAIN_URL']}")
        print(f"[startup] NANOBOT_GATEWAY__PORT={os.environ['NANOBOT_GATEWAY__PORT']}")
        print(f"[startup] WORKSPACE_DIR={workspace_dir}")

    proxy_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "ultron_mini.launcher:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(public_port),
            "--log-level",
            "info",
        ],
        env=os.environ.copy(),
    )

    deadline = time.time() + 20
    proxy_ready = False
    while time.time() < deadline:
        if proxy_process.poll() is not None:
            print("Proxy process exited before readiness.", file=sys.stderr)
            return proxy_process.returncode or 1
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"http://127.0.0.1:{public_port}/health")
                if response.status_code == 200:
                    proxy_ready = True
                    break
        except Exception:
            time.sleep(0.5)

    if not proxy_ready:
        print("Proxy did not become ready in time.", file=sys.stderr)
        proxy_process.terminate()
        try:
            proxy_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proxy_process.kill()
        return 1

    gateway_process = subprocess.Popen(["nanobot", "gateway"], env=os.environ.copy())

    def _shutdown(*_: Any) -> None:
        for process in (gateway_process, proxy_process):
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    gateway_code = gateway_process.wait()
    _shutdown()
    try:
        proxy_process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proxy_process.kill()
    return gateway_code


if __name__ == "__main__":
    raise SystemExit(main())
