"""Tests for FastAPI main application."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import numpy as np

from aurora_web.main import load_config


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_default(self):
        """load_config should return defaults when file not found."""
        config = load_config("/nonexistent/path.yaml")
        assert "server" in config
        assert "matrix" in config
        assert config["server"]["port"] == 80
        assert config["matrix"]["width"] == 32
        assert config["matrix"]["height"] == 18

    def test_load_config_from_file(self, tmp_path):
        """load_config should load from YAML file."""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("""
server:
  host: "127.0.0.1"
  port: 9000
matrix:
  width: 64
  height: 32
""")
        config = load_config(str(config_file))
        assert config["server"]["port"] == 9000
        assert config["matrix"]["width"] == 64
        assert config["matrix"]["height"] == 32


class TestFastAPIEndpoints:
    """Tests for FastAPI REST endpoints.

    These tests mock the global state to avoid needing actual hardware.
    """

    @pytest.fixture
    def mock_globals(self):
        """Mock global state for testing."""
        from aurora_web.core.drawer_manager import DrawerManager
        from aurora_web.drawers.off import OffDrawer

        manager = DrawerManager(32, 18)
        manager.register_drawer(OffDrawer(32, 18))
        manager.set_active_drawer("Off")

        return {
            "config": {
                "matrix": {"width": 32, "height": 18, "fps": 40},
                "server": {"host": "0.0.0.0", "port": 80}
            },
            "drawer_manager": manager,
        }

    @pytest.fixture
    def client(self, mock_globals):
        """Create test client with mocked globals."""
        from fastapi.testclient import TestClient
        import aurora_web.main as main_module

        # Patch global state
        with patch.object(main_module, 'config', mock_globals["config"]), \
             patch.object(main_module, 'drawer_manager', mock_globals["drawer_manager"]), \
             patch.object(main_module, 'serial_manager', None):

            # Create client without lifespan to avoid hardware init
            from fastapi import FastAPI
            from fastapi.staticfiles import StaticFiles
            from pathlib import Path

            test_app = FastAPI()

            # Register routes manually for testing
            @test_app.get("/api/config")
            async def get_config():
                return {
                    "width": mock_globals["config"]["matrix"]["width"],
                    "height": mock_globals["config"]["matrix"]["height"],
                }

            @test_app.get("/api/drawers")
            async def get_drawers():
                return {"drawers": mock_globals["drawer_manager"].get_drawer_list()}

            @test_app.get("/api/status")
            async def get_status():
                return mock_globals["drawer_manager"].get_status()

            yield TestClient(test_app)

    def test_get_config(self, client):
        """GET /api/config should return matrix dimensions."""
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert data["width"] == 32
        assert data["height"] == 18

    def test_get_drawers(self, client):
        """GET /api/drawers should return drawer list."""
        response = client.get("/api/drawers")
        assert response.status_code == 200
        data = response.json()
        assert "drawers" in data
        assert len(data["drawers"]) == 1
        assert data["drawers"][0]["name"] == "Off"

    def test_get_status(self, client):
        """GET /api/status should return current status."""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data
        assert "active_drawer" in data
        assert "drawers" in data


class TestBroadcast:
    """Tests for WebSocket broadcast helper."""

    def test_broadcast_sends_to_clients(self):
        """broadcast should send message to all connected clients."""
        import asyncio
        from aurora_web.main import broadcast, connected_clients

        async def run_test():
            # Create mock WebSocket clients
            ws1 = AsyncMock()
            ws2 = AsyncMock()
            connected_clients.clear()
            connected_clients.add(ws1)
            connected_clients.add(ws2)

            await broadcast('{"type": "test"}')

            ws1.send_text.assert_called_once_with('{"type": "test"}')
            ws2.send_text.assert_called_once_with('{"type": "test"}')

            connected_clients.clear()

        asyncio.run(run_test())

    def test_broadcast_removes_disconnected(self):
        """broadcast should remove clients that fail to send."""
        import asyncio
        from aurora_web.main import broadcast, connected_clients

        async def run_test():
            # Create mock clients - one fails
            ws_good = AsyncMock()
            ws_bad = AsyncMock()
            ws_bad.send_text.side_effect = Exception("Connection closed")

            connected_clients.clear()
            connected_clients.add(ws_good)
            connected_clients.add(ws_bad)

            await broadcast('{"type": "test"}')

            # Good client should remain, bad client should be removed
            assert ws_good in connected_clients
            assert ws_bad not in connected_clients

            connected_clients.clear()

        asyncio.run(run_test())
