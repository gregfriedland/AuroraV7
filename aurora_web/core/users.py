"""User profile management for Aurora Web."""

import yaml
import hashlib
import secrets
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any
from datetime import datetime


@dataclass
class UserProfile:
    """User profile with preferences and custom drawer ownership."""
    username: str
    password_hash: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_login: str | None = None

    # User preferences
    default_drawer: str | None = None
    favorite_drawers: list[str] = field(default_factory=list)
    custom_drawers: list[str] = field(default_factory=list)

    # Settings preferences
    preferred_palette: str | None = None
    auto_rotate: bool = False
    rotate_interval: int = 30

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'UserProfile':
        """Create from dictionary."""
        return cls(**data)


class UserManager:
    """Manages user profiles and authentication."""

    def __init__(self, users_db_path: str = "./users.yaml"):
        """Initialize user manager.

        Args:
            users_db_path: Path to users YAML database file
        """
        self.db_path = Path(users_db_path)
        self.users: dict[str, UserProfile] = {}
        self._sessions: dict[str, str] = {}  # session_token -> username
        self._load()

    def _load(self) -> None:
        """Load users from YAML file."""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r') as f:
                    data = yaml.safe_load(f) or {}

                for username, user_data in data.get('users', {}).items():
                    self.users[username] = UserProfile.from_dict(user_data)

            except Exception as e:
                print(f"[UserManager] Error loading users: {e}")
                self.users = {}

    def _save(self) -> None:
        """Save users to YAML file."""
        try:
            data = {
                'users': {
                    username: user.to_dict()
                    for username, user in self.users.items()
                }
            }

            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.db_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)

        except Exception as e:
            print(f"[UserManager] Error saving users: {e}")

    def _hash_password(self, password: str) -> str:
        """Hash a password using SHA-256.

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        return hashlib.sha256(password.encode()).hexdigest()

    def create_user(self, username: str, password: str) -> UserProfile | None:
        """Create a new user.

        Args:
            username: Username (alphanumeric, 3-20 chars)
            password: Password (min 4 chars)

        Returns:
            UserProfile if created, None if username exists or invalid
        """
        # Validate username
        if not username or len(username) < 3 or len(username) > 20:
            return None
        if not username.isalnum():
            return None
        if username.lower() in self.users:
            return None

        # Validate password
        if not password or len(password) < 4:
            return None

        # Create user
        user = UserProfile(
            username=username.lower(),
            password_hash=self._hash_password(password),
        )
        self.users[username.lower()] = user
        self._save()

        return user

    def authenticate(self, username: str, password: str) -> str | None:
        """Authenticate user and create session.

        Args:
            username: Username
            password: Password

        Returns:
            Session token if authenticated, None otherwise
        """
        username = username.lower()
        user = self.users.get(username)

        if not user:
            return None

        if user.password_hash != self._hash_password(password):
            return None

        # Update last login
        user.last_login = datetime.now().isoformat()
        self._save()

        # Create session token
        token = secrets.token_urlsafe(32)
        self._sessions[token] = username

        return token

    def logout(self, session_token: str) -> bool:
        """Logout user by invalidating session.

        Args:
            session_token: Session token to invalidate

        Returns:
            True if session was valid and removed
        """
        if session_token in self._sessions:
            del self._sessions[session_token]
            return True
        return False

    def get_user_by_session(self, session_token: str) -> UserProfile | None:
        """Get user profile from session token.

        Args:
            session_token: Session token

        Returns:
            UserProfile if valid session, None otherwise
        """
        username = self._sessions.get(session_token)
        if username:
            return self.users.get(username)
        return None

    def get_user(self, username: str) -> UserProfile | None:
        """Get user profile by username.

        Args:
            username: Username

        Returns:
            UserProfile if found, None otherwise
        """
        return self.users.get(username.lower())

    def update_user(self, username: str, updates: dict[str, Any]) -> bool:
        """Update user profile.

        Args:
            username: Username to update
            updates: Dict of fields to update

        Returns:
            True if updated successfully
        """
        user = self.users.get(username.lower())
        if not user:
            return False

        # Update allowed fields
        allowed_fields = {
            'default_drawer', 'favorite_drawers', 'custom_drawers',
            'preferred_palette', 'auto_rotate', 'rotate_interval'
        }

        for key, value in updates.items():
            if key in allowed_fields:
                setattr(user, key, value)

        self._save()
        return True

    def delete_user(self, username: str) -> bool:
        """Delete a user.

        Args:
            username: Username to delete

        Returns:
            True if deleted
        """
        username = username.lower()
        if username in self.users:
            del self.users[username]
            # Remove any sessions for this user
            self._sessions = {
                token: user for token, user in self._sessions.items()
                if user != username
            }
            self._save()
            return True
        return False

    def list_users(self) -> list[str]:
        """Get list of usernames.

        Returns:
            List of usernames
        """
        return list(self.users.keys())

    def add_custom_drawer(self, username: str, drawer_path: str) -> bool:
        """Add a custom drawer to user's list.

        Args:
            username: Username
            drawer_path: Relative path to drawer YAML

        Returns:
            True if added
        """
        user = self.users.get(username.lower())
        if not user:
            return False

        if drawer_path not in user.custom_drawers:
            user.custom_drawers.append(drawer_path)
            self._save()

        return True

    def remove_custom_drawer(self, username: str, drawer_path: str) -> bool:
        """Remove a custom drawer from user's list.

        Args:
            username: Username
            drawer_path: Relative path to drawer YAML

        Returns:
            True if removed
        """
        user = self.users.get(username.lower())
        if not user:
            return False

        if drawer_path in user.custom_drawers:
            user.custom_drawers.remove(drawer_path)
            self._save()
            return True

        return False

    def add_favorite(self, username: str, drawer_name: str) -> bool:
        """Add a drawer to user's favorites.

        Args:
            username: Username
            drawer_name: Drawer name

        Returns:
            True if added
        """
        user = self.users.get(username.lower())
        if not user:
            return False

        if drawer_name not in user.favorite_drawers:
            user.favorite_drawers.append(drawer_name)
            self._save()

        return True

    def remove_favorite(self, username: str, drawer_name: str) -> bool:
        """Remove a drawer from user's favorites.

        Args:
            username: Username
            drawer_name: Drawer name

        Returns:
            True if removed
        """
        user = self.users.get(username.lower())
        if not user:
            return False

        if drawer_name in user.favorite_drawers:
            user.favorite_drawers.remove(drawer_name)
            self._save()
            return True

        return False
