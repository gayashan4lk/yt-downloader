# CLAUDE.md

Guidance for AI coding assistants (and people) working on this repo.

## Project

`ytdl`: a Python CLI that downloads YouTube video, audio and clips using **yt-dlp** (extraction) and **FFmpeg** (merge, cut, convert), with **Deno** solving YouTube's JS challenges. Commands: `video`, `clip`, `audio`, `info`.

Docs: [PRD](docs/PRD.md) · [Architecture](docs/ARCHITECTURE.md) · [Decisions](docs/DECISIONS.md) · [Roadmap](docs/ROADMAP.md) · [Development guide](docs/DEVELOPMENT.md)

## Commands

```bash
uv sync                                   # install
uv run ytdl <command> --help              # run
uv run pytest                             # tests (no network)
uv run ruff check src tests && uv run ruff format src tests
uv lock --upgrade-package yt-dlp && uv sync   # upgrade yt-dlp
```

Always use `uv run`. The system Python is 3.9 and too old for yt-dlp.

## Layout

- `src/yt_downloader/cli.py`: Typer commands only (parse, validate, call, print). Shared options are `Annotated` aliases.
- `src/yt_downloader/options.py`: **all yt-dlp settings**, as pure `build_*_params()` functions and dataclasses.
- `src/yt_downloader/downloader.py`: runs `YoutubeDL`; `ERROR_HINTS`; runtime-only settings (hooks, logger, FFmpeg log level).
- `src/yt_downloader/progress.py`: Rich logger, progress bars, `POSTPROCESSOR_LABELS`.
- `src/yt_downloader/info.py`: `info` summaries (pure row functions + Rich renderers).
- `src/yt_downloader/preflight.py`: checks for ffmpeg, ffprobe and deno.

## Rules

- Put new yt-dlp settings in `options.py` and test them in `tests/test_options.py`. Don't build settings in `cli.py`.
- Unit tests must not use the network. Stub `cli.download`, `cli.fetch_info` and `cli.check_tools` (see `stub()` in `tests/test_cli.py`).
- Invalid input → `typer.BadParameter` → exit code 2, **before** any download. Download failure → exit code 1.
- Escape YouTube-supplied text with `rich.markup.escape` before printing.
- Follow yt-dlp's CLI post-processor order (`yt_dlp/__init__.py`): container changes, then subtitles, then metadata, then thumbnail.
- Keep the known workarounds (see "yt-dlp quirks" in docs/ARCHITECTURE.md): the post-processor hook de-duplication, and `-loglevel error -nostats` for FFmpeg.
- Branches: `feat/*`, `fix/*`, `docs/*` off `main`; PR into `main`. Don't commit or push unless asked.
- After a feature, update the README usage, PRD status, ROADMAP, and DECISIONS (for notable choices).

## Verifying real downloads

Test video: `https://www.youtube.com/watch?v=jNQXAC9IVRw` (19 s). Save to a temp folder with `-o`, not to the repo. Check the files with `ffprobe` (one file per call). Full checklist: docs/DEVELOPMENT.md → "Manual real-URL checks".

## Scope

Only for content the user has the right to download (their own, Creative Commons, public domain, or with permission). Don't add features that get around DRM, paywalls or members-only access.
