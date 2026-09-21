"""Run yt-dlp with our params and report results."""

from dataclasses import dataclass, field
from typing import Any

from rich.console import Console
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from yt_downloader.progress import DownloadProgress, RichLogger

# Substrings of yt-dlp error messages mapped to actionable hints.
ERROR_HINTS = (
    (
        "Sign in to confirm you",
        "YouTube suspects a bot. Retry later, add --sleep, or use --cookies-from-browser chrome.",
    ),
    ("confirm your age", "Age-restricted video. Use --cookies-from-browser with a signed-in browser."),
    ("Private video", "This video is private."),
    ("members-only", "Members-only video. Use --cookies-from-browser with an account that has access."),
    (
        "Requested format is not available",
        "No stream matches your filters. Try a different --max-height or drop --compat.",
    ),
    ("unavailable", "The video is unavailable (removed, blocked in your region, or wrong URL)."),
    ("playlist does not exist", "The playlist doesn't exist or is private. Check the list= part of the URL."),
    ("JavaScript runtime", "Install Deno so yt-dlp can solve YouTube's challenges: brew install deno"),
)


def hint_for(message: str) -> str | None:
    for needle, hint in ERROR_HINTS:
        if needle.lower() in message.lower():
            return hint
    return None


@dataclass
class DownloadReport:
    files: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed


def download(urls: list[str], params: dict[str, Any], console: Console, verbose: bool = False) -> DownloadReport:
    """Download each URL separately so one failure doesn't stop the rest."""
    report = DownloadReport()

    with DownloadProgress(console) as progress:
        ydl_params = {
            **params,
            "logger": RichLogger(console, verbose=verbose),
            "progress_hooks": [progress.download_hook],
            "postprocessor_hooks": [progress.postprocessor_hook],
            # Called with the final path after all post-processing.
            "post_hooks": [report.files.append],
        }
        if not verbose:
            # When ffmpeg itself downloads (e.g. clip sections), keep its stats off the
            # terminal but still show real errors. Placed before the first input.
            ydl_params["external_downloader_args"] = {"ffmpeg_i1": ["-loglevel", "error", "-nostats"]}
        with YoutubeDL(ydl_params) as ydl:
            for url in urls:
                try:
                    ydl.download([url])
                except DownloadError as err:
                    # yt-dlp already printed the error through our logger.
                    report.failed.append(url)
                    if hint := hint_for(str(err)):
                        console.print(f"[yellow]Hint:[/] {hint}")

    return report


def fetch_info(url: str, params: dict[str, Any], console: Console, verbose: bool = False) -> dict[str, Any] | None:
    """Extract metadata without downloading. Returns None (after printing the error) on failure."""
    with YoutubeDL({**params, "logger": RichLogger(console, verbose=verbose)}) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except DownloadError as err:
            if hint := hint_for(str(err)):
                console.print(f"[yellow]Hint:[/] {hint}")
            return None
        return ydl.sanitize_info(info)
