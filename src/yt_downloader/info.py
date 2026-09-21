"""Summarise a yt-dlp info dict for `ytdl info`.

The row-building functions are pure so they can be tested with fake info dicts;
the render functions turn them into rich tables.
"""

from dataclasses import dataclass
from typing import Any

from rich.console import Group, RenderableType
from rich.markup import escape
from rich.table import Table
from yt_dlp.utils import format_bytes

VIDEO_CODECS = (
    ("av01", "AV1"),
    ("vp09", "VP9"),
    ("vp9", "VP9"),
    ("avc1", "H.264"),
    ("hev1", "H.265"),
    ("hvc1", "H.265"),
)
AUDIO_CODECS = (
    ("mp4a", "AAC"),
    ("opus", "Opus"),
    ("vorbis", "Vorbis"),
    ("mp3", "MP3"),
    ("ac-3", "AC-3"),
    ("ec-3", "E-AC-3"),
)


def codec_family(codec: str | None) -> str | None:
    """'avc1.4d400c' -> 'H.264', 'mp4a.40.2' -> 'AAC'. None for 'none' or unknown-empty."""
    if not codec or codec == "none":
        return None
    lowered = codec.lower()
    for prefix, name in VIDEO_CODECS + AUDIO_CODECS:
        if lowered.startswith(prefix):
            return name
    return codec


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def format_date(yyyymmdd: str | None) -> str:
    if not yyyymmdd or len(yyyymmdd) != 8:
        return "unknown"
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"


def _size(fmt: dict[str, Any]) -> int | None:
    return fmt.get("filesize") or fmt.get("filesize_approx")


def _is_video(fmt: dict[str, Any]) -> bool:
    return codec_family(fmt.get("vcodec")) is not None and bool(fmt.get("height"))


def _is_audio_only(fmt: dict[str, Any]) -> bool:
    return fmt.get("vcodec") == "none" and codec_family(fmt.get("acodec")) is not None


def _is_drc(fmt: dict[str, Any]) -> bool:
    # YouTube's "DRC" variants are volume-normalised copies of the same audio.
    return str(fmt.get("format_id", "")).endswith("-drc")


@dataclass(frozen=True)
class ResolutionRow:
    height: int
    codecs: list[str]
    fps: float | None
    max_size: int | None


@dataclass(frozen=True)
class AudioRow:
    codec: str
    bitrate: float | None
    size: int | None
    language: str | None


def resolution_rows(formats: list[dict[str, Any]]) -> list[ResolutionRow]:
    """One row per resolution, highest first, listing which codecs YouTube offers at it."""
    by_height: dict[int, list[dict[str, Any]]] = {}
    for fmt in formats:
        if _is_video(fmt):
            by_height.setdefault(fmt["height"], []).append(fmt)

    order = ["AV1", "VP9", "H.265", "H.264"]
    rows = []
    for height in sorted(by_height, reverse=True):
        group = by_height[height]
        codecs = {codec_family(f["vcodec"]) for f in group}
        sizes = [s for f in group if (s := _size(f))]
        fps_values = [f["fps"] for f in group if f.get("fps")]
        rows.append(
            ResolutionRow(
                height=height,
                codecs=sorted(codecs, key=lambda c: order.index(c) if c in order else len(order)),
                fps=max(fps_values) if fps_values else None,
                max_size=max(sizes) if sizes else None,
            )
        )
    return rows


def audio_rows(formats: list[dict[str, Any]]) -> list[AudioRow]:
    """Best bitrate per audio codec (and language), ignoring DRC duplicates."""
    best: dict[tuple[str, str | None], dict[str, Any]] = {}
    for fmt in formats:
        if not _is_audio_only(fmt) or _is_drc(fmt):
            continue
        key = (codec_family(fmt["acodec"]), fmt.get("language"))
        current = best.get(key)
        if current is None or (fmt.get("abr") or 0) > (current.get("abr") or 0):
            best[key] = fmt
    rows = [
        AudioRow(codec=codec, bitrate=fmt.get("abr"), size=_size(fmt), language=language)
        for (codec, language), fmt in best.items()
    ]
    return sorted(rows, key=lambda r: r.bitrate or 0, reverse=True)


def default_choice(info: dict[str, Any]) -> str:
    """What `ytdl video` would download with no options (same selector as yt-dlp's default)."""
    video = codec_family(info.get("vcodec"))
    audio = codec_family(info.get("acodec"))
    parts = [info.get("resolution") or "?"]
    if video:
        parts.append(video)
    if audio:
        parts.append(f"+ {audio}")
    size = _size(info)
    if size:
        parts.append(f"(~{format_bytes(size)})")
    return " ".join(parts)


# --- rendering ---


def _count(value: int | None) -> str:
    return f"{value:,}" if value is not None else "unknown"


def render_video(info: dict[str, Any]) -> RenderableType:
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Title", escape(info.get("title") or "unknown"))
    summary.add_row("Channel", escape(info.get("channel") or info.get("uploader") or "unknown"))
    summary.add_row("Uploaded", format_date(info.get("upload_date")))
    summary.add_row("Duration", format_duration(info.get("duration")))
    summary.add_row("Views", _count(info.get("view_count")))
    summary.add_row("URL", escape(info.get("webpage_url") or ""))
    chapters = info.get("chapters") or []
    if chapters:
        summary.add_row("Chapters", str(len(chapters)))
    subs = sorted((info.get("subtitles") or {}).keys())
    summary.add_row("Subtitles", escape(", ".join(subs)) if subs else "none")
    auto_count = len(info.get("automatic_captions") or {})
    if auto_count:
        summary.add_row("Auto captions", f"{auto_count} languages")
    summary.add_row("ytdl video gets", escape(default_choice(info)))

    video_table = Table(title="Video", title_justify="left", title_style="bold")
    video_table.add_column("Resolution", justify="right")
    video_table.add_column("Codecs")
    video_table.add_column("FPS", justify="right")
    video_table.add_column("Size (largest)", justify="right")
    for row in resolution_rows(info.get("formats") or []):
        video_table.add_row(
            f"{row.height}p",
            ", ".join(row.codecs),
            f"{row.fps:g}" if row.fps else "",
            f"~{format_bytes(row.max_size)}" if row.max_size else "",
        )

    audio_table = Table(title="Audio", title_justify="left", title_style="bold")
    audio_table.add_column("Codec")
    audio_table.add_column("Bitrate", justify="right")
    audio_table.add_column("Size", justify="right")
    audio_table.add_column("Language")
    for row in audio_rows(info.get("formats") or []):
        audio_table.add_row(
            row.codec,
            f"{row.bitrate:.0f}k" if row.bitrate else "",
            f"~{format_bytes(row.size)}" if row.size else "",
            row.language or "",
        )

    return Group(summary, "", video_table, audio_table)


def render_formats(info: dict[str, Any]) -> RenderableType:
    """Every format yt-dlp found, like `yt-dlp -F`, minus storyboard images."""
    table = Table(title="All formats", title_justify="left", title_style="bold")
    for name, justify in [
        ("ID", "left"),
        ("Ext", "left"),
        ("Resolution", "right"),
        ("FPS", "right"),
        ("Video", "left"),
        ("Audio", "left"),
        ("Bitrate", "right"),
        ("Size", "right"),
        ("Protocol", "left"),
        ("Note", "left"),
    ]:
        table.add_column(name, justify=justify)
    for fmt in info.get("formats") or []:
        if fmt.get("ext") == "mhtml":
            continue
        size = _size(fmt)
        table.add_row(
            escape(str(fmt.get("format_id", ""))),
            fmt.get("ext") or "",
            f"{fmt['height']}p" if fmt.get("height") else "audio",
            f"{fmt['fps']:g}" if fmt.get("fps") else "",
            codec_family(fmt.get("vcodec")) or "",
            codec_family(fmt.get("acodec")) or "",
            f"{fmt['tbr']:.0f}k" if fmt.get("tbr") else "",
            f"~{format_bytes(size)}" if size else "",
            fmt.get("protocol") or "",
            escape(fmt.get("format_note") or ""),
        )
    return table


def render_playlist(info: dict[str, Any]) -> RenderableType:
    entries = [e for e in info.get("entries") or [] if e]
    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Playlist", escape(info.get("title") or "unknown"))
    summary.add_row("Channel", escape(info.get("channel") or info.get("uploader") or "unknown"))
    summary.add_row("Videos", str(info.get("playlist_count") or len(entries)))
    total = sum(e.get("duration") or 0 for e in entries)
    if total:
        summary.add_row("Total length", format_duration(total))

    table = Table()
    table.add_column("#", justify="right")
    table.add_column("Title")
    table.add_column("Duration", justify="right")
    table.add_column("ID")
    for index, entry in enumerate(entries, start=1):
        table.add_row(
            str(index),
            escape(entry.get("title") or ""),
            format_duration(entry.get("duration")) if entry.get("duration") else "",
            escape(entry.get("id") or ""),
        )
    return Group(summary, "", table)
