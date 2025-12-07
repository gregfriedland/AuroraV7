"""Custom drawer API endpoints for creating and managing user-defined patterns."""

from fastapi import APIRouter, HTTPException, Cookie
from pydantic import BaseModel
from typing import Any
from pathlib import Path

from aurora_web.drawers.custom import CustomDrawer, CustomDrawerLoader, EXAMPLE_DRAWER_YAML
from aurora_web.core.users import UserManager

router = APIRouter(prefix="/api/custom-drawers", tags=["custom-drawers"])

# Global references - set during app startup
custom_drawer_loader: CustomDrawerLoader | None = None
user_manager: UserManager | None = None
drawer_manager = None  # Reference to main drawer manager


def set_custom_drawer_loader(loader: CustomDrawerLoader) -> None:
    """Set the global custom drawer loader."""
    global custom_drawer_loader
    custom_drawer_loader = loader


def set_user_manager(manager: UserManager) -> None:
    """Set the global user manager."""
    global user_manager
    user_manager = manager


def set_drawer_manager(manager) -> None:
    """Set the global drawer manager."""
    global drawer_manager
    drawer_manager = manager


class DrawerDefinition(BaseModel):
    """Custom drawer definition request."""
    name: str
    description: str | None = ""
    uses_audio: bool = False
    uses_video: bool = False
    uses_canvas: bool = False
    settings: dict[str, Any] = {}
    code: str


class UpdateDrawerRequest(BaseModel):
    """Request to update an existing drawer."""
    name: str | None = None
    description: str | None = None
    uses_audio: bool | None = None
    uses_video: bool | None = None
    uses_canvas: bool | None = None
    settings: dict[str, Any | None] = None
    code: str | None = None


def get_user_from_session(session_token: str | None):
    """Get user from session token."""
    if not user_manager or not session_token:
        return None
    return user_manager.get_user_by_session(session_token)


@router.get("/list")
async def list_custom_drawers(
    username: str | None = None,
    session_token: str | None = Cookie(None),
):
    """List available custom drawers.

    If username is provided, only show that user's drawers.
    If not provided, show all custom drawers.
    """
    if not custom_drawer_loader:
        raise HTTPException(status_code=500, detail="Custom drawer loader not initialized")

    drawers = custom_drawer_loader.list_drawers(username)
    return {"drawers": drawers}


@router.get("/my-drawers")
async def list_my_drawers(
    session_token: str | None = Cookie(None),
):
    """List current user's custom drawers."""
    if not custom_drawer_loader:
        raise HTTPException(status_code=500, detail="Custom drawer loader not initialized")

    user = get_user_from_session(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    drawers = custom_drawer_loader.list_drawers(user.username)
    return {"drawers": drawers}


@router.get("/template")
async def get_template():
    """Get the example drawer template YAML."""
    return {
        "template": EXAMPLE_DRAWER_YAML,
        "message": "Use this template as a starting point for your custom drawer"
    }


@router.post("/create")
async def create_custom_drawer(
    definition: DrawerDefinition,
    session_token: str | None = Cookie(None),
):
    """Create a new custom drawer."""
    if not custom_drawer_loader or not user_manager:
        raise HTTPException(status_code=500, detail="Service not initialized")

    user = get_user_from_session(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Build YAML definition
    yaml_def = {
        'name': definition.name,
        'author': user.username,
        'description': definition.description,
        'uses': {
            'audio': definition.uses_audio,
            'video': definition.uses_video,
            'canvas': definition.uses_canvas,
        },
        'settings': definition.settings,
        'code': definition.code,
    }

    # Validate by trying to create the drawer
    try:
        test_drawer = CustomDrawer.from_yaml_string(
            yaml.dump(yaml_def),
            width=32, height=18,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid drawer definition: {e}")

    # Save the drawer
    try:
        relative_path = custom_drawer_loader.save_drawer(
            user.username,
            definition.name,
            yaml_def,
        )

        # Add to user's custom drawers list
        user_manager.add_custom_drawer(user.username, relative_path)

        return {
            "success": True,
            "path": relative_path,
            "message": f"Drawer '{definition.name}' created successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save drawer: {e}")


@router.get("/{username}/{drawer_name}")
async def get_custom_drawer(username: str, drawer_name: str):
    """Get a specific custom drawer definition."""
    if not custom_drawer_loader:
        raise HTTPException(status_code=500, detail="Custom drawer loader not initialized")

    # Construct path
    relative_path = f"{username}/{drawer_name}.yaml"
    yaml_path = custom_drawer_loader.base_path / relative_path

    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail="Drawer not found")

    try:
        import yaml
        with open(yaml_path, 'r') as f:
            definition = yaml.safe_load(f)

        return {
            "path": relative_path,
            "definition": definition
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load drawer: {e}")


@router.put("/{username}/{drawer_name}")
async def update_custom_drawer(
    username: str,
    drawer_name: str,
    updates: UpdateDrawerRequest,
    session_token: str | None = Cookie(None),
):
    """Update an existing custom drawer."""
    if not custom_drawer_loader or not user_manager:
        raise HTTPException(status_code=500, detail="Service not initialized")

    user = get_user_from_session(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Only allow updating own drawers
    if user.username != username:
        raise HTTPException(status_code=403, detail="Can only update your own drawers")

    # Load existing definition
    relative_path = f"{username}/{drawer_name}.yaml"
    yaml_path = custom_drawer_loader.base_path / relative_path

    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail="Drawer not found")

    try:
        import yaml
        with open(yaml_path, 'r') as f:
            definition = yaml.safe_load(f)

        # Apply updates
        if updates.name is not None:
            definition['name'] = updates.name
        if updates.description is not None:
            definition['description'] = updates.description
        if updates.uses_audio is not None:
            definition.setdefault('uses', {})['audio'] = updates.uses_audio
        if updates.uses_video is not None:
            definition.setdefault('uses', {})['video'] = updates.uses_video
        if updates.uses_canvas is not None:
            definition.setdefault('uses', {})['canvas'] = updates.uses_canvas
        if updates.settings is not None:
            definition['settings'] = updates.settings
        if updates.code is not None:
            definition['code'] = updates.code

        # Validate the updated definition
        try:
            test_drawer = CustomDrawer.from_yaml_string(
                yaml.dump(definition),
                width=32, height=18,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid drawer definition: {e}")

        # Save updated definition
        with open(yaml_path, 'w') as f:
            yaml.dump(definition, f, default_flow_style=False)

        return {
            "success": True,
            "message": f"Drawer '{drawer_name}' updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update drawer: {e}")


@router.delete("/{username}/{drawer_name}")
async def delete_custom_drawer(
    username: str,
    drawer_name: str,
    session_token: str | None = Cookie(None),
):
    """Delete a custom drawer."""
    if not custom_drawer_loader or not user_manager:
        raise HTTPException(status_code=500, detail="Service not initialized")

    user = get_user_from_session(session_token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Only allow deleting own drawers
    if user.username != username:
        raise HTTPException(status_code=403, detail="Can only delete your own drawers")

    relative_path = f"{username}/{drawer_name}.yaml"

    if custom_drawer_loader.delete_drawer(relative_path):
        user_manager.remove_custom_drawer(user.username, relative_path)
        return {
            "success": True,
            "message": f"Drawer '{drawer_name}' deleted successfully"
        }

    raise HTTPException(status_code=404, detail="Drawer not found")


@router.post("/{username}/{drawer_name}/activate")
async def activate_custom_drawer(
    username: str,
    drawer_name: str,
):
    """Load and activate a custom drawer."""
    if not custom_drawer_loader or not drawer_manager:
        raise HTTPException(status_code=500, detail="Service not initialized")

    relative_path = f"{username}/{drawer_name}.yaml"

    try:
        custom_drawer = custom_drawer_loader.load_drawer(relative_path)

        # Register with drawer manager if not already registered
        full_name = f"Custom:{username}/{drawer_name}"
        custom_drawer.name = full_name

        drawer_manager.register_drawer(custom_drawer)
        drawer_manager.set_active_drawer(full_name)

        return {
            "success": True,
            "drawer": full_name,
            "message": f"Activated custom drawer '{drawer_name}'"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to activate drawer: {e}")


@router.post("/validate")
async def validate_drawer_code(definition: DrawerDefinition):
    """Validate drawer code without saving.

    Returns compilation errors if any, or success if valid.
    """
    import yaml

    yaml_def = {
        'name': definition.name,
        'author': 'validator',
        'description': definition.description,
        'uses': {
            'audio': definition.uses_audio,
            'video': definition.uses_video,
            'canvas': definition.uses_canvas,
        },
        'settings': definition.settings,
        'code': definition.code,
    }

    try:
        test_drawer = CustomDrawer.from_yaml_string(
            yaml.dump(yaml_def),
            width=32, height=18,
        )
        return {
            "valid": True,
            "message": "Drawer code is valid"
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }


# Import yaml for the endpoints that need it
import yaml
