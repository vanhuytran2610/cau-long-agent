"""
FastAPI agent service.

  React admin  --(lệnh + accessToken)-->  POST /agent  -->  LangGraph agent
                                                               |
                                                    tools = httpx -> Express routes
                                                               |
                                                      Express + MongoDB (giữ nguyên)

Conversation history is persisted to the SAME MongoDB via LangGraph's
official MongoDB checkpointer, keyed by thread_id (one per admin).
FastAPI itself never queries the app's collections — only the checkpoint DB.
"""

import asyncio
import os
import base64
import json
import uuid
from contextlib import asynccontextmanager, ExitStack
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
from langgraph.checkpoint.mongodb import MongoDBSaver

from agent import build_agent
from rag import initialize_rag
from client.express import ExpressClient
from memory import store_memory, retrieve_memories
from memory import extract_events
from content.prompts import get_welcome
from content.suggestions import get_suggestions

MONGODB_URI = os.environ["MONGODB_URI"]
CHECKPOINT_DB = os.environ.get("CHECKPOINT_DB", "agent_memory")
MEMORY_COLLECTION = os.environ.get("MEMORY_COLLECTION", "agent_memories")

# Holds the live checkpointer for the app's lifetime.
state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    with ExitStack() as stack:
        try:
            checkpointer = stack.enter_context(
                MongoDBSaver.from_conn_string(
                    MONGODB_URI,
                    db_name=CHECKPOINT_DB,
                    serverSelectionTimeoutMS=5000,
                )
            )
        except Exception as e:
            raise RuntimeError(
                f"Không kết nối được MongoDB tại MONGODB_URI để lưu memory. "
                f"Kiểm tra MONGODB_URI và (nếu dùng Atlas) whitelist IP server. Chi tiết: {e}"
            ) from e
        state["checkpointer"] = checkpointer

        mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        state["memory_collection"] = mongo_client[CHECKPOINT_DB][MEMORY_COLLECTION]

        try:
            await initialize_rag()
        except Exception as e:
            print(f"[RAG] Warning: khởi tạo thất bại, retrieve_knowledge sẽ không hoạt động: {e}")
        yield

        mongo_client.close()
    state.clear()


app = FastAPI(title="Badminton Admin Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatIn(BaseModel):
    message: str
    thread_id: Optional[str] = None
    refresh_token: Optional[str] = None


class ChatOut(BaseModel):
    status_code: int = 200
    message: str = ""
    data: Optional[dict] = None


def _extract_access_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing access token")
    return authorization.split(" ", 1)[1]


def _extract_language(accept_language: Optional[str]) -> str:
    if accept_language and accept_language.strip().startswith("en"):
        return "en"
    return "vi"


def _decode_username(access_token: str) -> str:
    try:
        payload_b64 = access_token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        return payload.get("username", "Admin")
    except Exception:
        return "Admin"


def _decode_admin_id(access_token: str) -> str:
    try:
        payload_b64 = access_token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        return str(payload.get("id") or payload.get("_id") or access_token[-24:])
    except Exception:
        return access_token[-24:]


@app.get("/health")
async def health():
    return ChatOut(data={"ok": True})


@app.get("/welcome")
async def welcome(
    authorization: Optional[str] = Header(default=None),
    accept_language: Optional[str] = Header(default=None),
):
    access_token = _extract_access_token(authorization)
    username = _decode_username(access_token)
    language = _extract_language(accept_language)
    return ChatOut(data={"reply": get_welcome(username, language)})


@app.post("/agent/reset")
async def reset_thread(authorization: Optional[str] = Header(default=None)):
    """Tạo thread_id mới để bắt đầu cuộc hội thoại mới, xóa bỏ flow cũ."""
    _extract_access_token(authorization)
    return ChatOut(data={"thread_id": str(uuid.uuid4())})


@app.get("/suggestions")
async def suggestions(accept_language: Optional[str] = Header(default=None)):
    """Function hints rendered as tappable buttons in the admin UI."""
    language = _extract_language(accept_language)
    return ChatOut(data={"suggestions": get_suggestions(language)})


@app.post("/agent", response_model=ChatOut)
async def agent_chat(
    req: ChatIn,
    authorization: Optional[str] = Header(default=None),
    accept_language: Optional[str] = Header(default=None),
):
    access_token = _extract_access_token(authorization)
    thread_id = req.thread_id or access_token[-24:]
    admin_id = _decode_admin_id(access_token)
    language = _extract_language(accept_language)
    memory_col = state["memory_collection"]

    # RETRIEVE: tìm memories liên quan, inject vào system prompt
    memory_context = ""
    try:
        memories = await asyncio.to_thread(
            retrieve_memories, memory_col, admin_id, req.message
        )
        if memories:
            memory_context = "\n".join(f"- {m}" for m in memories)
    except Exception as e:
        print(f"[Memory] retrieve error: {e}")

    client = ExpressClient(access_token, req.refresh_token)
    agent = build_agent(client, state["checkpointer"], language, memory_context)
    config = {"configurable": {"thread_id": thread_id}}

    result = await agent.ainvoke({"messages": [("user", req.message)]}, config)
    reply = result["messages"][-1].content

    # STORE: lưu events thành công vào vector DB (fire and forget)
    events = extract_events(result["messages"])
    if events:
        async def _store_events():
            for ev in events:
                try:
                    await asyncio.to_thread(
                        store_memory,
                        memory_col,
                        admin_id,
                        ev["event_type"],
                        ev["text"],
                        ev["metadata"],
                    )
                except Exception as e:
                    print(f"[Memory] store error: {e}")
        asyncio.create_task(_store_events())

    response_data: dict = {"reply": reply, "thread_id": thread_id}
    if client.new_tokens:
        response_data["new_tokens"] = client.new_tokens

    return ChatOut(data=response_data)
