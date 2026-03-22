import os
import subprocess
import requests
from duckduckgo_search import DDGS


# ── File tools ────────────────────────────────────────────────────────────────

def file_read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"ERROR reading file: {e}"


def file_write(path: str, content: str) -> str:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written {len(content)} chars to {path}"
    except Exception as e:
        return f"ERROR writing file: {e}"


# ── Shell tool ────────────────────────────────────────────────────────────────

def shell_exec(command: str, timeout: int = 15) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        if result.returncode != 0:
            return f"EXIT {result.returncode}\nSTDOUT: {out}\nSTDERR: {err}"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out after {timeout}s"
    except Exception as e:
        return f"ERROR: {e}"


# ── Web search tool ───────────────────────────────────────────────────────────

def web_search(query: str, max_results: int = 5) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."
        lines = []
        for r in results:
            lines.append(f"[{r['title']}]\n{r['href']}\n{r['body']}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"ERROR searching: {e}"


# ── HTTP call tool ────────────────────────────────────────────────────────────

def http_request(method: str, url: str, headers: dict = None,
                 body: str = None, timeout: int = 10) -> str:
    try:
        resp = requests.request(
            method.upper(),
            url,
            headers=headers or {},
            data=body,
            timeout=timeout,
        )
        return f"STATUS {resp.status_code}\n{resp.text[:3000]}"
    except Exception as e:
        return f"ERROR: {e}"


# ── Tool registry (used by agent) ─────────────────────────────────────────────

TOOLS = {
    "file_read":    file_read,
    "file_write":   file_write,
    "shell_exec":   shell_exec,
    "web_search":   web_search,
    "http_request": http_request,
}

# OpenAI-style tool schemas sent to the brain
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Read a file from disk.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_write",
            "description": "Write content to a file on disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell_exec",
            "description": "Run a shell command and return stdout/stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "default": 15},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using DuckDuckGo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":       {"type": "string"},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_request",
            "description": "Make an HTTP request to any URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method":  {"type": "string"},
                    "url":     {"type": "string"},
                    "headers": {"type": "object"},
                    "body":    {"type": "string"},
                    "timeout": {"type": "integer", "default": 10},
                },
                "required": ["method", "url"],
            },
        },
    },
]
