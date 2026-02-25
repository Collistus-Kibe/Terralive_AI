"""
FastAPI WebSocket endpoint that bridges the browser to the Gemini Live API.
"""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.gemini_live import GeminiLiveClient

ws_router = APIRouter()


@ws_router.websocket("/ws/agent")
async def agent_websocket(websocket: WebSocket):
    """
    Accept a browser WebSocket connection and relay audio bidirectionally
    between the browser microphone and the Gemini Live API.
    """
    await websocket.accept()
    print("[WS] Client connected")

    gemini = GeminiLiveClient()

    try:
        # Open the upstream Gemini session
        await gemini.connect()
        print("[WS] Gemini Live session established")

        # Notify the browser that the AI session is ready
        await websocket.send_json({"type": "session_ready"})

        async def browser_to_gemini():
            """Read audio/image frames from the browser and forward to Gemini."""
            try:
                while True:
                    raw = await websocket.receive_text()
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    msg_type = msg.get("type")
                    payload  = msg.get("data")
                    if not payload:
                        continue

                    if msg_type == "audio":
                        await gemini.send_audio(payload)
                    elif msg_type == "image":
                        await gemini.send_image(payload)
                    elif msg_type == "text":
                        await gemini.send_text(payload)

            except WebSocketDisconnect:
                print("[WS] Client disconnected (browser→gemini)")
            except Exception as e:
                print(f"[WS] browser_to_gemini error: {e}")

        async def gemini_to_browser():
            """Stream Gemini audio responses back to the browser."""
            await gemini.receive_loop(websocket)

        # Run both directions concurrently
        await asyncio.gather(
            browser_to_gemini(),
            gemini_to_browser(),
        )

    except WebSocketDisconnect:
        print("[WS] Client disconnected")
    except Exception as e:
        print(f"[WS] Error: {e}")
    finally:
        await gemini.close()
        print("[WS] Session closed")
