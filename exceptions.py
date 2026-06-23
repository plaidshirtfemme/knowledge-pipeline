class VideoTooLongError(Exception):
    """Video exceeds the configured duration limit."""

class IPBlockedError(Exception):
    """YouTube is blocking requests from this IP."""

class SubtitlesUnavailableError(Exception):
    """No subtitles or transcript could be found for this video."""

class NoTextError(Exception):
    """No usable text could be extracted from the source."""

class URLNotFoundError(Exception):
    """URL returned 404 or is otherwise unreachable."""

class UnsupportedSourceError(Exception):
    """Source platform is not yet supported by the pipeline."""
