"""Input feeds for Aurora Web."""

from .canvas_feed import CanvasFeed, Touch
from .audio_feed import AudioFeed, AudioInput, MockAudioFeed, Onset
from .video_feed import VideoFeed, VideoInput, MockVideoFeed

__all__ = [
    "CanvasFeed",
    "Touch",
    "AudioFeed",
    "AudioInput",
    "MockAudioFeed",
    "Onset",
    "VideoFeed",
    "VideoInput",
    "MockVideoFeed",
]
