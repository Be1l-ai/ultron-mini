# Brain Model Troubleshooting (Qwen2-1.5B GGUF)

## What the code expects
- `ultron_mini/launcher.py` **does not load GGUF files**. It only proxies requests to an **OpenAI-compatible HTTP server**.
- The proxy always calls:
  - `POST {BRAIN_URL}/v1/chat/completions`
  - `GET {BRAIN_URL}/v1/models`
- If `BRAIN_URL` is a file path (like `/root/.cache/.../Qwen2-1.5B...gguf`), requests will fail because it is not an HTTP endpoint.

## Why it likely isn’t working
1. **Model file path is not a server**  
   The GGUF path is just a file on disk. The launcher expects a running OpenAI-compatible server (e.g., `llama.cpp` server, vLLM, TGI).
2. **The model ID doesn’t match what the server exposes**  
   `BRAIN_MODEL` must match the ID returned by `GET /v1/models`. If it doesn’t, the backend may reject the request.
3. **Context vs. output budget mismatch**  
   The model supports 32k context, but this repo defaults to `BRAIN_MAX_TOKENS=512` and `BRAIN_MAX_TOKENS_CAP=768`, so outputs are short.
4. **Pipeline mode adds extra calls**  
   `BRAIN_PIPELINE=1` (default) makes multiple calls per user request. Slow backends can time out or fail.
5. **Runtime path mismatch in containers**  
   The file path `/root/.cache/...` only exists on the host that downloaded the model. If you run in Render/HF/container, that path won’t exist unless you mount it.

## What to do (required)
1. **Run an OpenAI-compatible server with the GGUF file**  
   For `llama.cpp` server, load the file directly and set the context:
   - Model path: `/root/.cache/huggingface/hub/.../Qwen2-1.5B-Instruct-Abliterated-Q4_K_M.gguf`
   - Context: `32768`
   - Parallel slots: `4`
   - Expose an HTTP port (e.g., `8080`)
2. **Set environment variables for ultron-mini**
   - `BRAIN_URL=http://<host>:<port>` (**no** `/v1` suffix)
   - `BRAIN_MODEL=<id from /v1/models>` (often the filename or the model name the server reports)
   - `BRAIN_SECRET=<token>` if your server requires auth (leave blank otherwise)
   - `TELEGRAM_TOKEN` and `TELEGRAM_USER_ID` (required)
3. **Tune output budgets to fit your use-case**
   - Increase `BRAIN_MAX_TOKENS` and `BRAIN_MAX_TOKENS_CAP` if you want longer answers.
   - Keep them below your server’s available context and RAM.
4. **If it’s slow or timing out, disable the pipeline**
   - `BRAIN_PIPELINE=0`
   - Or increase `BRAIN_TIMEOUT` and `BRAIN_PIPELINE_BUDGET_SEC`

## Recommendations
- **Verify the backend first**: `GET {BRAIN_URL}/v1/models` should return the model list.
- **Use `/pingbrain`** in Telegram to check upstream connectivity.
- **Enable debug logs**: `BRAIN_PIPELINE_DEBUG=1` to see pipeline timing.
- **Container environments**: if you deploy on Render/HF, mount the GGUF path or use HF repo-based loading (see `./huggingface/README.md` in this repo).
- **Keep `BRAIN_URL` clean**: the code appends `/v1`, so don’t include it yourself.
