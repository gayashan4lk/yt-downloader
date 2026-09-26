"""Command-line interface: `ytdl <command> ...`."""

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape

from yt_downloader.cookies import inspect_cookie_file
from yt_downloader.downloader import DownloadReport, download, fetch_info
from yt_downloader.info import render_formats, render_playlist, render_video
from yt_downloader.options import (
    AUDIO_CODECS,
    AudioOptions,
    ClipOptions,
    CommonOptions,
    VideoOptions,
    build_audio_params,
    build_clip_params,
    build_info_params,
    build_video_params,
    parse_audio_quality,
    parse_rate_limit,
    parse_timestamp,
)
from yt_downloader.preflight import INSTALL_HINT, check_tools
from yt_downloader.progress import describe_file

app = typer.Typer(
    help="Download YouTube videos with yt-dlp and FFmpeg.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
# Logs and errors for `info --json`, so stdout stays pure JSON.
err_console = Console(stderr=True)


@app.callback()
def main() -> None:
    """Download YouTube videos with yt-dlp and FFmpeg."""


def _run_preflight(require_ffmpeg: bool = True, out: Console = console) -> None:
    result = check_tools()
    for tool in result.missing_optional:
        out.print(f"[yellow]WARNING:[/] {tool.name} not found (used for {tool.purpose}). YouTube downloads may fail.")
    if require_ffmpeg and not result.ok:
        names = ", ".join(t.name for t in result.missing_required)
        console.print(f"[red]ERROR:[/] Missing required tools: {names}. {INSTALL_HINT}")
        raise typer.Exit(code=2)


def _validate_rate_limit(value: str | None) -> str | None:
    if value is not None:
        try:
            parse_rate_limit(value)
        except ValueError as err:
            raise typer.BadParameter(str(err)) from err
    return value


def _validate_cookies(value: Path | None) -> Path | None:
    """Reject an unusable cookie file before anything is downloaded."""
    if value is None:
        return None
    try:
        report = inspect_cookie_file(value)
    except ValueError as err:
        raise typer.BadParameter(str(err)) from err
    if not report.has_youtube:
        raise typer.BadParameter(
            f"no youtube.com or google.com cookies in {value}. Export them while signed in to YouTube."
        )
    return value


def _check_one_cookie_source(cookies: Path | None, cookies_from_browser: str | None) -> None:
    if cookies and cookies_from_browser:
        raise typer.BadParameter("use either --cookies or --cookies-from-browser, not both", param_hint="--cookies")


def _validate_timestamp(value: str | None) -> str | None:
    if value is not None:
        try:
            parse_timestamp(value)
        except ValueError as err:
            raise typer.BadParameter(str(err)) from err
    return value


def _validate_codec(value: str) -> str:
    if value not in AUDIO_CODECS:
        raise typer.BadParameter(f"must be one of: {', '.join(AUDIO_CODECS)}")
    return value


def _validate_quality(value: str | None) -> str | None:
    if value is not None:
        try:
            parse_audio_quality(value)
        except ValueError as err:
            raise typer.BadParameter(str(err)) from err
    return value


def _validate_container(value: str) -> str:
    if value not in ("mp4", "mkv"):
        raise typer.BadParameter("must be mp4 or mkv")
    return value


def _split_langs(value: str | None) -> list[str]:
    return [lang.strip() for lang in value.split(",") if lang.strip()] if value else []


def _print_report(report: DownloadReport, url_count: int) -> None:
    for path in report.files:
        console.print(f"[green]✓ Saved[/] {escape(describe_file(path))}")
    if not report.files and report.ok:
        console.print("[dim]Nothing new to download (already in archive?).[/]")
    if not report.ok:
        console.print(f"[red]✗ {len(report.failed)} of {url_count} URL(s) failed.[/]")
        raise typer.Exit(code=1)


# Options shared by several commands.
MaxHeight = Annotated[int | None, typer.Option("--max-height", min=144, help="Maximum resolution height, e.g. 1080.")]
ContainerOpt = Annotated[
    str, typer.Option("--format", "-f", callback=_validate_container, help="Output container: mp4 or mkv.")
]
Compat = Annotated[bool, typer.Option("--compat", help="Prefer H.264/AAC so the file plays on any device.")]
OutputDir = Annotated[Path, typer.Option("--output-dir", "-o", help="Folder to save files in.")]
EmbedThumbnail = Annotated[
    bool, typer.Option("--embed-thumbnail/--no-embed-thumbnail", help="Embed the thumbnail as cover art.")
]
CookiesFromBrowser = Annotated[
    str | None,
    typer.Option("--cookies-from-browser", help="Use cookies from a browser (chrome, firefox, safari...)."),
]
Cookies = Annotated[
    Path | None,
    typer.Option(
        "--cookies",
        exists=True,
        dir_okay=False,
        readable=True,
        callback=_validate_cookies,
        help="Netscape-format cookies.txt file. See README: Cookies.",
    ),
]
RateLimit = Annotated[
    str | None,
    typer.Option("--rate-limit", callback=_validate_rate_limit, help="Max download speed, e.g. 2M or 500K."),
]
Verbose = Annotated[bool, typer.Option("--verbose", "-v", help="Show yt-dlp's detailed output.")]
Archive = Annotated[bool, typer.Option("--archive", help="Keep an archive file and skip videos already downloaded.")]
Playlist = Annotated[
    bool, typer.Option("--playlist", help="If a video URL is part of a playlist, download the whole playlist.")
]
Sleep = Annotated[float | None, typer.Option("--sleep", min=0, help="Seconds to wait between downloads.")]


@app.command()
def video(
    urls: Annotated[list[str], typer.Argument(help="One or more YouTube video or playlist URLs.")],
    max_height: MaxHeight = None,
    container: ContainerOpt = "mp4",
    compat: Compat = False,
    output_dir: OutputDir = Path("downloads"),
    subs: Annotated[
        str | None, typer.Option("--subs", help="Comma-separated subtitle languages to embed, e.g. en,si.")
    ] = None,
    embed_thumbnail: EmbedThumbnail = True,
    cookies_from_browser: CookiesFromBrowser = None,
    cookies: Cookies = None,
    archive: Archive = False,
    playlist: Playlist = False,
    rate_limit: RateLimit = None,
    sleep: Sleep = None,
    verbose: Verbose = False,
) -> None:
    """Download full videos: best video + audio, merged by FFmpeg."""
    _check_one_cookie_source(cookies, cookies_from_browser)
    _run_preflight()

    common = CommonOptions(
        output_dir=output_dir,
        subtitle_langs=_split_langs(subs),
        embed_thumbnail=embed_thumbnail,
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies,
        use_archive=archive,
        playlist=playlist,
        rate_limit=rate_limit,
        sleep_seconds=sleep,
    )
    params = build_video_params(common, VideoOptions(max_height=max_height, container=container, compat=compat))

    report = download(urls, params, console, verbose=verbose)
    _print_report(report, len(urls))


@app.command()
def clip(
    url: Annotated[str, typer.Argument(help="A YouTube video URL.")],
    start: Annotated[
        str | None,
        typer.Option("--start", "-s", callback=_validate_timestamp, help="Clip start, e.g. 90, 1:30 or 1:02:03."),
    ] = None,
    end: Annotated[
        str | None,
        typer.Option("--end", "-e", callback=_validate_timestamp, help="Clip end. Omit to go to the end of the video."),
    ] = None,
    precise: Annotated[
        bool,
        typer.Option(
            "--precise/--fast",
            help="--precise re-encodes for frame-exact cuts; --fast skips re-encoding but may be off by a few seconds.",
        ),
    ] = True,
    max_height: MaxHeight = None,
    container: ContainerOpt = "mp4",
    compat: Compat = False,
    output_dir: OutputDir = Path("downloads"),
    embed_thumbnail: EmbedThumbnail = True,
    cookies_from_browser: CookiesFromBrowser = None,
    cookies: Cookies = None,
    rate_limit: RateLimit = None,
    verbose: Verbose = False,
) -> None:
    """Download part of a video: only the chosen time range is fetched and cut by FFmpeg."""
    _check_one_cookie_source(cookies, cookies_from_browser)
    if start is None and end is None:
        raise typer.BadParameter("give --start, --end or both", param_hint="--start/--end")
    clip_options = ClipOptions(
        start=parse_timestamp(start) if start else 0,
        end=parse_timestamp(end) if end else None,
        precise=precise,
    )
    if clip_options.end is not None and clip_options.end <= clip_options.start:
        raise typer.BadParameter("must be after --start", param_hint="--end")

    _run_preflight()

    common = CommonOptions(
        output_dir=output_dir,
        embed_thumbnail=embed_thumbnail,
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies,
        rate_limit=rate_limit,
    )
    video_options = VideoOptions(max_height=max_height, container=container, compat=compat)
    params = build_clip_params(common, video_options, clip_options)

    report = download([url], params, console, verbose=verbose)
    _print_report(report, 1)


@app.command()
def audio(
    urls: Annotated[list[str], typer.Argument(help="One or more YouTube video or playlist URLs.")],
    codec: Annotated[
        str,
        typer.Option(
            "--codec",
            "-c",
            callback=_validate_codec,
            help="m4a (AAC, plays everywhere), mp3 (re-encoded), opus (smallest), or best (keep the original).",
        ),
    ] = "m4a",
    quality: Annotated[
        str | None,
        typer.Option(
            "--quality",
            "-q",
            callback=_validate_quality,
            help="Only used when re-encoding: 0 (best) to 10 (smallest), or a bitrate like 192k. mp3 default: 2.",
        ),
    ] = None,
    output_dir: OutputDir = Path("downloads"),
    embed_thumbnail: EmbedThumbnail = True,
    cookies_from_browser: CookiesFromBrowser = None,
    cookies: Cookies = None,
    archive: Archive = False,
    playlist: Playlist = False,
    rate_limit: RateLimit = None,
    sleep: Sleep = None,
    verbose: Verbose = False,
) -> None:
    """Download audio only: m4a and opus are copied without re-encoding, mp3 is converted by FFmpeg."""
    _check_one_cookie_source(cookies, cookies_from_browser)
    _run_preflight()

    common = CommonOptions(
        output_dir=output_dir,
        embed_thumbnail=embed_thumbnail,
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies,
        use_archive=archive,
        playlist=playlist,
        rate_limit=rate_limit,
        sleep_seconds=sleep,
    )
    params = build_audio_params(common, AudioOptions(codec=codec, quality=quality))

    report = download(urls, params, console, verbose=verbose)
    _print_report(report, len(urls))


@app.command()
def info(
    url: Annotated[str, typer.Argument(help="A YouTube video or playlist URL.")],
    formats: Annotated[
        bool, typer.Option("--formats", "-F", help="Also list every format yt-dlp found (like yt-dlp -F).")
    ] = False,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the full metadata as JSON (for scripts, e.g. piping to jq).")
    ] = False,
    playlist: Playlist = False,
    cookies_from_browser: CookiesFromBrowser = None,
    cookies: Cookies = None,
    verbose: Verbose = False,
) -> None:
    """Show a video's details and available qualities without downloading anything."""
    _check_one_cookie_source(cookies, cookies_from_browser)
    out = err_console if as_json else console
    # Nothing is downloaded or converted, so ffmpeg isn't needed here.
    _run_preflight(require_ffmpeg=False, out=out)

    common = CommonOptions(
        embed_thumbnail=False,
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies,
        playlist=playlist,
    )
    data = fetch_info(url, build_info_params(common), out, verbose=verbose)
    if data is None:
        raise typer.Exit(code=1)

    if as_json:
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
    elif data.get("_type") == "playlist":
        console.print(render_playlist(data))
    else:
        console.print(render_video(data))
        if formats:
            console.print(render_formats(data))


cookies_app = typer.Typer(help="Work with cookie files.", no_args_is_help=True)
app.add_typer(cookies_app, name="cookies")

# Warn this many days before a cookie expires, so there's time to export a fresh file.
EXPIRY_WARN_DAYS = 14


@cookies_app.command("check")
def cookies_check(
    path: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, readable=True, help="A Netscape-format cookies.txt file."),
    ],
) -> None:
    """Check whether a cookie file still holds a usable YouTube session."""
    try:
        report = inspect_cookie_file(path)
    except ValueError as err:
        console.print(f"[red]✗[/] {escape(str(err))}")
        raise typer.Exit(code=2) from err

    console.print(f"[green]✓[/] Netscape format, {report.total} entries")

    youtube = report.youtube_domains
    if youtube:
        counts = "  ".join(f"{escape(domain.lstrip('.'))} ({count})" for domain, count in sorted(youtube.items()))
        console.print(f"[green]✓[/] {counts}")
    else:
        console.print("[red]✗[/] No youtube.com or google.com cookies. Export them while signed in to YouTube.")

    if report.auth_present:
        console.print(f"[green]✓[/] Auth cookies present: {', '.join(report.auth_present)}")
    else:
        console.print("[red]✗[/] No signed-in session cookies. This file won't get past the bot check.")

    expired = _print_expiry(report.soonest_expiry)

    if not youtube or not report.auth_present or expired:
        raise typer.Exit(code=1)


def _print_expiry(soonest: int | None) -> bool:
    """Print the soonest expiry. Returns True if it has already passed."""
    if soonest is None:
        console.print("[dim]All cookies are session cookies (no expiry).[/]")
        return False

    when = datetime.fromtimestamp(soonest)
    days = (when - datetime.now()).days
    stamp = when.strftime("%Y-%m-%d")
    if days < 0:
        console.print(f"[red]✗[/] Soonest expiry: {stamp} (expired). Export a fresh file.")
        return True
    if days <= EXPIRY_WARN_DAYS:
        console.print(f"[yellow]⚠[/] Soonest expiry: {stamp} ({days} days)")
    else:
        console.print(f"[green]✓[/] Soonest expiry: {stamp} ({days} days)")
    return False
