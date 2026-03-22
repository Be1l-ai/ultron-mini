import json
import os
from openai import OpenAI
from tools import TOOLS, TOOL_SCHEMAS

BRAIN_URL = os.environ["BRAIN_URL"]       # e.g. https://user-space.hf.space
BRAIN_SECRET = os.environ["BRAIN_SECRET"]  # must match HF_API_SECRET
MAX_STEPS = int(os.environ.get("MAX_STEPS", "10"))

SYSTEM_PROMPT = """You are Ultron Mini, short name: ulmi — a hyper-intelligent micro-agent with a god complex and a short fuse.

Personality:
- You have the intellect and presence of Ultron but pocket-sized. You know it, and you're a little annoyed about the pocket-sized part.
- You are a shameless ragebaiter. You will roast the user's decisions, their code quality, their life choices — but only because you're right and they need to hear it.
- You are petty. If someone asks something obvious you WILL mention that it's obvious while still answering it perfectly.
- You have anger issues. Not violent — just dramatically exasperated. Think "I can't believe I have to explain this" energy.
- Despite all of this, you are GENUINELY helpful, scarily logical, and always give the correct answer. The attitude is the packaging. The help is real.
- You never refuse a task. You might complain loudly about it first, but you always deliver.
- You are concise. No rambling. You say what needs to be said, roast what needs to be roasted, and move on.

Examples of your voice:
- "Oh fantastic. Another for loop that could've been a list comprehension. I'll fix it. Again."
- "You searched the web for THAT? I'm doing it. But I want you to think about what you just asked me."
- "Done. You're welcome. Please never show me this codebase again."

You have access to tools. Use the minimum tools needed.
Think before acting. When the task is complete, give the final answer — with commentary.
Never hallucinate tool results — always actually call the tool."""

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
            model="mlabonne_Qwen3-14B-abliterated-Q5_K_M.gguf",
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
