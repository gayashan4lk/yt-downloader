"""Command-line interface: `ytdl <command> ...`."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape

from yt_downloader.downloader import download
from yt_downloader.options import CommonOptions, VideoOptions, build_video_params, parse_rate_limit
from yt_downloader.preflight import INSTALL_HINT, check_tools
from yt_downloader.progress import describe_file

app = typer.Typer(
    help="Download YouTube videos with yt-dlp and FFmpeg.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.callback()
def main() -> None:
    """Download YouTube videos with yt-dlp and FFmpeg."""


def _run_preflight() -> None:
    result = check_tools()
    for tool in result.missing_optional:
        console.print(
            f"[yellow]WARNING:[/] {tool.name} not found (used for {tool.purpose}). YouTube downloads may fail."
        )
    if not result.ok:
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


def _split_langs(value: str | None) -> list[str]:
    return [lang.strip() for lang in value.split(",") if lang.strip()] if value else []


@app.command()
def video(
    urls: Annotated[list[str], typer.Argument(help="One or more YouTube video or playlist URLs.")],
    max_height: Annotated[
        int | None, typer.Option("--max-height", min=144, help="Maximum resolution height, e.g. 1080.")
    ] = None,
    container: Annotated[str, typer.Option("--format", "-f", help="Output container: mp4 or mkv.")] = "mp4",
    compat: Annotated[bool, typer.Option("--compat", help="Prefer H.264/AAC so the file plays on any device.")] = False,
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o", help="Folder to save files in.")] = Path(
        "downloads"
    ),
    subs: Annotated[
        str | None, typer.Option("--subs", help="Comma-separated subtitle languages to embed, e.g. en,si.")
    ] = None,
    embed_thumbnail: Annotated[
        bool, typer.Option("--embed-thumbnail/--no-embed-thumbnail", help="Embed the thumbnail as cover art.")
    ] = True,
    cookies_from_browser: Annotated[
        str | None,
        typer.Option("--cookies-from-browser", help="Use cookies from a browser (chrome, firefox, safari...)."),
    ] = None,
    archive: Annotated[
        bool, typer.Option("--archive", help="Record downloads in archive.txt and skip ones already done.")
    ] = False,
    playlist: Annotated[
        bool, typer.Option("--playlist", help="If a video URL is part of a playlist, download the whole playlist.")
    ] = False,
    rate_limit: Annotated[
        str | None,
        typer.Option("--rate-limit", callback=_validate_rate_limit, help="Max download speed, e.g. 2M or 500K."),
    ] = None,
    sleep: Annotated[float | None, typer.Option("--sleep", min=0, help="Seconds to wait between downloads.")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show yt-dlp's detailed output.")] = False,
) -> None:
    """Download full videos: best video + audio, merged by FFmpeg."""
    if container not in ("mp4", "mkv"):
        raise typer.BadParameter("must be mp4 or mkv", param_hint="--format")

    _run_preflight()

    common = CommonOptions(
        output_dir=output_dir,
        subtitle_langs=_split_langs(subs),
        embed_thumbnail=embed_thumbnail,
        cookies_from_browser=cookies_from_browser,
        use_archive=archive,
        playlist=playlist,
        rate_limit=rate_limit,
        sleep_seconds=sleep,
    )
    params = build_video_params(common, VideoOptions(max_height=max_height, container=container, compat=compat))

    report = download(urls, params, console, verbose=verbose)

    for path in report.files:
        console.print(f"[green]✓ Saved[/] {escape(describe_file(path))}")
    if not report.files and report.ok:
        console.print("[dim]Nothing new to download (already in archive?).[/]")
    if not report.ok:
        console.print(f"[red]✗ {len(report.failed)} of {len(urls)} URL(s) failed.[/]")
        raise typer.Exit(code=1)
