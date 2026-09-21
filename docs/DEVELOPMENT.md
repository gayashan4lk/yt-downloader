# Development Guide

Everything you need to change `ytdl` safely. Read [ARCHITECTURE.md](ARCHITECTURE.md) first for the module layout.

## Setup

```bash
brew install uv ffmpeg deno     # macOS; uv installs Python 3.12 itself
uv sync                         # creates .venv from uv.lock (including dev tools)
uv run ytdl --help
```

Check the environment:

```bash
ffmpeg -version | head -1 && deno --version | head -1 && uv run python -c "import yt_dlp; print(yt_dlp.version.__version__)"
```

## Daily commands

| Task | Command |
|---|---|
| Run the tool | `uv run ytdl <command> ...` |
| Unit tests | `uv run pytest` (no network, under 1 s) |
| Lint | `uv run ruff check src tests` |
| Format | `uv run ruff format src tests` |
| Upgrade yt-dlp | `uv lock --upgrade-package yt-dlp && uv sync` |
| Add a dependency | `uv add <pkg>` (dev only: `uv add --dev <pkg>`) |

## Git workflow

1. Start from an up-to-date `main`: `git checkout main && git pull`
2. Create a branch: `feat/<name>` for features, `fix/<name>` for bugs, `docs/<name>` for docs.
3. Make the change **with tests**. `pytest` and `ruff check` must pass.
4. Run the relevant [manual real-URL checks](#manual-real-url-checks).
5. Update the docs: the README usage section, the PRD requirement status, a [DECISIONS.md](DECISIONS.md) ADR for notable choices, and tick the item in [ROADMAP.md](ROADMAP.md).
6. Open a PR into `main`. The description should cover what changed, why, what a reviewer should know, and the test results.

## Testing strategy

| Layer | How | File |
|---|---|---|
| yt-dlp settings | Call `build_*_params` and assert on the dict (format string, post-processor keys and order, archive path…) | `tests/test_options.py` |
| Parsers | Parametrised valid and invalid inputs (`parse_timestamp`, `parse_audio_quality`, `parse_rate_limit`) | `tests/test_options.py` |
| CLI wiring | `typer.testing.CliRunner`. `stub()` / `stub_info()` replace `download` / `fetch_info` and `check_tools`, so nothing touches the network. Assert on the captured params, the exit code and the output. | `tests/test_cli.py` |
| `info` summaries | Fake `formats` lists shaped like real yt-dlp output | `tests/test_info.py` |
| Tool check | Patch `preflight.shutil.which` | `tests/test_preflight.py` |
| End to end | Manual, against real URLs (below) | none yet (see ROADMAP) |

Rules of thumb:
- **Never hit the network in unit tests.** Stub at the `cli.download` / `cli.fetch_info` boundary.
- Bad input should give **exit code 2 before any download**. Assert that `captured == {}`.
- For download-range callables, call them: `list(params["download_ranges"]({"id": "x"}, None))`.
- Rich output wraps at 80 columns in tests. Pass `env={"COLUMNS": "120"}` to `runner.invoke` when asserting on table text.

## Manual real-URL checks

Run these after changing download logic or upgrading yt-dlp. Save to the scratch folder `/tmp/ytdl-check` so nothing lands in the repo.

**Test video:** `https://www.youtube.com/watch?v=jNQXAC9IVRw` ("Me at the zoo": 19 s, 240p, has chapters, en/de subtitles, AAC and Opus audio). The yt-dlp test video `BaW_jenozKc` is **no longer available**. It's still useful for checking the error hint.
**Playlist-like URL:** `https://www.youtube.com/@jawed/videos` (a channel with one video).

```bash
URL="https://www.youtube.com/watch?v=jNQXAC9IVRw"; OUT=/tmp/ytdl-check
uv run ytdl info  "$URL"                               # summary + tables
uv run ytdl info  "$URL" --json | python3 -c "import json,sys; print(json.load(sys.stdin)['title'])"
uv run ytdl video "$URL" -o $OUT/video                 # ~0.7 MB mp4
uv run ytdl video "$URL" -o $OUT/compat -f mkv --compat
uv run ytdl clip  "$URL" -s 0:05 -e 0:12 -o $OUT/clip  # exactly 7.000 s
uv run ytdl audio "$URL" -o $OUT/audio                 # AAC ~128k, copied as-is
uv run ytdl audio "$URL" -c mp3 -o $OUT/mp3
uv run ytdl info  "https://www.youtube.com/@jawed/videos"
uv run ytdl info  "https://www.youtube.com/watch?v=BaW_jenozKc"   # expect a hint + exit code 1
```

Check the results with `ffprobe` (one file at a time):

```bash
ffprobe -v error -show_entries stream=codec_type,codec_name:format=duration -of compact "$OUT/clip/<file>.mp4"
```

| Check | Expected |
|---|---|
| video | av1 (or vp9) + opus + png cover, ~19 s, title/artist tags |
| compat | h264 + aac |
| clip (precise) | h264 + aac, duration 7.000 |
| audio (m4a) | aac ~128k, cover art |
| mp3 | mp3 + png cover |

## Adding a new command

Using `ytdl thumbnail URL` as an example:

1. **Options** ([`options.py`](../src/yt_downloader/options.py)): add a `ThumbnailOptions` dataclass if the command needs its own settings, and a pure `build_thumbnail_params(common, opts)` that starts from `build_common_params(common)`. Find the right yt-dlp settings in `YoutubeDL.py`'s docstring and in `yt_dlp/__init__.py`, which shows how the CLI builds its post-processor list.
2. **Tests first** (`tests/test_options.py`): assert on the returned dict.
3. **CLI** ([`cli.py`](../src/yt_downloader/cli.py)): add an `@app.command()` function. Reuse the `Annotated` aliases (`OutputDir`, `CookiesFromBrowser`, `Verbose`, …). Validate with option callbacks that raise `typer.BadParameter`. Call `_run_preflight()`, then `download(...)` and `_print_report(...)`, or `fetch_info` for commands that only read metadata.
4. **CLI tests** (`tests/test_cli.py`): use `stub(monkeypatch)` and assert on the captured params and exit codes, including bad input giving exit code 2.
5. **Progress label**: if a new post-processor runs, add its `pp_key()` to `POSTPROCESSOR_LABELS` in [`progress.py`](../src/yt_downloader/progress.py).
6. **Hints**: add any new error strings to `ERROR_HINTS` in [`downloader.py`](../src/yt_downloader/downloader.py).
7. **Docs**: README usage, the PRD requirement table, ROADMAP, and an ADR if needed.
8. **Real-URL check**, then open a PR.

## Code conventions

- Python 3.12 syntax (`X | None`, `list[str]`); ruff rules `E F I UP B SIM`; line length 120.
- **All yt-dlp settings go in `options.py`**, not in `cli.py` or `downloader.py`. The only exception is runtime-only settings (hooks, logger, FFmpeg verbosity) in `downloader.py`.
- Option dataclasses are `frozen=True`.
- User-facing text: say what to do next ("Use --cookies-from-browser…"), not just what went wrong.
- Pass any text from YouTube (titles, paths) through `rich.markup.escape` before printing.
- Comments explain *why* (yt-dlp quirks, trade-offs), not *what*.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Sign in to confirm you're not a bot` | YouTube rate limiting or bot detection | Wait, `--sleep 5`, `--cookies-from-browser chrome`, upgrade yt-dlp |
| Few formats, or warnings about JS or "n" challenges | Deno missing or old; yt-dlp out of date | `brew install deno` / `brew upgrade deno`; upgrade yt-dlp |
| `Requested format is not available` | `--max-height` or `--compat` filters too strict | `ytdl info URL` to see what's available |
| `ffmpeg not found` (exit 2) | FFmpeg not on PATH | `brew install ffmpeg` |
| Output is an .mp4 that QuickTime won't open | AV1/Opus codecs | `--compat` |
| Need to see what yt-dlp is doing | Output hidden by default | `-v` |
| Debugging a yt-dlp setting directly | Compare with the yt-dlp CLI | `uv run yt-dlp --print-traffic -v ...`, or read `.venv/lib/python3.12/site-packages/yt_dlp/YoutubeDL.py` (the options docstring is at the top) |
