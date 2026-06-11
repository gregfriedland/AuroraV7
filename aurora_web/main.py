"""Aurora Web - FastAPI application for LED matrix visualization.

Supports both finger paint mode (browser-sourced frames) and
pattern mode (server-generated frames from drawers).
"""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from pathlib import Path


import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import numpy as np

from aurora_web.core.find_beats import ExternalBeatFeed
from aurora_web.core.output_factory import OutputManager, OutputManagerFactory
from aurora_web.core.drawer_manager import DrawerManager
from aurora_web.core.users import UserManager
from aurora_web.core.palette import Palette
from aurora_web.drawers import (
    OffDrawer,
    AlienBlobDrawer,
    BzrDrawer,
    GrayScottDrawer,
    GinzburgLandauDrawer,
    AudioVizDrawer,
    BeatBouncerDrawer,
    CameraDrawer,
    SignalGridDrawer,
)
from aurora_web.inputs.audio_feed import AudioFeed
from aurora_web.inputs.video_feed import VideoFeed
import math

from aurora_web.drawers.custom import CustomDrawer, CustomDrawerLoader, EXAMPLE_DRAWER_YAML
from aurora_web.drawers.base import Drawer, DrawerContext
from aurora_web.api import users_router, custom_drawers_router
from aurora_web.api import users as users_api
from aurora_web.api import custom_drawers as custom_drawers_api


class LiveCodeDrawer(Drawer):
    """Drawer that runs user code with a simple canvas-based API.

    The user's draw function receives (canvas, t, dt) and writes RGB
    values directly into the canvas array.
    """

    # Flag so DrawerManager knows to skip palette conversion
    returns_rgb = True

    def __init__(self, width: int, height: int, code: str):
        super().__init__("LiveCode", width, height)
        self.paused = False
        self._last_frame = np.zeros((height, width, 3), dtype=np.uint8)
        self._compile(code)

    # Color constants available in user code
    COLORS = {
        "BLACK": np.array([0, 0, 0], dtype=np.uint8),
        "WHITE": np.array([255, 255, 255], dtype=np.uint8),
        "RED": np.array([255, 0, 0], dtype=np.uint8),
        "GREEN": np.array([0, 255, 0], dtype=np.uint8),
        "BLUE": np.array([0, 0, 255], dtype=np.uint8),
        "YELLOW": np.array([255, 255, 0], dtype=np.uint8),
        "CYAN": np.array([0, 255, 255], dtype=np.uint8),
        "MAGENTA": np.array([255, 0, 255], dtype=np.uint8),
        "ORANGE": np.array([255, 127, 0], dtype=np.uint8),
        "PURPLE": np.array([128, 0, 255], dtype=np.uint8),
        "PINK": np.array([255, 105, 180], dtype=np.uint8),
        "GRAY": np.array([128, 128, 128], dtype=np.uint8),
    }

    def _compile(self, code: str) -> None:
        namespace = {
            "np": np,
            "numpy": np,
            "math": math,
            **self.COLORS,
            "__builtins__": {
                "range": range,
                "len": len,
                "int": int,
                "float": float,
                "abs": abs,
                "min": min,
                "max": max,
                "sum": sum,
                "enumerate": enumerate,
                "zip": zip,
                "map": map,
                "list": list,
                "tuple": tuple,
                "bool": bool,
                "print": print,
                "round": round,
            },
        }
        exec(code, namespace)
        if "draw" not in namespace:
            raise ValueError("Code must define a 'draw(canvas, t, dt)' function")
        self._draw_func = namespace["draw"]

    def reset(self) -> None:
        pass

    def draw(self, ctx: DrawerContext) -> np.ndarray:
        if self.paused:
            return self._last_frame

        canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        try:
            self._draw_func(canvas, ctx.time, ctx.delta_time)
        except Exception as e:
            print(f"[LiveCode] Error in draw(): {e}")
        self._last_frame = np.clip(canvas, 0, 255).astype(np.uint8)
        return self._last_frame


# Global state
config: dict = {}
serial_manager: OutputManager | None = None
drawer_manager: DrawerManager | None = None
user_manager: UserManager | None = None
custom_drawer_loader: CustomDrawerLoader | None = None
beat_feed: ExternalBeatFeed | None = None
audio_feed: AudioFeed | None = None
video_feed: VideoFeed | None = None
render_task: asyncio.Task | None = None
connected_clients: set[WebSocket] = set()

# Frame from browser (used in paint mode)
browser_frame: np.ndarray | None = None
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
            "output_driver": "serial",
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

            # Check for auto-rotation
            rotation_result = drawer_manager.check_auto_rotate()
            if rotation_result and connected_clients:
                await broadcast(json.dumps({
                    "type": "auto_rotated",
                    "drawer": rotation_result.get("drawer"),
                    "palette_index": rotation_result.get("palette_index"),
                    "settings": rotation_result.get("settings"),
                }))

            # Broadcast preview frame to clients every 4 frames (~10fps)
            if local_frame_num % 4 == 0 and connected_clients and drawer_manager.mode == "pattern":
                await broadcast_bytes(rgb.tobytes())

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
    """Broadcast text message to all connected WebSocket clients."""
    disconnected = set()
    for ws in list(connected_clients):  # Iterate over a copy
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    connected_clients.difference_update(disconnected)


async def broadcast_bytes(data: bytes):
    """Broadcast binary data to all connected WebSocket clients."""
    disconnected = set()
    for ws in list(connected_clients):
        try:
            await ws.send_bytes(data)
        except Exception:
            disconnected.add(ws)
    connected_clients.difference_update(disconnected)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    global config, serial_manager, drawer_manager, user_manager, custom_drawer_loader, beat_feed, audio_feed, video_feed, render_task

    # Load config
    config = load_config()
    matrix_cfg = config.get("matrix", {})
    width = matrix_cfg.get("width", 32)
    height = matrix_cfg.get("height", 18)

    # Initialize user manager
    users_db_path = config.get("users_db", "./users.yaml")
    user_manager = UserManager(users_db_path)
    users_api.set_user_manager(user_manager)
    custom_drawers_api.set_user_manager(user_manager)
    print(f"[Aurora Web] Users DB: {users_db_path}")

    # Initialize custom drawer loader
    custom_drawers_path = Path(config.get("custom_drawers_path", "./custom_drawers"))
    custom_drawer_loader = CustomDrawerLoader(
        custom_drawers_path, width, height, palette_size=4096
    )
    custom_drawers_api.set_custom_drawer_loader(custom_drawer_loader)
    print(f"[Aurora Web] Custom drawers path: {custom_drawers_path}")

    # Start external beat feed if configured
    beats_cfg = config.get("inputs", {}).get("beats", {})
    find_beats_cmd = (
        config.get("findBeatsCmd")
        or beats_cfg.get("findBeatsCmd")
        or beats_cfg.get("find_beats_cmd")
    )
    if find_beats_cmd:
        beat_feed = ExternalBeatFeed(
            str(find_beats_cmd),
            onset_duration=float(beats_cfg.get("onset_duration", 0.2)),
        )
        beat_feed.start()

    # Start audio feed if enabled
    audio_cfg = config.get("inputs", {}).get("audio", {})
    if audio_cfg.get("enabled", False):
        try:
            audio_feed = AudioFeed(
                source=audio_cfg.get("source", "pulse"),
                beat_tracker=str(audio_cfg.get("beat_tracker", "internal")),
                latency_ms=float(audio_cfg.get("latency_ms", 60.0)),
                source_lambda=float(audio_cfg.get("source_lambda", 0.35)),
            )
            await audio_feed.start()
            if not audio_feed.is_running:
                audio_feed = None
        except Exception as e:
            print(f"[Aurora Web] Audio feed unavailable: {e}")
            audio_feed = None

    # Initialize drawer manager
    drawer_manager = DrawerManager(width, height, beat_feed=beat_feed, audio_feed=audio_feed)
    custom_drawers_api.set_drawer_manager(drawer_manager)

    # Register built-in drawers
    drawer_manager.register_drawer(OffDrawer(width, height))
    drawer_manager.register_drawer(AlienBlobDrawer(width, height))
    drawer_manager.register_drawer(BzrDrawer(width, height))
    drawer_manager.register_drawer(GrayScottDrawer(width, height))
    drawer_manager.register_drawer(GinzburgLandauDrawer(width, height))
    if beat_feed:
        drawer_manager.register_drawer(BeatBouncerDrawer(width, height))
    if audio_feed:
        drawer_manager.register_drawer(AudioVizDrawer(width, height))
        drawer_manager.register_drawer(SignalGridDrawer(width, height))

    # Camera drawer with lazy video feed (not started until Camera is selected)
    video_cfg = config.get("inputs", {}).get("video", {})
    video_feed = VideoFeed(
        device=int(video_cfg.get("device", 0)),
        enable_face_detection=bool(video_cfg.get("enable_face_detection", False)),
    )
    drawer_manager.register_drawer(CameraDrawer(width, height, video_feed=video_feed))

    # Start/stop video feed when switching to/from Camera drawer
    loop = asyncio.get_event_loop()

    def on_drawer_change(old_name, new_name):
        if new_name == "Camera" and not video_feed.is_running:
            loop.create_task(video_feed.start())
            print("[Aurora Web] Started video feed for Camera drawer")
        elif old_name == "Camera" and video_feed.is_running:
            loop.create_task(video_feed.stop())
            print("[Aurora Web] Stopped video feed (Camera deselected)")
    drawer_manager._on_drawer_change = on_drawer_change

    # Load and register custom drawers
    for drawer_info in custom_drawer_loader.list_drawers():
        try:
            custom_drawer = custom_drawer_loader.load_drawer(drawer_info['path'])
            custom_drawer.name = f"Custom:{drawer_info['path'].replace('.yaml', '')}"
            drawer_manager.register_drawer(custom_drawer)
            print(f"[Aurora Web] Loaded custom drawer: {custom_drawer.name}")
        except Exception as e:
            print(f"[Aurora Web] Failed to load custom drawer {drawer_info['path']}: {e}")

    # Start in pattern mode with the configured default drawer,
    # falling back to a random pattern
    drawer_manager.set_mode("pattern")
    default_drawer = config.get("default_drawer", "AudioViz")
    if default_drawer in drawer_manager.drawers:
        drawer_manager.set_active_drawer(default_drawer)
        # dark-background palette so source boxes have contrast
        palette_idx = int(config.get("default_palette", 11))
        drawer_manager.palette.set_curated(palette_idx)
        drawer_manager.current_palette_index = palette_idx
        print(f"[Aurora Web] Auto-started with: {default_drawer}, palette #{palette_idx}")
    else:
        result = drawer_manager.randomize_all()
        print(f"[Aurora Web] Auto-started with: {result.get('drawer')}, palette #{result.get('palette_index')}")

    # Start hardware output process
    serial_manager = OutputManagerFactory.create(matrix_cfg)
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
    if beat_feed:
        beat_feed.stop()
    if audio_feed and audio_feed.is_running:
        await audio_feed.stop()
    if video_feed and video_feed.is_running:
        await video_feed.stop()


app = FastAPI(title="Aurora Web", lifespan=lifespan)

# Include API routers
app.include_router(users_router)
app.include_router(custom_drawers_router)

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
        init_msg["palette_index"] = drawer_manager.current_palette_index
        init_msg["palette_count"] = Palette.curated_count()

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
                        drawer_manager.user_interacted()
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
                        drawer_manager.user_interacted()
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
                        drawer_manager.user_interacted()
                        drawer_manager.update_drawer_settings(settings)

                elif msg_type == "randomize_drawer":
                    # Randomize drawer settings and palette
                    if drawer_manager and drawer_manager.active_drawer:
                        drawer_manager.user_interacted()
                        drawer_manager.active_drawer.randomize_settings()
                        # Also randomize palette
                        import random
                        drawer_manager.current_palette_index = random.randint(0, Palette.curated_count() - 1)
                        drawer_manager.palette.set_curated(drawer_manager.current_palette_index)
                        await websocket.send_text(json.dumps({
                            "type": "drawer_changed",
                            "drawer": drawer_manager.active_drawer.name,
                            "settings": drawer_manager.active_drawer.get_settings_info(),
                            "palette_index": drawer_manager.current_palette_index
                        }))

                elif msg_type == "set_palette":
                    # Set palette by index
                    palette_index = msg.get("index", 0)
                    if drawer_manager:
                        drawer_manager.user_interacted()
                        drawer_manager.current_palette_index = palette_index % Palette.curated_count()
                        drawer_manager.palette.set_curated(drawer_manager.current_palette_index)

                elif msg_type == "get_drawers":
                    # Return list of drawers
                    if drawer_manager:
                        await websocket.send_text(json.dumps({
                            "type": "drawers_list",
                            "drawers": drawer_manager.get_drawer_list()
                        }))

                elif msg_type == "submit_code":
                    # Compile and activate user-submitted draw code
                    code = msg.get("code", "")
                    if drawer_manager and code:
                        try:
                            live_drawer = LiveCodeDrawer(width, height, code)
                            drawer_manager.register_drawer(live_drawer)
                            drawer_manager.set_active_drawer("LiveCode")
                            drawer_manager.set_mode("pattern")
                            drawer_manager.user_interacted()

                            await websocket.send_text(json.dumps({
                                "type": "code_result",
                                "success": True,
                            }))
                            await broadcast(json.dumps({
                                "type": "drawer_changed",
                                "drawer": "LiveCode",
                                "settings": live_drawer.get_settings_info(),
                                "palette_index": drawer_manager.current_palette_index,
                            }))
                        except Exception as e:
                            await websocket.send_text(json.dumps({
                                "type": "code_result",
                                "success": False,
                                "error": str(e),
                            }))

                elif msg_type == "stop_code":
                    # Pause live code — freeze on last rendered frame
                    if drawer_manager and drawer_manager.active_drawer and drawer_manager.active_drawer.name == "LiveCode":
                        drawer_manager.active_drawer.paused = True
                        drawer_manager.user_interacted()

                elif msg_type == "get_code_template":
                    # Send example draw function code
                    template_code = (
                        "# Colors: BLACK, WHITE, RED, GREEN, BLUE,\n"
                        "#   YELLOW, CYAN, MAGENTA, ORANGE, PURPLE,\n"
                        "#   PINK, GRAY\n"
                        "\n"
                        "def draw(canvas, t, dt):\n"
                        "    h, w, _ = canvas.shape\n"
                        "    x = int(t * 5) % w\n"
                        "    y = h // 2\n"
                        "    canvas[y, x] = WHITE\n"
                    )
                    await websocket.send_text(json.dumps({
                        "type": "code_template",
                        "code": template_code,
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
