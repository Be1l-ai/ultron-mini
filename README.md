# ultron-mini (Nanobot)

A self-hosted AI agent with a god complex and a short fuse. Powered by [nanobot-ai](https://pypi.org/project/nanobot-ai/) and an OpenAI-compatible LLM backend (Hugging Face Inference Space), delivered over **Telegram**. Deploy in one click on [Render](https://render.com).

---

## Features

- **nanobot-ai** — agent runtime and Telegram gateway
- **Local OpenAI proxy** — dynamic token sizing and timeout handling live in-repo
- **Telegram channel** — interact with your agent directly from Telegram
- **CPU-friendly defaults** — tuned for small local boxes and slower Hugging Face backends
- **Ready for Render** — includes a `render.yaml` for one-click deployment

---

## Requirements

- Python 3.10+
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
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

| Variable           | Required | Description                                                                          |
|--------------------|----------|--------------------------------------------------------------------------------------|
| `BRAIN_URL`        | ✅        | Base URL of your OpenAI-compatible LLM backend (e.g. `https://your-space.hf.space`) |
| `BRAIN_SECRET`     | ✅        | API key / secret for the LLM backend                                                 |
| `TELEGRAM_TOKEN`   | ✅        | Telegram bot token from @BotFather                                                   |
| `TELEGRAM_USER_ID` | ✅        | Your Telegram user ID — only this user can interact with the bot                     |

```bash
export BRAIN_URL="https://your-space.hf.space"
export BRAIN_SECRET="your-hf-api-secret"
export TELEGRAM_TOKEN="your-telegram-bot-token"
export TELEGRAM_USER_ID="your-telegram-user-id"
```

### 4. Run locally

```bash
bash start.sh
```

This writes a compact runtime config, starts the local OpenAI-compatible proxy, and launches the Telegram gateway.

---

## Deployment on Render

The repository includes a `render.yaml` for zero-config deployment:

1. Fork this repository
2. Go to [Render](https://render.com) → **New** → **Blueprint**
3. Connect your fork
4. Set the required environment variables (`BRAIN_URL`, `BRAIN_SECRET`, `TELEGRAM_TOKEN`, `TELEGRAM_USER_ID`) in the Render dashboard
5. Deploy

---

## Project Structure

```
ultron-mini/
├── start.sh               # Thin entrypoint to the launcher
├── ultron_mini/launcher.py # Local proxy, config writer, and process supervisor
├── tests/                  # Small regression tests for token policy and persona size
├── requirements.txt        # Pinned Python dependencies
└── render.yaml             # Render deployment config

The launcher writes only a tiny `AGENTS.md` persona file at runtime and keeps the Hugging Face backend behind a local OpenAI-compatible proxy, so nanobot never has to be patched in place.
```

---

## License

MIT
