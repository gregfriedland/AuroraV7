"""Stub kms module for headless environments without DRM/KMS support.

picamera2 imports kms (pykms) for DRM preview, which requires
python3-kms++ system package. On headless setups (like LED matrix
controllers), we don't need DRM preview — only NullPreview is used.

This stub satisfies the import so picamera2 can load without error.
The DrmPreview class will fail at runtime if actually used, which is
fine since we never use it.
"""


class _Enum:
    """Attribute-access stub that returns 0 for any attribute."""
    def __getattr__(self, name):
        return 0


PixelFormat = _Enum()
PlaneType = _Enum()


class Card:
    pass


class ResourceManager:
    def __init__(self, *a, **kw):
        pass

    def reserve_connector(self, *a, **kw):
        return None

    def reserve_crtc(self, *a, **kw):
        return None

    def reserve_plane(self, *a, **kw):
        return None

    def reserve_overlay_plane(self, *a, **kw):
        return None


class DumbFramebuffer:
    def __init__(self, *a, **kw):
        pass


class DmabufFramebuffer:
    def __init__(self, *a, **kw):
        pass


class AtomicReq:
    def __init__(self, *a, **kw):
        pass

    def add(self, *a, **kw):
        pass

    def commit_sync(self, *a, **kw):
        pass
