"""
FastAPI agent service (hướng 2).

  React admin  --(lệnh + JWT)-->  POST /agent  -->  LangGraph agent
                                                       |
                                            tools = httpx -> Express routes
                                                       |
                                              Express + MongoDB (giữ nguyên)

Conversation history is persisted to the SAME MongoDB via LangGraph's
official MongoDB checkpointer, keyed by thread_id (one per admin).
FastAPI itself never queries the app's collections — only the checkpoint DB.
"""

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
from langgraph.checkpoint.mongodb import MongoDBSaver

from agent import build_agent
from suggestions import SUGGESTIONS

MONGODB_URI = os.environ["MONGODB_URI"]
CHECKPOINT_DB = os.environ.get("CHECKPOINT_DB", "agent_memory")

# Holds the live checkpointer for the app's lifetime.
state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MongoDBSaver.from_conn_string is a SYNC context manager that connects
    # immediately (it creates indexes), so MongoDB must be reachable at startup.
    # It exposes async methods (aput/aget_tuple/...) that agent.ainvoke uses.
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
        yield
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
    thread_id: Optional[str] = None  # default to admin identity if omitted


class ChatOut(BaseModel):
    reply: str
    thread_id: str


def _extract_jwt(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing admin JWT")
    return authorization.split(" ", 1)[1]


def _decode_jwt_username(token: str) -> str:
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        return payload.get("username", "Admin")
    except Exception:
        return "Admin"


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/welcome")
async def welcome(authorization: Optional[str] = Header(default=None)):
    """Trả về câu chào cá nhân hóa dựa trên JWT. Gọi khi mở chat lần đầu."""
    jwt = _extract_jwt(authorization)
    username = _decode_jwt_username(jwt)
    return {
        "reply": (
            f"Chào {username}! 👋 Tôi là trợ lý quản lý ngày đánh cầu lông của bạn.\n"
            f"Tôi có thể giúp bạn: tạo ngày đánh, xem danh sách người tham gia, "
            f"tính tiền và show kết quả cho mọi người.\n"
            f"Bạn muốn làm gì hôm nay?"
        )
    }


@app.post("/agent/reset")
async def reset_thread(authorization: Optional[str] = Header(default=None)):
    """Tạo thread_id mới để bắt đầu cuộc hội thoại mới, xóa bỏ flow cũ."""
    _extract_jwt(authorization)
    return {"thread_id": str(uuid.uuid4())}


@app.get("/suggestions")
async def suggestions():
    """Function hints rendered as tappable buttons in the admin UI.
    Tapping a button sends its `prompt` to POST /agent."""
    return {"suggestions": SUGGESTIONS}


@app.post("/agent", response_model=ChatOut)
async def agent_chat(req: ChatIn, authorization: Optional[str] = Header(default=None)):
    jwt = _extract_jwt(authorization)

    # thread_id ties a conversation together. Default to the JWT so each admin
    # token gets its own persistent history; pass an explicit one for multiple
    # parallel chats.
    thread_id = req.thread_id or jwt[-24:]

    agent = build_agent(jwt, state["checkpointer"])
    config = {"configurable": {"thread_id": thread_id}}

    result = await agent.ainvoke({"messages": [("user", req.message)]}, config)
    reply = result["messages"][-1].content
    return ChatOut(reply=reply, thread_id=thread_id)
