"""Translate CLI choices into yt-dlp parameter dicts.

Everything here is pure (no network, no filesystem writes) so it can be unit-tested.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from yt_dlp.utils import download_range_func, parse_bytes

Container = Literal["mp4", "mkv"]
AudioCodec = Literal["m4a", "mp3", "opus", "best"]
AUDIO_CODECS: tuple[AudioCodec, ...] = ("m4a", "mp3", "opus", "best")

# Which YouTube audio stream to fetch for each target, so m4a/opus are a lossless copy.
AUDIO_FORMATS: dict[AudioCodec, str] = {
    "m4a": "ba[acodec^=mp4a]/ba/b",
    "opus": "ba[acodec=opus]/ba/b",
    "mp3": "ba/b",
    "best": "ba/b",
}
DEFAULT_MP3_QUALITY = "2"  # LAME VBR V2, roughly 190 kbps

OUTPUT_TEMPLATE = "%(title)s [%(id)s].%(ext)s"
# Include the range so clips never overwrite the full video or each other.
CLIP_OUTPUT_TEMPLATE = "%(title)s [%(id)s] %(section_start>%H-%M-%S)s to %(section_end>%H-%M-%S)s.%(ext)s"
ARCHIVE_FILENAME = "archive.txt"
# Separate archive so downloading a video doesn't make `audio` skip it (and vice versa).
AUDIO_ARCHIVE_FILENAME = "archive-audio.txt"


@dataclass(frozen=True)
class CommonOptions:
    """Options shared by every download command."""

    output_dir: Path = Path("downloads")
    subtitle_langs: list[str] = field(default_factory=list)
    embed_thumbnail: bool = True
    cookies_from_browser: str | None = None
    use_archive: bool = False
    playlist: bool = False
    rate_limit: str | None = None
    sleep_seconds: float | None = None


@dataclass(frozen=True)
class VideoOptions:
    max_height: int | None = None
    container: Container = "mp4"
    compat: bool = False


@dataclass(frozen=True)
class ClipOptions:
    start: float = 0
    end: float | None = None  # None = until the end of the video
    precise: bool = True


@dataclass(frozen=True)
class AudioOptions:
    codec: AudioCodec = "m4a"
    quality: str | None = None  # None = codec default


def parse_audio_quality(value: str) -> str:
    """Accept a VBR level 0 (best) to 10 (smallest), or a bitrate such as '192k' or '192'."""
    text = value.strip().lower().removesuffix("k")
    try:
        number = float(text)
    except ValueError:
        raise ValueError(f"Invalid quality {value!r}; use 0-10 or a bitrate like 192k") from None
    if not (0 <= number <= 10 or 32 <= number <= 512):
        raise ValueError(f"Invalid quality {value!r}; use 0-10 or a bitrate between 32k and 512k")
    return text


def parse_timestamp(value: str) -> float:
    """Parse '90', '1:30', '01:02:03' or '1:30.5' into seconds."""
    parts = value.strip().split(":")
    if not value.strip() or len(parts) > 3:
        raise ValueError(f"Invalid time {value!r}; use SS, MM:SS or HH:MM:SS")
    try:
        numbers = [float(p) for p in parts]
    except ValueError:
        raise ValueError(f"Invalid time {value!r}; use SS, MM:SS or HH:MM:SS") from None
    if any(n < 0 for n in numbers) or any(n >= 60 for n in numbers[1:]):
        raise ValueError(f"Invalid time {value!r}; minutes and seconds must be 0-59")
    seconds = 0.0
    for n in numbers:
        seconds = seconds * 60 + n
    return seconds


def parse_rate_limit(value: str) -> int:
    """Parse a human rate such as '500K' or '2M' into bytes per second."""
    rate = parse_bytes(value)
    if rate is None or rate <= 0:
        raise ValueError(f"Invalid rate limit {value!r}; use a value like 500K or 2M")
    return rate


def build_format(max_height: int | None) -> str:
    """Best video + best audio (merged by ffmpeg), falling back to the best single file."""
    height = f"[height<={max_height}]" if max_height else ""
    return f"bv*{height}+ba/b{height}"


def build_common_params(common: CommonOptions) -> dict[str, Any]:
    params: dict[str, Any] = {
        "outtmpl": {"default": OUTPUT_TEMPLATE},
        "paths": {"home": str(common.output_dir)},
        # Keep Unicode titles (e.g. Sinhala) but drop characters invalid on any OS.
        "windowsfilenames": True,
        "noplaylist": not common.playlist,
        "retries": 10,
        "fragment_retries": 10,
        # Output is handled by our logger and progress hooks.
        "noprogress": True,
        "postprocessors": [],
    }

    if common.subtitle_langs:
        params["writesubtitles"] = True
        params["subtitleslangs"] = list(common.subtitle_langs)
    if common.embed_thumbnail:
        params["writethumbnail"] = True
    if common.cookies_from_browser:
        params["cookiesfrombrowser"] = (common.cookies_from_browser,)
    if common.use_archive:
        params["download_archive"] = str(common.output_dir / ARCHIVE_FILENAME)
    if common.rate_limit:
        params["ratelimit"] = parse_rate_limit(common.rate_limit)
    if common.sleep_seconds:
        params["sleep_interval"] = common.sleep_seconds

    return params


def build_video_params(common: CommonOptions, video: VideoOptions, *, embed_chapters: bool = True) -> dict[str, Any]:
    params = build_common_params(common)
    params["format"] = build_format(video.max_height)
    params["merge_output_format"] = video.container
    if video.compat:
        # Prefer H.264 video + AAC audio so the file plays everywhere (QuickTime, iOS, TVs)
        # without re-encoding. Resolution may be lower where YouTube has no H.264 stream.
        params["format_sort"] = ["vcodec:h264", "acodec:aac"]

    # Post-processor order mirrors the yt-dlp CLI: container first, then things
    # embedded into the final container.
    postprocessors = [
        # A pre-merged single-file format may not match the requested container.
        {"key": "FFmpegVideoRemuxer", "preferedformat": video.container},
    ]
    if common.subtitle_langs:
        postprocessors.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})
    postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": embed_chapters})
    if common.embed_thumbnail:
        postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

    params["postprocessors"] = postprocessors
    return params


def build_clip_params(common: CommonOptions, video: VideoOptions, clip: ClipOptions) -> dict[str, Any]:
    if clip.end is not None and clip.end <= clip.start:
        raise ValueError("End time must be after start time")

    # The full video's chapter times would be wrong for a clip.
    params = build_video_params(common, video, embed_chapters=False)
    params["outtmpl"] = {"default": CLIP_OUTPUT_TEMPLATE}
    end = clip.end if clip.end is not None else float("inf")
    # yt-dlp hands the range to ffmpeg, which downloads only that section.
    params["download_ranges"] = download_range_func(None, [(clip.start, end)])
    # Without this, cuts snap to the nearest keyframe (can be several seconds off).
    # With it, ffmpeg re-encodes the clip so it starts and ends exactly where asked.
    params["force_keyframes_at_cuts"] = clip.precise
    return params


def build_audio_params(common: CommonOptions, audio: AudioOptions) -> dict[str, Any]:
    params = build_common_params(common)
    params["format"] = AUDIO_FORMATS[audio.codec]
    if common.use_archive:
        params["download_archive"] = str(common.output_dir / AUDIO_ARCHIVE_FILENAME)

    quality = audio.quality
    if quality is None and audio.codec == "mp3":
        quality = DEFAULT_MP3_QUALITY

    extract: dict[str, Any] = {"key": "FFmpegExtractAudio", "preferredcodec": audio.codec}
    if quality is not None:
        # Only used when ffmpeg has to re-encode; a stream that already matches is copied as-is.
        extract["preferredquality"] = parse_audio_quality(quality)

    postprocessors = [
        extract,
        {"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": True},
    ]
    if common.embed_thumbnail:
        postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
    params["postprocessors"] = postprocessors
    return params
