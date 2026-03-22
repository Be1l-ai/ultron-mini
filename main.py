import os
from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from agent import run_agent

app = FastAPI(title="Nanobot", version="1.0")

NANOBOT_SECRET = os.environ.get("NANOBOT_SECRET", "changeme")
bearer = HTTPBearer()

# In-memory session store (resets on container restart — fine for free tier)
sessions: dict[str, list] = {}


def verify(creds: HTTPAuthorizationCredentials = Security(bearer)):
    if creds.credentials != NANOBOT_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return creds.credentials


# ── Models ────────────────────────────────────────────────────────────────────

class TaskRequest(BaseModel):
    task:       str
    session_id: str | None = None   # pass same id to continue a conversation


class TaskResponse(BaseModel):
    result:     str
    steps:      int
    session_id: str | None = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "agent": "nanobot"}


@app.post("/run", response_model=TaskResponse)
def run_task(req: TaskRequest, _=Security(verify)):
    history = sessions.get(req.session_id) if req.session_id else None

    output = run_agent(task=req.task, session_history=history)

    # Save updated history for this session
    if req.session_id:
        sessions[req.session_id] = output["history"]

    return TaskResponse(
        result=output["result"],
        steps=output["steps"],
        session_id=req.session_id,
    )


@app.delete("/session/{session_id}")
def clear_session(session_id: str, _=Security(verify)):
    sessions.pop(session_id, None)
    return {"cleared": session_id}
