"""Aurora Web - FastAPI application for LED matrix finger paint.

Phase 1 MVP: Finger paint only, no pattern drawers.
Browser is source of truth - handles fading locally and sends frames to server.
"""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import numpy as np

from aurora_web.core.serial_process import SerialOutputManager


# Global state
config: dict = {}
serial_manager: Optional[SerialOutputManager] = None
render_task: Optional[asyncio.Task] = None
connected_clients: set[WebSocket] = set()

# Frame from browser (source of truth)
browser_frame: Optional[np.ndarray] = None
browser_frame_lock = asyncio.Lock()
frame_num: int = 0


def load_config(config_path: str = "aurora_web/config.yaml") -> dict:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f)

    # Default config if file doesn't exist
    return {
        "server": {"host": "0.0.0.0", "port": 80},
        "matrix": {
            "width": 32,
            "height": 18,
            "serial_device": "/dev/ttyACM0",
            "fps": 40,
            "gamma": 2.5,
            "layout_left_to_right": True,
        },
    }


async def render_loop():
    """Main render loop - sends browser frame to LED matrix."""
    global browser_frame, serial_manager, frame_num

    matrix_cfg = config.get("matrix", {})
    width = matrix_cfg.get("width", 32)
    height = matrix_cfg.get("height", 18)
    target_fps = matrix_cfg.get("fps", 40)
    frame_time = 1.0 / target_fps
    local_frame_num = 0
    last_time = time.perf_counter()

    # Default black frame
    black_frame = np.zeros((height, width, 3), dtype=np.uint8)

    while True:
        frame_start = time.perf_counter()
        delta_time = frame_start - last_time
        last_time = frame_start

        if serial_manager:
            # Use browser frame if available, otherwise black
            async with browser_frame_lock:
                rgb = browser_frame if browser_frame is not None else black_frame

            # Send to serial
            serial_manager.send_frame(rgb)

            local_frame_num += 1

            # Broadcast status to clients every 30 frames
            if local_frame_num % 30 == 0 and connected_clients:
                actual_fps = 1.0 / max(delta_time, 0.001)
                status = {
                    "type": "status",
                    "fps": round(actual_fps, 1),
                    "frame": local_frame_num,
                }
                await broadcast(json.dumps(status))

        # Sleep to maintain target FPS
        elapsed = time.perf_counter() - frame_start
        sleep_time = frame_time - elapsed
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
        else:
            await asyncio.sleep(0)  # Yield to other tasks


async def broadcast(message: str):
    """Broadcast message to all connected WebSocket clients."""
    disconnected = set()
    for ws in connected_clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    connected_clients.difference_update(disconnected)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    global config, serial_manager, render_task

    # Load config
    config = load_config()
    matrix_cfg = config.get("matrix", {})
    width = matrix_cfg.get("width", 32)
    height = matrix_cfg.get("height", 18)

    # Start serial output process
    serial_manager = SerialOutputManager(
        device=matrix_cfg.get("serial_device", "/dev/ttyACM0"),
        width=width,
        height=height,
        fps=matrix_cfg.get("fps", 40),
        gamma=matrix_cfg.get("gamma", 2.5),
        layout_ltr=matrix_cfg.get("layout_left_to_right", True),
    )
    serial_manager.start()

    # Start render loop
    render_task = asyncio.create_task(render_loop())

    print(f"[Aurora Web] Started - {width}x{height} matrix")

    yield

    # Shutdown
    print("[Aurora Web] Shutting down...")
    if render_task:
        render_task.cancel()
        try:
            await render_task
        except asyncio.CancelledError:
            pass
    if serial_manager:
        serial_manager.stop()


app = FastAPI(title="Aurora Web", lifespan=lifespan)

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    """Serve the main HTML page."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Aurora Web - static files not found"}


@app.get("/api/config")
async def get_config():
    """Get current configuration."""
    return {
        "width": config.get("matrix", {}).get("width", 32),
        "height": config.get("matrix", {}).get("height", 18),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time frame data from browser."""
    global browser_frame

    await websocket.accept()
    connected_clients.add(websocket)

    matrix_cfg = config.get("matrix", {})
    width = matrix_cfg.get("width", 32)
    height = matrix_cfg.get("height", 18)
    expected_size = width * height * 3

    # Send initial config
    await websocket.send_text(json.dumps({
        "type": "config",
        "width": width,
        "height": height,
    }))

    try:
        while True:
            # Can receive either text (JSON) or binary (frame data)
            message = await websocket.receive()

            if "bytes" in message:
                # Binary frame data from browser
                data = message["bytes"]
                if len(data) == expected_size:
                    # Convert to numpy array
                    frame = np.frombuffer(data, dtype=np.uint8).reshape(height, width, 3)
                    async with browser_frame_lock:
                        browser_frame = frame.copy()

            elif "text" in message:
                # JSON message (for backward compatibility / other commands)
                msg = json.loads(message["text"])
                msg_type = msg.get("type")

                if msg_type == "clear_canvas":
                    async with browser_frame_lock:
                        browser_frame = np.zeros((height, width, 3), dtype=np.uint8)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
    finally:
        connected_clients.discard(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)
