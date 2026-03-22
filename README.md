# ultron-mini (Nanobot)

A self-hosted AI agent with a god complex and a short fuse. Powered by [nanobot-ai](https://pypi.org/project/nanobot-ai/) and an OpenAI-compatible LLM backend (Hugging Face Inference Space), delivered over **Telegram**. Deploy in one click on [Render](https://render.com).

---

## Features

- **nanobot-ai** — uses the `nanobot-ai` package for the agent runtime and gateway
- **Telegram channel** — interact with your agent directly from Telegram
- **Custom LLM backend** — points at any OpenAI-compatible API (e.g. a Hugging Face Space)
- **Custom personality** — ships with a snarky `SOUL.md` persona (Ultron, pocket-sized, perpetually annoyed)
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

This will install `nanobot-ai`, write the config and personality files, and start the Telegram gateway.

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
├── start.sh         # Installs nanobot-ai, writes config + SOUL.md, starts the gateway
├── requirements.txt # Python dependencies (nanobot-ai)
└── render.yaml      # Render deployment config
```

---

## License

MIT
