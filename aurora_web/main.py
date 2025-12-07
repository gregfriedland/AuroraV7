"""Aurora Web - FastAPI application for LED matrix visualization.

Supports both finger paint mode (browser-sourced frames) and
pattern mode (server-generated frames from drawers).
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
from aurora_web.core.drawer_manager import DrawerManager
from aurora_web.drawers import (
    OffDrawer,
    AlienBlobDrawer,
    BzrDrawer,
    GrayScottDrawer,
    GinzburgLandauDrawer,
)


# Global state
config: dict = {}
serial_manager: Optional[SerialOutputManager] = None
drawer_manager: Optional[DrawerManager] = None
render_task: Optional[asyncio.Task] = None
connected_clients: set[WebSocket] = set()

# Frame from browser (used in paint mode)
browser_frame: Optional[np.ndarray] = None
browser_frame_lock = asyncio.Lock()


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
    """Main render loop - sends frames to LED matrix."""
    global browser_frame, serial_manager, drawer_manager

    matrix_cfg = config.get("matrix", {})
    target_fps = matrix_cfg.get("fps", 40)
    frame_time = 1.0 / target_fps
    local_frame_num = 0
    last_time = time.perf_counter()

    while True:
        frame_start = time.perf_counter()
        delta_time = frame_start - last_time
        last_time = frame_start

        if serial_manager and drawer_manager:
            # Get current frame based on mode
            async with browser_frame_lock:
                rgb = drawer_manager.get_frame(browser_frame)

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
                    "mode": drawer_manager.mode,
                    "drawer": drawer_manager.active_drawer.name if drawer_manager.active_drawer else None,
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
    global config, serial_manager, drawer_manager, render_task

    # Load config
    config = load_config()
    matrix_cfg = config.get("matrix", {})
    width = matrix_cfg.get("width", 32)
    height = matrix_cfg.get("height", 18)

    # Initialize drawer manager
    drawer_manager = DrawerManager(width, height)

    # Register drawers
    drawer_manager.register_drawer(OffDrawer(width, height))
    drawer_manager.register_drawer(AlienBlobDrawer(width, height))
    drawer_manager.register_drawer(BzrDrawer(width, height))
    drawer_manager.register_drawer(GrayScottDrawer(width, height))
    drawer_manager.register_drawer(GinzburgLandauDrawer(width, height))

    # Set default drawer
    drawer_manager.set_active_drawer("AlienBlob")

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
    print(f"[Aurora Web] Drawers: {list(drawer_manager.drawers.keys())}")

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


@app.get("/api/drawers")
async def get_drawers():
    """Get list of available drawers."""
    if drawer_manager:
        return {"drawers": drawer_manager.get_drawer_list()}
    return {"drawers": []}


@app.get("/api/status")
async def get_status():
    """Get current status."""
    if drawer_manager:
        return drawer_manager.get_status()
    return {"mode": "paint", "active_drawer": None, "drawers": []}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    global browser_frame, drawer_manager

    await websocket.accept()
    connected_clients.add(websocket)

    matrix_cfg = config.get("matrix", {})
    width = matrix_cfg.get("width", 32)
    height = matrix_cfg.get("height", 18)
    expected_size = width * height * 3

    # Send initial config
    init_msg = {
        "type": "config",
        "width": width,
        "height": height,
    }

    # Add drawer info
    if drawer_manager:
        init_msg["mode"] = drawer_manager.mode
        init_msg["drawers"] = drawer_manager.get_drawer_list()
        init_msg["active_drawer"] = drawer_manager.active_drawer.name if drawer_manager.active_drawer else None

    await websocket.send_text(json.dumps(init_msg))

    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message:
                # Binary frame data from browser (paint mode)
                data = message["bytes"]
                if len(data) == expected_size:
                    frame = np.frombuffer(data, dtype=np.uint8).reshape(height, width, 3)
                    async with browser_frame_lock:
                        browser_frame = frame.copy()

            elif "text" in message:
                # JSON message
                msg = json.loads(message["text"])
                msg_type = msg.get("type")

                if msg_type == "clear_canvas":
                    async with browser_frame_lock:
                        browser_frame = np.zeros((height, width, 3), dtype=np.uint8)

                elif msg_type == "set_mode":
                    # Switch between paint and pattern mode
                    mode = msg.get("mode", "paint")
                    if drawer_manager:
                        drawer_manager.set_mode(mode)
                        # Notify all clients
                        await broadcast(json.dumps({
                            "type": "mode_changed",
                            "mode": mode
                        }))

                elif msg_type == "set_drawer":
                    # Set active drawer
                    drawer_name = msg.get("drawer")
                    if drawer_manager and drawer_name:
                        if drawer_manager.set_active_drawer(drawer_name):
                            # Send updated settings
                            await websocket.send_text(json.dumps({
                                "type": "drawer_changed",
                                "drawer": drawer_name,
                                "settings": drawer_manager.active_drawer.get_settings_info()
                            }))

                elif msg_type == "set_drawer_settings":
                    # Update drawer settings
                    settings = msg.get("settings", {})
                    if drawer_manager:
                        drawer_manager.update_drawer_settings(settings)

                elif msg_type == "randomize_drawer":
                    # Randomize drawer settings
                    if drawer_manager and drawer_manager.active_drawer:
                        drawer_manager.active_drawer.randomize_settings()
                        await websocket.send_text(json.dumps({
                            "type": "drawer_changed",
                            "drawer": drawer_manager.active_drawer.name,
                            "settings": drawer_manager.active_drawer.get_settings_info()
                        }))

                elif msg_type == "get_drawers":
                    # Return list of drawers
                    if drawer_manager:
                        await websocket.send_text(json.dumps({
                            "type": "drawers_list",
                            "drawers": drawer_manager.get_drawer_list()
                        }))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
    finally:
        connected_clients.discard(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)
