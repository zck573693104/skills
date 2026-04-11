"""
DeepAgent WebUI Server
======================
FastAPI 后端：
  GET  /             → 前端页面
  GET  /api/skills   → 已加载技能列表
  POST /api/chat     → 发送消息，响应为 SSE（日志 + ReAct步骤 + 最终答案）

SSE 事件类型：
  log     → 后台 print 输出（原始日志）
  react   → ReAct 步骤（Thought / Action / Observation）
  answer  → 最终回答
  clarify → 需要用户补充信息
  error   → 异常
  done    → 流结束
"""

import asyncio
import json
import os
import queue
import re
import threading
import winreg
from pathlib import Path
from typing import AsyncGenerator

# ── 自动注入系统代理 ──────────────────────────────────────────
def _inject_proxy():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        )
        enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if enabled:
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
            if server:
                proxy_url = server if "://" in server else f"http://{server}"
                for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
                    if not os.environ.get(var):
                        os.environ[var] = proxy_url
                print(f"[Server] 已注入系统代理: {proxy_url}")
        winreg.CloseKey(key)
    except Exception:
        pass

_inject_proxy()

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from workbuddy import log_collector
from deep_agent import DeepAgent

# ── 初始化 DeepAgent ──────────────────────────────────────────
SKILLS_DIR = str(Path(__file__).parent / "skills")
agent = DeepAgent(SKILLS_DIR)

app = FastAPI(title="DeepAgent WebUI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── SSE 工具 ──────────────────────────────────────────────────
def sse_event(event: str, data: str) -> str:
    data = data.replace("\n", "\\n")
    return f"event: {event}\ndata: {data}\n\n"


def sse_json(event: str, payload: dict) -> str:
    return sse_event(event, json.dumps(payload, ensure_ascii=False))


# ── API: 技能列表 ─────────────────────────────────────────────
@app.get("/api/skills")
def get_skills():
    return [
        {"name": m.name, "description": m.description, "tags": m.tags}
        for m in agent.registry.all()
    ]


# ── API: 聊天（SSE 流式） ─────────────────────────────────────
class ChatRequest(BaseModel):
    message: str


# 解析 print 日志，识别 ReAct 特征行并额外发送 react 事件
_REACT_PATTERNS = [
    (re.compile(r"\[ReAct\]\s*步骤\s*(\d+)\s*\|\s*action=(\S+)"),   "step"),
    (re.compile(r"\[ReAct\]\s*推理:\s*(.+)"),                        "reasoning"),
    (re.compile(r"\[ReAct\]\s*Observation:\s*(.+)"),                  "observation"),
    (re.compile(r"\[SkillTool\]\s*调用 Skill:\s*(.+)"),              "skill_call"),
    (re.compile(r"\[SkillTool\]\s*选中脚本:\s*(.+)"),                "script"),
    (re.compile(r"\[SkillTool\]\s*提取到参数:\s*(.+)"),              "params"),
    (re.compile(r"\[DeepAgent\]\s*(.+)"),                             "agent"),
]


def classify_log(text: str):
    """
    返回 (react_type, react_payload) 或 None（普通日志）
    """
    for pattern, rtype in _REACT_PATTERNS:
        m = pattern.search(text)
        if m:
            return rtype, m.group(1) if m.lastindex >= 1 else ""
    return None


@app.post("/api/chat")
async def chat(req: ChatRequest):
    q: queue.Queue = queue.Queue()

    def on_log(text: str):
        q.put(("log", text))

    log_collector.subscribe(on_log)

    async def stream() -> AsyncGenerator[str, None]:
        loop = asyncio.get_event_loop()
        result_holder = {}

        def run_chat():
            try:
                with log_collector.capture():
                    result_holder["answer"] = agent.chat(req.message)
                    # 如果 Agent 在等待追问，标记类型
                    if agent.waiting_for_user:
                        result_holder["clarify"] = True
            except Exception as e:
                import traceback
                result_holder["error"] = traceback.format_exc()
            finally:
                q.put(None)

        thread = threading.Thread(target=run_chat, daemon=True)
        thread.start()

        try:
            while True:
                try:
                    item = await loop.run_in_executor(None, lambda: q.get(timeout=0.05))
                    if item is None:
                        break
                    event, data = item
                    # 发送原始日志
                    yield sse_event("log", data)
                    # 识别是否有 ReAct 步骤事件
                    classified = classify_log(data)
                    if classified:
                        rtype, payload = classified
                        yield sse_json("react", {"type": rtype, "text": payload, "raw": data})
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            log_collector.unsubscribe(on_log)

        if "error" in result_holder:
            yield sse_event("error", result_holder["error"])
        elif result_holder.get("clarify"):
            yield sse_json("clarify", {"question": result_holder.get("answer", "")})
        else:
            yield sse_event("answer", result_holder.get("answer", ""))

        yield sse_event("done", "")

    return StreamingResponse(stream(), media_type="text/event-stream")


# ── 前端页面 ──────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "deep_agent_ui.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    uvicorn.run("deep_agent_server:app", host="0.0.0.0", port=8766, reload=False)
