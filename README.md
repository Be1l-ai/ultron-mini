# ultron-mini (Nanobot)

A lightweight, self-hosted AI agent API built with **FastAPI** and powered by any OpenAI-compatible LLM backend (e.g. a Hugging Face Inference Space). Nanobot exposes a simple REST interface so you can send tasks and get back results from a ReAct-style agent loop — with built-in tools for file I/O, shell execution, web search, and HTTP requests.

---

## Features

- **ReAct agent loop** — the agent thinks, calls tools, and iterates until the task is complete (or hits `MAX_STEPS`)
- **Multi-turn sessions** — pass a `session_id` to continue a conversation across multiple requests
- **Built-in tools**
  - `file_read` / `file_write` — read and write files on the server
  - `shell_exec` — run arbitrary shell commands with a configurable timeout
  - `web_search` — search the web via DuckDuckGo
  - `http_request` — make HTTP requests to any URL
- **Bearer-token auth** — all `/run` and `/session` endpoints require a shared secret
- **Ready for Render** — includes a `render.yaml` for one-click deployment

---

## Requirements

- Python 3.10+
- An OpenAI-compatible LLM backend (e.g. a Hugging Face Space running `text-generation-inference` or `vllm`)

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Be1l-ai/ultron-mini.git
cd ultron-mini
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

| Variable        | Required | Description                                                                 |
|-----------------|----------|-----------------------------------------------------------------------------|
| `BRAIN_URL`     | ✅        | Base URL of your OpenAI-compatible LLM backend (e.g. `https://your-space.hf.space`) |
| `BRAIN_SECRET`  | ✅        | API key / secret for the LLM backend                                        |
| `NANOBOT_SECRET`| ✅        | Shared bearer token used to authenticate calls to this API (default: `changeme`) |
| `MAX_STEPS`     | ❌        | Maximum ReAct loop iterations per request (default: `10`)                   |

Copy the example below and fill in your values:

```bash
export BRAIN_URL="https://your-space.hf.space"
export BRAIN_SECRET="your-hf-api-secret"
export NANOBOT_SECRET="your-own-strong-secret"
export MAX_STEPS=10
```

### 4. Run locally

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

---

## API Reference

### `GET /health`

Returns the health status of the service. No authentication required.

**Response:**
```json
{"status": "ok", "agent": "nanobot"}
```

---

### `POST /run`

Submit a task to the agent.

**Headers:**
```
Authorization: Bearer <NANOBOT_SECRET>
Content-Type: application/json
```

**Request body:**
```json
{
  "task": "Write a Python function that reverses a string.",
  "session_id": "optional-session-uuid"
}
```

**Response:**
```json
{
  "result": "Here is a Python function that reverses a string:\n\n```python\ndef reverse_string(s: str) -> str:\n    return s[::-1]\n```",
  "steps": 1,
  "session_id": "optional-session-uuid"
}
```

---

### `DELETE /session/{session_id}`

Clear the stored conversation history for a session.

**Headers:**
```
Authorization: Bearer <NANOBOT_SECRET>
```

**Response:**
```json
{"cleared": "your-session-uuid"}
```

---

## Deployment on Render

The repository includes a `render.yaml` for zero-config deployment:

1. Fork this repository
2. Go to [Render](https://render.com) → **New** → **Blueprint**
3. Connect your fork
4. Set the required environment variables (`BRAIN_URL`, `BRAIN_SECRET`, `NANOBOT_SECRET`) in the Render dashboard
5. Deploy

---

## Project Structure

```
ultron-mini/
├── main.py          # FastAPI app, routes, auth, session management
├── agent.py         # ReAct agent loop (talks to the LLM brain)
├── tools.py         # Tool implementations + OpenAI-style tool schemas
├── requirements.txt # Python dependencies
└── render.yaml      # Render deployment config
```

---

## License

MIT
