"""Tests for UserManager and UserProfile."""

import pytest
import tempfile
from pathlib import Path

from aurora_web.core.users import UserManager, UserProfile


class TestUserProfile:
    """Tests for UserProfile dataclass."""

    def test_creation(self):
        """UserProfile should be created with required fields."""
        profile = UserProfile(
            username="testuser",
            password_hash="abc123",
        )
        assert profile.username == "testuser"
        assert profile.password_hash == "abc123"
        assert profile.favorite_drawers == []
        assert profile.custom_drawers == []

    def test_to_dict(self):
        """to_dict() should serialize all fields."""
        profile = UserProfile(
            username="testuser",
            password_hash="abc123",
            default_drawer="AlienBlob",
        )
        data = profile.to_dict()
        assert data["username"] == "testuser"
        assert data["password_hash"] == "abc123"
        assert data["default_drawer"] == "AlienBlob"

    def test_from_dict(self):
        """from_dict() should deserialize profile."""
        data = {
            "username": "testuser",
            "password_hash": "abc123",
            "created_at": "2025-01-01T00:00:00",
            "last_login": None,
            "default_drawer": "Bzr",
            "favorite_drawers": ["AlienBlob", "Bzr"],
            "custom_drawers": [],
            "preferred_palette": None,
            "auto_rotate": True,
            "rotate_interval": 60,
        }
        profile = UserProfile.from_dict(data)
        assert profile.username == "testuser"
        assert profile.default_drawer == "Bzr"
        assert profile.auto_rotate is True


class TestUserManager:
    """Tests for UserManager class."""

    def test_initialization(self):
        """UserManager should initialize with path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))
            assert manager.users == {}

    def test_create_user(self):
        """create_user() should create a new user."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            user = manager.create_user("testuser", "password123")
            assert user is not None
            assert user.username == "testuser"
            assert user.password_hash != "password123"  # Should be hashed

    def test_create_user_duplicate(self):
        """create_user() should fail for duplicate username."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            manager.create_user("testuser", "password123")
            duplicate = manager.create_user("testuser", "different")
            assert duplicate is None

    def test_create_user_invalid_username(self):
        """create_user() should fail for invalid username."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            # Too short
            assert manager.create_user("ab", "password") is None
            # Too long
            assert manager.create_user("a" * 21, "password") is None
            # Non-alphanumeric
            assert manager.create_user("test@user", "password") is None

    def test_create_user_invalid_password(self):
        """create_user() should fail for invalid password."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            # Too short
            assert manager.create_user("testuser", "abc") is None

    def test_authenticate_success(self):
        """authenticate() should return token for valid credentials."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            manager.create_user("testuser", "password123")
            token = manager.authenticate("testuser", "password123")

            assert token is not None
            assert len(token) > 20

    def test_authenticate_wrong_password(self):
        """authenticate() should return None for wrong password."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            manager.create_user("testuser", "password123")
            token = manager.authenticate("testuser", "wrongpassword")

            assert token is None

    def test_authenticate_unknown_user(self):
        """authenticate() should return None for unknown user."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            token = manager.authenticate("unknown", "password")
            assert token is None

    def test_get_user_by_session(self):
        """get_user_by_session() should return user for valid token."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            manager.create_user("testuser", "password123")
            token = manager.authenticate("testuser", "password123")
            user = manager.get_user_by_session(token)

            assert user is not None
            assert user.username == "testuser"

    def test_get_user_by_session_invalid(self):
        """get_user_by_session() should return None for invalid token."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            user = manager.get_user_by_session("invalid_token")
            assert user is None

    def test_logout(self):
        """logout() should invalidate session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            manager.create_user("testuser", "password123")
            token = manager.authenticate("testuser", "password123")

            assert manager.logout(token) is True
            assert manager.get_user_by_session(token) is None

    def test_update_user(self):
        """update_user() should update allowed fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            manager.create_user("testuser", "password123")
            result = manager.update_user("testuser", {
                "default_drawer": "Bzr",
                "auto_rotate": True,
            })

            assert result is True
            user = manager.get_user("testuser")
            assert user.default_drawer == "Bzr"
            assert user.auto_rotate is True

    def test_delete_user(self):
        """delete_user() should remove user."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            manager.create_user("testuser", "password123")
            result = manager.delete_user("testuser")

            assert result is True
            assert manager.get_user("testuser") is None

    def test_add_favorite(self):
        """add_favorite() should add drawer to favorites."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            manager.create_user("testuser", "password123")
            manager.add_favorite("testuser", "AlienBlob")

            user = manager.get_user("testuser")
            assert "AlienBlob" in user.favorite_drawers

    def test_remove_favorite(self):
        """remove_favorite() should remove drawer from favorites."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            manager.create_user("testuser", "password123")
            manager.add_favorite("testuser", "AlienBlob")
            manager.remove_favorite("testuser", "AlienBlob")

            user = manager.get_user("testuser")
            assert "AlienBlob" not in user.favorite_drawers

    def test_add_custom_drawer(self):
        """add_custom_drawer() should add drawer path to user."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            manager.create_user("testuser", "password123")
            manager.add_custom_drawer("testuser", "testuser/my_drawer.yaml")

            user = manager.get_user("testuser")
            assert "testuser/my_drawer.yaml" in user.custom_drawers

    def test_persistence(self):
        """User data should persist across manager instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"

            # Create user with first manager
            manager1 = UserManager(str(db_path))
            manager1.create_user("testuser", "password123")
            manager1.add_favorite("testuser", "Bzr")

            # Load with second manager
            manager2 = UserManager(str(db_path))
            user = manager2.get_user("testuser")

            assert user is not None
            assert user.username == "testuser"
            assert "Bzr" in user.favorite_drawers

    def test_list_users(self):
        """list_users() should return all usernames."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            manager.create_user("user1", "password1")
            manager.create_user("user2", "password2")

            users = manager.list_users()
            assert "user1" in users
            assert "user2" in users
            assert len(users) == 2

    def test_case_insensitive_username(self):
        """Username should be case-insensitive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "users.yaml"
            manager = UserManager(str(db_path))

            manager.create_user("TestUser", "password123")

            # Should find with different case
            user = manager.get_user("testuser")
            assert user is not None
            assert user.username == "testuser"

            # Should authenticate with different case
            token = manager.authenticate("TESTUSER", "password123")
            assert token is not None

            # Should not allow duplicate with different case
            duplicate = manager.create_user("TESTUSER", "different")
            assert duplicate is None
