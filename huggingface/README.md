---
title: Nanobot Brain
emoji: 🧠
sdk: docker
pinned: false
---

## Runtime Variables

Set these in your Hugging Face Space settings:

- `LLAMA_ARG_HF_REPO` (required): Hugging Face repo that contains the GGUF model
- `LLAMA_ARG_API_KEY` (required for private/gated repos): HF token or secret
- `LLAMA_ARG_OVERRIDE_KV` (optional): llama.cpp key/value overrides, if needed
- `LLAMA_ARG_HOST` (optional): host binding; usually leave unset
- any other `LLAMA_ARG_*` variables supported by `llama.cpp`

The Space uses the native `llama.cpp` server image, so model loading is controlled entirely by `LLAMA_ARG_*` variables.