"""
WorkBuddy WebUI Server
FastAPI 后端：
  GET  /             → 前端页面
  GET  /api/skills   → 已加载技能列表
  GET  /api/logs     → SSE 实时日志流
  POST /api/chat     → 发送消息，响应为 SSE（日志 + 最终答案）
"""

import asyncio
import json
import os
import queue
import threading
import winreg
from pathlib import Path
from typing import AsyncGenerator

# ── 自动注入系统代理（解决 Start-Process 不继承代理环境变量的问题）──
def _inject_proxy():
    """读取 WinINet 系统代理设置，注入到当前进程及子进程环境变量"""
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
        pass  # 没有代理设置或读取失败，忽略

_inject_proxy()

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from workbuddy import WorkBuddy, log_collector

# ── 初始化 WorkBuddy ────────────────────────────────────────────
SKILLS_DIR = str(Path(__file__).parent / "skills")
buddy = WorkBuddy(SKILLS_DIR)

app = FastAPI(title="WorkBuddy WebUI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── SSE 工具 ───────────────────────────────────────────────────
def sse_event(event: str, data: str) -> str:
    """格式化一条 SSE 消息"""
    data = data.replace("\n", "\\n")
    return f"event: {event}\ndata: {data}\n\n"


# ── API: 技能列表 ──────────────────────────────────────────────
@app.get("/api/skills")
def get_skills():
    return [
        {"name": m.name, "description": m.description, "tags": m.tags}
        for m in buddy.registry.all()
    ]


# ── API: 聊天（SSE 流式） ──────────────────────────────────────
class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    SSE 流：
      event: log   → print 日志行
      event: done  → 最终回答
      event: error → 错误信息
    """
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
                    result_holder["answer"] = buddy.chat(req.message)
            except Exception as e:
                result_holder["error"] = str(e)
            finally:
                q.put(None)  # 结束信号

        thread = threading.Thread(target=run_chat, daemon=True)
        thread.start()

        try:
            while True:
                try:
                    item = await loop.run_in_executor(None, lambda: q.get(timeout=0.05))
                    if item is None:
                        break
                    event, data = item
                    yield sse_event(event, data)
                except queue.Empty:
                    yield ": keep-alive\n\n"  # 心跳，防止连接断开
        finally:
            log_collector.unsubscribe(on_log)

        if "error" in result_holder:
            yield sse_event("error", result_holder["error"])
        else:
            yield sse_event("done", result_holder.get("answer", ""))

    return StreamingResponse(stream(), media_type="text/event-stream")


# ── 前端页面 ───────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "workbuddy_ui.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    uvicorn.run("workbuddy_server:app", host="0.0.0.0", port=8765, reload=False)
