# Roadmap and Backlog

What could come next, roughly in priority order, plus known limitations. Each item says **why** it's worth doing and **where** it would go, so it can be picked up without extra context. When you start an item, create a `feat/<name>` branch. When it ships, update the [PRD](PRD.md) status and add an ADR to [DECISIONS.md](DECISIONS.md) if you made a notable choice.

## Done (v0.1.0)

- [x] `ytdl video`: best-quality merge, `--max-height`, `--compat`, mp4/mkv, subtitles, thumbnail, archive, playlists, cookies, rate limit, sleep. PR: initial commit on `main`.
- [x] `ytdl clip`: time ranges, precise/fast. PR #1.
- [x] `ytdl audio`: m4a/opus copied without re-encoding, mp3 re-encoded, separate archive. PR #2.
- [x] `ytdl info`: summary, quality tables, `-F`, `--json`, playlists. PR #3.

## Next up

### P1: Quality and safety

| Item | Why | Where / notes |
|---|---|---|
| **CI with GitHub Actions** | Run `pytest` and `ruff` on every PR automatically | `.github/workflows/ci.yml`: `astral-sh/setup-uv`, `uv sync`, `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`. No network needed. |
| **Opt-in integration tests** | Real-URL checks are manual right now | Add a pytest marker, e.g. `@pytest.mark.network`, skipped unless `YTDL_NETWORK_TESTS=1`. Use the test video `jNQXAC9IVRw` (19 s). Check duration and codecs with `ffprobe`. |
| **Limit filename length** | Long Sinhala or CJK titles can exceed the 255-byte limit and fail on write | Set `trim_file_name` (e.g. 150) in `build_common_params`, and test it with a long Unicode title |
| **`ytdl --version`** | Bug reports need the ytdl, yt-dlp and ffmpeg versions | Typer callback option in `cli.py`; print `yt_dlp.version.__version__` and the output of `ffmpeg -version` |

### P2: Features

| Item | Why | Where / notes |
|---|---|---|
| **Config file for defaults** | e.g. always `--compat`, always `-o ~/Movies/YouTube` | `~/.config/ytdl/config.toml` read with `tomllib`. Merge before CLI flags (CLI flags win). Keep it out of `options.py` so the builders stay pure. |
| **Several clip ranges** (`--range 1:00-1:30 --range 5:00-5:20`) | Several cuts in one command | `download_range_func` already accepts a list. `ClipOptions.ranges: list[tuple]`. The filename template already includes the section. |
| **Audio-only clips** | Cut a podcast segment | Either `ytdl clip --audio` or `ytdl audio --start/--end`: combine `download_ranges` with the ExtractAudio settings |
| **Auto-generated captions** (`--auto-subs`) | Many videos only have auto captions; `--subs` only finds manual ones | Set `writeautomaticsub=True` in `build_common_params`. Maybe `--subs-format srt` via `FFmpegSubtitlesConvertor`. |
| **Download by chapter** (`clip --chapter "Intro"`) | Chapters are common on long videos | `download_range_func(chapters=[regex], ranges=None)` |
| **SponsorBlock** (`--sponsorblock remove`) | Skip sponsor segments | yt-dlp `SponsorBlock` + `ModifyChapters` post-processors. They must run before `FFmpegMetadata` (see the order in `yt_dlp/__init__.py`). |
| **Lossless audio targets** (`-c flac/wav`) | For editing tools that want PCM. Deliberately left out so far (ADR-10). | Add to `AUDIO_CODECS` and `AUDIO_FORMATS`. Say clearly in the help text that it doesn't improve quality. |
| **Parallel downloads** (`-j 3`) | Big playlists | A separate `YoutubeDL` per worker; Rich `Progress` is thread-safe. Watch out for YouTube rate limits. |
| **Custom output template** (`--name "%(upload_date)s %(title)s"`) | Power users | Pass through to `outtmpl.default`; validate with `YoutubeDL.validate_outtmpl` |
| **Browser profile for cookies** (`chrome:Profile 1`) | Several browser profiles | Parse `browser[:profile]` into the `cookiesfrombrowser` tuple |

### P3: Nice to have

- Shell completion (currently `add_completion=False` in `cli.py`).
- `ytdl update`: runs `uv lock --upgrade-package yt-dlp && uv sync` and prints the version change.
- `info` for several URLs.
- Package for `uv tool install .` so `ytdl` works without `uv run`, and document it.
- Windows testing: paths, FFmpeg discovery, console encoding.

## Known limitations

| Limitation | Impact | Workaround / planned fix |
|---|---|---|
| The default MP4 is often **AV1 + Opus** | May not play in QuickTime, iOS or older TVs | Use `--compat`. Open question in PRD §10. |
| `--subs` only finds **manual** subtitles | No subtitles on videos that only have auto captions | Planned `--auto-subs` |
| A pure `playlist?list=` URL always downloads the **whole playlist** | `--playlist` only matters for watch URLs with `&list=` | By design (yt-dlp `noplaylist`) |
| The output folder is relative to **where you run the command** | Files end up in different places | Use `-o`, or the planned config file |
| **No filename length limit** | Very long Unicode titles may fail to save | Planned `trim_file_name` |
| Progress bars for FFmpeg-downloaded sections and HLS may show no speed or total | Cosmetic | yt-dlp reports little progress for these |
| **"Nothing new to download (already in archive?)"** appears whenever nothing was saved, even without `--archive` | Can be misleading | Base the message on whether an archive is in use |
| **No real-network tests in CI** | A YouTube breakage is only noticed when someone uses the tool | Planned opt-in integration tests |
| Only **Deno** is supported as the JS runtime | Node or Bun users need Deno too | Could expose `js_runtimes` |

## Maintenance tasks (recurring)

- **Every 1–2 weeks, or when downloads start failing:** `uv lock --upgrade-package yt-dlp && uv sync`, then run the [manual real-URL checks](DEVELOPMENT.md#manual-real-url-checks).
- **After a yt-dlp upgrade:** check that the post-processor keys, `download_range_func` and hook payloads haven't changed (see the quirks table in [ARCHITECTURE.md](ARCHITECTURE.md#yt-dlp-quirks-this-code-works-around)).
