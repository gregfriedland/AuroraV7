"""User authentication and profile API endpoints."""

from fastapi import APIRouter, HTTPException, Header, Response, Cookie
from pydantic import BaseModel


from aurora_web.core.users import UserManager

router = APIRouter(prefix="/api/users", tags=["users"])

# Global user manager - will be set during app startup
user_manager: UserManager | None = None


def set_user_manager(manager: UserManager) -> None:
    """Set the global user manager instance."""
    global user_manager
    user_manager = manager


def get_current_user(session_token: str | None = None):
    """Get current user from session token."""
    if not user_manager or not session_token:
        return None
    return user_manager.get_user_by_session(session_token)


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UpdateProfileRequest(BaseModel):
    default_drawer: str | None = None
    preferred_palette: str | None = None
    auto_rotate: bool | None = None
    rotate_interval: int | None = None


class FavoriteRequest(BaseModel):
    drawer_name: str


@router.post("/register")
async def register(request: RegisterRequest, response: Response):
    """Register a new user."""
    if not user_manager:
        raise HTTPException(status_code=500, detail="User manager not initialized")

    user = user_manager.create_user(request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Username already exists or invalid (3-20 alphanumeric chars, password min 4 chars)"
        )

    # Auto-login after registration
    token = user_manager.authenticate(request.username, request.password)
    if token:
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            max_age=86400 * 30,  # 30 days
            samesite="lax",
        )

    return {
        "success": True,
        "username": user.username,
        "message": "User created successfully"
    }


@router.post("/login")
async def login(request: LoginRequest, response: Response):
    """Login and create session."""
    if not user_manager:
        raise HTTPException(status_code=500, detail="User manager not initialized")

    token = user_manager.authenticate(request.username, request.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        max_age=86400 * 30,  # 30 days
        samesite="lax",
    )

    user = user_manager.get_user(request.username)
    return {
        "success": True,
        "username": user.username if user else request.username,
        "message": "Login successful"
    }


@router.post("/logout")
async def logout(
    response: Response,
    session_token: str | None = Cookie(None),
):
    """Logout and invalidate session."""
    if user_manager and session_token:
        user_manager.logout(session_token)

    response.delete_cookie("session_token")

    return {"success": True, "message": "Logged out"}


@router.get("/me")
async def get_current_user_profile(
    session_token: str | None = Cookie(None),
):
    """Get current user's profile."""
    if not user_manager:
        raise HTTPException(status_code=500, detail="User manager not initialized")

    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = user_manager.get_user_by_session(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    return {
        "username": user.username,
        "created_at": user.created_at,
        "last_login": user.last_login,
        "default_drawer": user.default_drawer,
        "favorite_drawers": user.favorite_drawers,
        "custom_drawers": user.custom_drawers,
        "preferred_palette": user.preferred_palette,
        "auto_rotate": user.auto_rotate,
        "rotate_interval": user.rotate_interval,
    }


@router.put("/me")
async def update_profile(
    request: UpdateProfileRequest,
    session_token: str | None = Cookie(None),
):
    """Update current user's profile."""
    if not user_manager:
        raise HTTPException(status_code=500, detail="User manager not initialized")

    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = user_manager.get_user_by_session(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    updates = request.model_dump(exclude_none=True)
    if updates:
        user_manager.update_user(user.username, updates)

    return {"success": True, "message": "Profile updated"}


@router.post("/me/favorites")
async def add_favorite(
    request: FavoriteRequest,
    session_token: str | None = Cookie(None),
):
    """Add a drawer to favorites."""
    if not user_manager:
        raise HTTPException(status_code=500, detail="User manager not initialized")

    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = user_manager.get_user_by_session(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    user_manager.add_favorite(user.username, request.drawer_name)
    return {"success": True, "message": f"Added {request.drawer_name} to favorites"}


@router.delete("/me/favorites/{drawer_name}")
async def remove_favorite(
    drawer_name: str,
    session_token: str | None = Cookie(None),
):
    """Remove a drawer from favorites."""
    if not user_manager:
        raise HTTPException(status_code=500, detail="User manager not initialized")

    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = user_manager.get_user_by_session(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    if user_manager.remove_favorite(user.username, drawer_name):
        return {"success": True, "message": f"Removed {drawer_name} from favorites"}

    raise HTTPException(status_code=404, detail="Drawer not in favorites")


@router.get("/list")
async def list_users():
    """List all usernames (admin/debug endpoint)."""
    if not user_manager:
        raise HTTPException(status_code=500, detail="User manager not initialized")

    return {"users": user_manager.list_users()}
