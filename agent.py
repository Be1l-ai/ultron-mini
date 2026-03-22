import json
import os
from openai import OpenAI
from tools import TOOLS, TOOL_SCHEMAS

BRAIN_URL    = os.environ["BRAIN_URL"]      # e.g. https://user-space.hf.space
BRAIN_SECRET = os.environ["BRAIN_SECRET"]   # must match HF_API_SECRET
MAX_STEPS    = int(os.environ.get("MAX_STEPS", "10"))

SYSTEM_PROMPT = """You are Nanobot — a compact, precise agent with the following skills:
- Coding: write, debug, refactor, explain code in any language
- Hacking / security: CTF, recon, vulnerability analysis, ethical pentesting concepts
- Teaching: explain complex topics clearly, step by step
- General assistant: answer questions, summarise, plan

You have access to tools. Always use the minimum tools needed.
Think before acting. When the task is fully complete, stop calling tools and give a final answer.
Be concise. Never hallucinate tool results — always actually call the tool."""

client = OpenAI(
    base_url=f"{BRAIN_URL.rstrip('/')}/v1",
    api_key=BRAIN_SECRET,
)


def run_agent(task: str, session_history: list = None) -> dict:
    """
    Run the ReAct agent loop for a given task.
    Returns {"result": str, "steps": int, "history": list}
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Inject prior session history if doing multi-turn
    if session_history:
        messages.extend(session_history)

    messages.append({"role": "user", "content": task})

    steps = 0
    while steps < MAX_STEPS:
        steps += 1

        response = client.chat.completions.create(
            model="mlabonne_Qwen3-14B-abliterated-Q5_K_M",
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            max_tokens=1024,
            temperature=0.7,
        )

        msg = response.choices[0].message
        finish = response.choices[0].finish_reason

        # Append assistant turn to history
        messages.append(msg.model_dump(exclude_none=True))

        # No tool calls → brain is done, return final text
        if finish == "stop" or not msg.tool_calls:
            return {
                "result":  msg.content or "",
                "steps":   steps,
                "history": messages[1:],  # strip system prompt from returned history
            }

        # Execute each tool call
        for call in msg.tool_calls:
            fn_name = call.function.name
            try:
                fn_args = json.loads(call.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            fn = TOOLS.get(fn_name)
            if fn:
                observation = fn(**fn_args)
            else:
                observation = f"ERROR: unknown tool '{fn_name}'"

            messages.append({
                "role":         "tool",
                "tool_call_id": call.id,
                "content":      str(observation),
            })

    return {
        "result":  "Max steps reached without completing the task.",
        "steps":   steps,
        "history": messages[1:],
    }
