"""Contract 4 chat API, served on port 8000.

    python -m uvicorn agents.server:app --port 8000      (or: make agents)

Needs the tools API on TOOLS_URL (default http://localhost:8001). See agents/chat.py for how the
Claude pipeline and the rule-based fallback are chosen.
"""
from __future__ import annotations

import asyncio
import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from dotenv import load_dotenv

from agents.chat import answer
from agents.tools_client import ToolsClient

load_dotenv()  # picks up ANTHROPIC_API_KEY from .env so the Claude pipeline can run

TOOLS_URL = os.getenv("TOOLS_URL", "http://localhost:8001")
REQUEST_TIMEOUT_SECONDS = 60


class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=12000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    history: list[HistoryItem] = Field(default_factory=list, max_length=30)
    site: str | None = None


app = FastAPI(title="DeCode chat", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/chat")
async def chat(request: ChatRequest) -> dict:
    tools = ToolsClient(TOOLS_URL)
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                answer,
                request.message,
                [item.model_dump() for item in request.history],
                request.site,
                tools,
            ),
            timeout=REQUEST_TIMEOUT_SECONDS - 1,
        )
    except asyncio.TimeoutError as error:
        raise HTTPException(status_code=504, detail="Chat request exceeded the 60 second limit") from error
    finally:
        tools.close()