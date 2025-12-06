"""Aurora Web - FastAPI application for LED matrix finger paint.

Phase 1 MVP: Finger paint only, no pattern drawers.
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
from aurora_web.core.palette import Palette
from aurora_web.inputs.canvas_feed import CanvasFeed


# Global state
config: dict = {}
serial_manager: Optional[SerialOutputManager] = None
canvas_feed: Optional[CanvasFeed] = None
palette: Optional[Palette] = None
render_task: Optional[asyncio.Task] = None
connected_clients: set[WebSocket] = set()


def load_config(config_path: str = "aurora_web/config.yaml") -> dict:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f)

    # Default config if file doesn't exist
    return {
        "server": {"host": "0.0.0.0", "port": 8000},
        "matrix": {
            "width": 32,
            "height": 18,
            "serial_device": "/dev/ttyACM0",
            "fps": 40,
            "gamma": 2.5,
            "layout_left_to_right": True,
        },
        "canvas": {"decay_rate": 0.0},
    }


async def render_loop():
    """Main render loop - sends canvas to LED matrix at target FPS."""
    global canvas_feed, serial_manager, palette

    target_fps = config.get("matrix", {}).get("fps", 40)
    frame_time = 1.0 / target_fps
    frame_num = 0
    last_time = time.perf_counter()

    while True:
        frame_start = time.perf_counter()
        delta_time = frame_start - last_time
        last_time = frame_start

        if canvas_feed and serial_manager:
            # Update canvas (apply decay)
            canvas_feed.update(delta_time)

            # Get RGB frame from canvas
            rgb = canvas_feed.get_rgb_frame()

            # Send to serial
            serial_manager.send_frame(rgb)

            frame_num += 1

            # Broadcast status to clients every 30 frames
            if frame_num % 30 == 0 and connected_clients:
                actual_fps = 1.0 / max(delta_time, 0.001)
                status = {
                    "type": "status",
                    "fps": round(actual_fps, 1),
                    "frame": frame_num,
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
    global config, serial_manager, canvas_feed, palette, render_task

    # Load config
    config = load_config()
    matrix_cfg = config.get("matrix", {})
    width = matrix_cfg.get("width", 32)
    height = matrix_cfg.get("height", 18)

    # Initialize components
    canvas_feed = CanvasFeed(width, height)
    canvas_feed.set_decay(config.get("canvas", {}).get("decay_rate", 0.0))

    palette = Palette(size=4096)

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
    """WebSocket endpoint for real-time paint input."""
    await websocket.accept()
    connected_clients.add(websocket)

    # Send initial config
    await websocket.send_text(json.dumps({
        "type": "config",
        "width": config.get("matrix", {}).get("width", 32),
        "height": config.get("matrix", {}).get("height", 18),
    }))

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type")

            if msg_type == "touch_start":
                x, y = msg.get("x", 0.5), msg.get("y", 0.5)
                color = tuple(msg.get("color", [255, 255, 255]))
                radius = msg.get("radius", 2)
                if canvas_feed:
                    canvas_feed.touch_start(x, y, color=color, radius=radius)

            elif msg_type == "touch_move":
                x, y = msg.get("x", 0.5), msg.get("y", 0.5)
                if canvas_feed:
                    canvas_feed.touch_move(x, y)

            elif msg_type == "touch_end":
                if canvas_feed:
                    canvas_feed.touch_end()

            elif msg_type == "clear_canvas":
                if canvas_feed:
                    canvas_feed.clear()

            elif msg_type == "set_color":
                color = msg.get("color", [255, 255, 255])
                if canvas_feed:
                    canvas_feed.set_color(*color)

            elif msg_type == "set_radius":
                radius = msg.get("radius", 2)
                if canvas_feed:
                    canvas_feed.set_radius(radius)

            elif msg_type == "set_decay":
                rate = msg.get("rate", 0)
                if canvas_feed:
                    canvas_feed.set_decay(rate)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
    finally:
        connected_clients.discard(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
