"""DoPeJarMo Kernel — minimal WebSocket entry point.

Two session paths:
  /operator  — DoPeJarMo interactive agent shell (operator sessions)
  /user      — DoPeJar conversational AI (user sessions)

Connection drop = session boundary.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone

import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("kernel")

HOST = os.getenv("KERNEL_HOST", "0.0.0.0")
PORT = int(os.getenv("KERNEL_PORT", "8080"))

# Connection bookkeeping
_sessions: dict[str, dict] = {}


async def _handle_operator(ws):
    """Handle /operator WebSocket sessions (DoPeJarMo agent shell)."""
    session_id = f"op-{id(ws):x}"
    _sessions[session_id] = {"type": "operator", "started": datetime.now(timezone.utc).isoformat()}
    log.info("SESSION_START operator %s from %s", session_id, ws.remote_address)
    try:
        async for message in ws:
            log.info("operator %s: received %d bytes", session_id, len(message))
            await ws.send(json.dumps({
                "session": session_id,
                "type": "ack",
                "received": len(message) if isinstance(message, (str, bytes)) else 0,
            }))
    finally:
        log.info("SESSION_END operator %s (connection dropped)", session_id)
        _sessions.pop(session_id, None)


async def _handle_user(ws):
    """Handle /user WebSocket sessions (DoPeJar conversational AI)."""
    session_id = f"usr-{id(ws):x}"
    _sessions[session_id] = {"type": "user", "started": datetime.now(timezone.utc).isoformat()}
    log.info("SESSION_START user %s from %s", session_id, ws.remote_address)
    try:
        async for message in ws:
            log.info("user %s: received %d bytes", session_id, len(message))
            await ws.send(json.dumps({
                "session": session_id,
                "type": "ack",
                "received": len(message) if isinstance(message, (str, bytes)) else 0,
            }))
    finally:
        log.info("SESSION_END user %s (connection dropped)", session_id)
        _sessions.pop(session_id, None)


async def _router(ws):
    """Route incoming WebSocket connections by path."""
    path = ws.request.path if hasattr(ws, "request") else getattr(ws, "path", "/")
    if path == "/operator":
        await _handle_operator(ws)
    elif path == "/user":
        await _handle_user(ws)
    elif path == "/health":
        await ws.send(json.dumps({
            "status": "ok",
            "sessions": len(_sessions),
            "uptime_check": datetime.now(timezone.utc).isoformat(),
        }))
    else:
        await ws.close(4004, f"Unknown path: {path}. Use /operator or /user.")


async def main():
    log.info("DoPeJarMo Kernel starting on %s:%d", HOST, PORT)
    log.info("  /operator — DoPeJarMo agent shell")
    log.info("  /user     — DoPeJar conversational AI")

    stop = asyncio.get_event_loop().create_future()

    def _shutdown():
        if not stop.done():
            stop.set_result(True)

    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_event_loop().add_signal_handler(sig, _shutdown)

    async with websockets.serve(_router, HOST, PORT):
        log.info("Kernel ready — listening on ws://%s:%d", HOST, PORT)
        await stop

    log.info("Kernel shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
