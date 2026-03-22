# D:\openclaw-plugin-demo\python-websocket-service\app.py
import asyncio
import websockets
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WebSocketServer:
    def __init__(self):
        # 分别存储前端客户端和 OpenClaw 插件客户端
        self.frontend_clients = set()
        self.openclaw_clients = set()
        
    async def register_client(self, websocket, path):
        # 根据连接路径区分客户端类型
        # 约定: OpenClaw 连接 /openclaw, 前端连接 / 或 /frontend
        if path == "/openclaw":
            self.openclaw_clients.add(websocket)
            logger.info(f"✅ [OpenClaw] 插件已连接: {websocket.remote_address}")
        else:
            self.frontend_clients.add(websocket)
            logger.info(f"✅ [Frontend] 前端已连接: {websocket.remote_address} (路径: {path})")
            
    async def unregister_client(self, websocket, path):
        if path == "/openclaw":
            self.openclaw_clients.discard(websocket)
            logger.info(f"❌ [OpenClaw] 插件已断开")
        else:
            self.frontend_clients.discard(websocket)
            logger.info(f"❌ [Frontend] 前端已断开")
        
    async def broadcast_to_group(self, message, group):
        """向指定组广播消息"""
        if not group:
            return
        logger.info(f"message={message}")
        logger.info(f"🔄 正在广播给 {len(group)} 个客户端...")
        # 使用 gather 并发发送，return_exceptions=True 防止单个发送失败影响整体
        await asyncio.gather(
            *[client.send(json.dumps(message)) for client in group],
            return_exceptions=True
        )

    async def handle_message(self, websocket, message_data, path):
        try:
            data = json.loads(message_data)
            msg_type = data.get("type", "unknown")
            content = data.get("data", data) # 兼容直接发数据或带 type 的数据
            
            logger.info(f"收到消息 [{path}]: type={msg_type}, content={str(content)[:50]}...")

            # === 核心转发逻辑 ===
            
            # 场景 1: 消息来自前端 (Vue)，需要转发给 OpenClaw
            if path != "/openclaw": 
                if not self.openclaw_clients:
                    logger.warning("⚠️ 没有连接的 OpenClaw 插件，消息无法转发")
                    # 可选：返回错误给前端
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "No OpenClaw plugin connected"
                    }))
                else:
                    # 构造转发给 OpenClaw 的消息包
                    forward_msg = {
                        "type": "from_frontend",
                        "source": "vue",
                        "data": data,
                        "timestamp": datetime.now().isoformat()
                    }
                    logger.info(f"🔄 正在转发给 {len(self.openclaw_clients)} 个 OpenClaw 客户端...")
                    await self.broadcast_to_group(forward_msg, self.openclaw_clients)
                    
                    # 同时给前端一个确认（可选）
                    # await websocket.send(json.dumps({"type": "ack", "status": "forwarded"}))

            # 场景 2: 消息来自 OpenClaw，需要转发给前端
            elif path == "/openclaw":
                if not self.frontend_clients:
                    logger.warning("⚠️ 没有连接的前端客户端，消息无法转发")
                else:
                    # 构造转发给前端的消息包
                    forward_msg = {
                        "type": "from_openclaw",
                        "source": "plugin",
                        "data": data,
                        "timestamp": datetime.now().isoformat()
                    }
                    logger.info(f"🔄 正在转发给 {len(self.frontend_clients)} 个前端客户端...")
                    await self.broadcast_to_group(forward_msg, self.frontend_clients)

        except json.JSONDecodeError:
            logger.error("收到无效的 JSON 格式")
            await websocket.send(json.dumps({"type": "error", "message": "Invalid JSON"}))
        except Exception as e:
            logger.error(f"处理消息异常: {e}", exc_info=True)
            # 尽量不中断连接，只记录错误

    # websockets v12+ handler 只接收 websocket
    async def handler(self, websocket):
        # 获取路径 (v12+ 写法)
        path = websocket.request.path if hasattr(websocket, 'request') else '/'
        
        await self.register_client(websocket, path)
        try:
            async for message in websocket:
                await self.handle_message(websocket, message, path)
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"连接正常关闭: {websocket.remote_address}")
        except Exception as e:
            logger.error(f"连接异常错误: {e}")
        finally:
            await self.unregister_client(websocket, path)

async def run_server():
    server = WebSocketServer()
    
    logger.info("🚀 启动 WebSocket 服务器 (Mode B: Hub)...")
    logger.info("   - 前端/Vue 请连接: ws://localhost:8765/")
    logger.info("   - OpenClaw 请连接: ws://localhost:8765/openclaw")
    
    async with websockets.serve(server.handler, "localhost", 8765):
        await asyncio.Future()  # 永久运行

def main():
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("服务器已手动停止")

if __name__ == "__main__":
    main()