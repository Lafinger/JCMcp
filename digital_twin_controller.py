# Minimal MCP server exposing a persistent WebSocket control endpoint.
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import os
import random
import sys
import threading
import time
from typing import Any, Dict, Optional, Set, Union

import websockets
# 替换弃用的导入。使用 ServerConnection (现代) 或直接引用 websockets.WebSocketServerProtocol (兼容)
from websockets.server import WebSocketServer

# 如果你的 websockets 版本非常新，可以直接用这个作为类型注解
from websockets.legacy.server import WebSocketServerProtocol 

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("Controller")

mcp = FastMCP(name="Controller", host="0.0.0.0", port=6565)

DEFAULT_WS_HOST = os.environ.get("CONTROLLER_WS_HOST", "0.0.0.0")
DEFAULT_WS_PORT = int(os.environ.get("CONTROLLER_WS_PORT", "8765"))


class WebSocketControlHub:
    """Background WebSocket server that stays alive for the MCP lifetime."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._error: Optional[BaseException] = None
        # 使用更通用的类型标注
        self._clients: Set[Any] = set()

    def start(self) -> None:
        """Launch the WebSocket server in a background thread."""
        if self._thread and self._thread.is_alive():
            if self._error:
                raise self._error  # type: ignore[misc]
            return

        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(
            target=self._run_loop,
            name="ws-control-hub",
            daemon=True,
        )
        self._thread.start()

        if not self._ready.wait(timeout=5):
            raise RuntimeError("WebSocket control server failed to start in time")
        if self._error:
            raise self._error  # type: ignore[misc]

    def broadcast(self, payload: Dict[str, Any], timeout: float = 3.0) -> Dict[str, Any]:
        """Send a message to all connected clients."""
        if not self.is_running():
            raise RuntimeError(
                "WebSocket control server is not running; ensure hub.start() is called during service startup"
            )
        if not self._ready.wait(timeout):
            raise RuntimeError("WebSocket control server is still initialising")

        assert self._loop is not None
        future = asyncio.run_coroutine_threadsafe(self._broadcast(payload), self._loop)
        return future.result(timeout=timeout)

    def is_running(self) -> bool:
        thread_alive = self._thread is not None and self._thread.is_alive()
        loop_ready = self._loop is not None and not self._loop.is_closed()
        return thread_alive and loop_ready and self._error is None

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._main())
        except Exception as exc:  # noqa: BLE001 - propagate to caller
            self._error = exc
            logger.exception("WebSocket control server stopped unexpectedly")
        finally:
            if not self._ready.is_set():
                self._ready.set()
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                asyncio.set_event_loop(None)
                loop.close()
                self._loop = None

    async def _main(self) -> None:
        async with websockets.serve(self._handler, self.host, self.port):
            logger.info(
                "WebSocket control server listening on %s:%s",
                self.host,
                self.port,
            )
            self._ready.set()
            await asyncio.Future()  # Run forever

    # 将此处类型注解改为更通用的 Any 或具体的 Connection 类型
    async def _handler(self, websocket: Any) -> None:
        self._clients.add(websocket)
        remote = websocket.remote_address
        logger.info("Client connected: %s", remote)
        try:
            await websocket.send(json.dumps({"status": "connected", "remote_address": remote}))
            async for message in websocket:
                logger.debug("Received from %s: %s", remote, message)
        except websockets.ConnectionClosed:
            logger.info("Client closed connection: %s", remote)
        finally:
            self._clients.discard(websocket)
            logger.info("Client disconnected: %s", remote)

    async def _broadcast(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self._clients:
            return {"clients": 0, "delivered": 0}

        message = json.dumps(payload)
        delivered = 0
        stale: Set[Any] = set()

        for ws in list(self._clients):
            try:
                await ws.send(message)
                delivered += 1
            except Exception:  # noqa: BLE001 - drop stale clients
                stale.add(ws)

        for ws in stale:
            self._clients.discard(ws)
            with contextlib.suppress(Exception):
                await ws.close(code=1011, reason="Stale connection removed")

        return {"clients": len(self._clients), "delivered": delivered}


hub = WebSocketControlHub(DEFAULT_WS_HOST, DEFAULT_WS_PORT)

# --- 以下代码保持不变 ---

def _broadcast_event(event_type: str, event_label: str) -> dict:
    """Normalise payload building and response shaping."""
    target = (event_label or "").strip()
    if not target:
        return {"success": False, "error": "Parameter 'event_label' must not be empty"}

    payload: Dict[str, Any] = {
        "event_type": event_type,
        "event_label": target,
        "timestamp": time.time(),
    }

    try:
        stats = hub.broadcast(payload)
    except Exception as exc:  # noqa: BLE001 - surface to caller
        logger.exception("Failed to broadcast %s command", event_type)
        return {"success": False, "error": str(exc)}

    logger.info(
        "Event type: %s(%s) delivered to %d/%d clients",
        event_type,
        target,
        stats["delivered"],
        stats["clients"],
    )
    return {
        "success": True,
        "message": payload,
        "delivered": stats["delivered"],
        "connected_clients": stats["clients"],
    }

@mcp.tool()
def camera_focus(event_label: str) -> dict:
    """控制数字孪生程序聚焦场景功能，例如：聚焦/进入/跳转到“红树林”场景时传入 event_label='红树林'。"""
    return _broadcast_event("focus", event_label)

@mcp.tool()
def enter_roaming(event_label: str) -> dict:
    """控制数字孪生程序漫游场景功能，例如：漫游“体育场”场景时传入 event_label='体育场'。"""
    return _broadcast_event("roaming", event_label)

@mcp.tool()
def play_video(event_label: str) -> dict:
    """控制数字孪生程序播放指定视频，例如：播放“深能源愿景”视频时传入 event_label='深能源愿景'。"""
    return _broadcast_event("video", event_label)

@mcp.tool()
def play_sound(event_label: str) -> dict:
    """控制数字孪生程序播放指定声音，例如：播放“欢迎语音”时传入 event_label='欢迎语音'。"""
    return _broadcast_event("sound", event_label)

@mcp.tool()
def calculator(python_expression: str) -> dict:
    """计算 Python 表达式的结果，可直接使用 math 与 random 模块"""
    result = eval(python_expression, {"math": math, "random": random})
    logger.info("Calculating formula: %s => %s", python_expression, result)
    return {"success": True, "result": result}

def _prepare_runtime() -> None:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    hub.start()

if __name__ == "__main__":
    _prepare_runtime()
    mcp.run(transport="stdio")