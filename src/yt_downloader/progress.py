"""Bridge yt-dlp's hooks and logger to rich output."""

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

# Friendlier labels for the post-processors we use.
POSTPROCESSOR_LABELS = {
    "Merger": "Merging video and audio",
    "VideoRemuxer": "Remuxing container",
    "EmbedSubtitle": "Embedding subtitles",
    "Metadata": "Embedding metadata",
    "EmbedThumbnail": "Embedding thumbnail",
}


class RichLogger:
    """yt-dlp logger: hide chatter unless verbose, always show warnings and errors."""

    def __init__(self, console: Console, verbose: bool = False) -> None:
        self.console = console
        self.verbose = verbose

    def debug(self, msg: str) -> None:
        if self.verbose:
            self.console.print(msg, style="dim", markup=False, highlight=False)

    def info(self, msg: str) -> None:
        self.debug(msg)

    def warning(self, msg: str) -> None:
        self.console.print(f"WARNING: {msg}", style="yellow", markup=False, highlight=False)

    def error(self, msg: str) -> None:
        self.console.print(msg, style="red", markup=False, highlight=False)


class DownloadProgress:
    """Renders one progress bar per downloaded stream (video and audio are separate)."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self.progress = Progress(
            TextColumn("[bold blue]{task.description}", justify="left"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=False,
        )
        self._tasks: dict[str, TaskID] = {}
        self._last_postprocessor: tuple[str, str | None] | None = None

    def __enter__(self) -> "DownloadProgress":
        self.progress.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.progress.stop()

    def _task_for(self, data: dict[str, Any]) -> TaskID:
        filename = data.get("filename") or data.get("tmpfilename") or "download"
        if filename not in self._tasks:
            info = data.get("info_dict") or {}
            label = info.get("format_note") or info.get("format_id") or ""
            kind = "audio" if info.get("vcodec") == "none" else "video"
            description = f"{kind} {label}".strip()
            self._tasks[filename] = self.progress.add_task(description, total=None)
        return self._tasks[filename]

    def download_hook(self, data: dict[str, Any]) -> None:
        status = data.get("status")
        if status not in ("downloading", "finished"):
            return
        task = self._task_for(data)
        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        done = data.get("downloaded_bytes") or 0
        if status == "finished":
            total = total or done
            done = total
        self.progress.update(task, completed=done, total=total)

    def postprocessor_hook(self, data: dict[str, Any]) -> None:
        if data.get("status") != "started":
            return
        name = data.get("postprocessor", "")
        # yt-dlp registers hooks twice on post-processors passed via params, so skip repeats.
        key = (name, (data.get("info_dict") or {}).get("filepath"))
        if key == self._last_postprocessor:
            return
        self._last_postprocessor = key
        label = POSTPROCESSOR_LABELS.get(name)
        if label:
            self.console.print(f"[cyan]→[/] {label} (ffmpeg)")


def describe_file(path: str) -> str:
    p = Path(path)
    try:
        size_mb = p.stat().st_size / (1024 * 1024)
    except OSError:
        return str(p)
    return f"{p} ({size_mb:.1f} MB)"
