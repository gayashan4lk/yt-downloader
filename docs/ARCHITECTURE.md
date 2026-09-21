# Architecture

How `ytdl` is put together, and where to make changes. For *why* things are this way, see [DECISIONS.md](DECISIONS.md).

## Overview

```
                ┌──────────────────────────────────────────────────────────┐
  user ──args──▶│ cli.py     Typer commands: parse + validate, no logic     │
                └───────┬──────────────────────────────┬───────────────────┘
                        │ dataclasses                  │
                        ▼                              ▼
                ┌──────────────────┐          ┌──────────────────┐
                │ options.py       │          │ preflight.py     │
                │ CLI choices →    │          │ ffmpeg/ffprobe/  │
                │ yt-dlp params    │          │ deno on PATH?    │
                │ (pure)           │          └──────────────────┘
                └───────┬──────────┘
                        │ params dict
                        ▼
                ┌──────────────────┐   hooks/logger   ┌──────────────────┐
                │ downloader.py    │◀────────────────▶│ progress.py      │
                │ YoutubeDL runs,  │                  │ rich bars, step  │
                │ errors → hints   │                  │ lines, logger    │
                └───────┬──────────┘                  └──────────────────┘
                        │ info dict (info command)
                        ▼
                ┌──────────────────┐
                │ info.py          │  pure rows → rich tables
                └──────────────────┘
                        │
                        ▼
           yt-dlp  ──▶  Deno (JS challenges)  ──▶  FFmpeg (merge / cut / convert / embed)
```

## Modules

| Module | Responsibility | Pure? | Tests |
|---|---|---|---|
| [`cli.py`](../src/yt_downloader/cli.py) | Typer app `ytdl` and its commands. Parses and validates input, builds option dataclasses, calls the builders and `download`/`fetch_info`, prints the result, sets the exit code. Shared options are `Annotated` type aliases (`MaxHeight`, `OutputDir`, `Archive`, …). | No | `test_cli.py` (network stubbed) |
| [`options.py`](../src/yt_downloader/options.py) | Dataclasses (`CommonOptions`, `VideoOptions`, `ClipOptions`, `AudioOptions`), parsers (`parse_timestamp`, `parse_rate_limit`, `parse_audio_quality`), and `build_*_params` functions that return yt-dlp parameter dicts. **All yt-dlp settings live here.** | Yes | `test_options.py` |
| [`downloader.py`](../src/yt_downloader/downloader.py) | `download(urls, params, …)` runs `YoutubeDL` one URL at a time and collects a `DownloadReport` (saved files, failed URLs). `fetch_info` runs metadata-only extraction. `ERROR_HINTS` maps error text to advice. | No | via `test_cli.py` (hints) |
| [`progress.py`](../src/yt_downloader/progress.py) | `RichLogger` (yt-dlp logger: debug only when verbose, warnings and errors always), `DownloadProgress` (progress bars from yt-dlp's hooks, FFmpeg step lines), `describe_file`. | No | manual |
| [`info.py`](../src/yt_downloader/info.py) | Summarises an info dict: `codec_family`, `resolution_rows`, `audio_rows`, `default_choice` (pure), and `render_video`/`render_formats`/`render_playlist` (Rich tables). | Rows are pure | `test_info.py` |
| [`preflight.py`](../src/yt_downloader/preflight.py) | `check_tools()` returns the required tools (ffmpeg, ffprobe) and optional tools (deno) that are missing. | Yes (uses `shutil.which`) | `test_preflight.py` |

## Request flow (download commands)

1. **cli**: Typer parses the arguments. Option callbacks (`_validate_*`) reject bad input with exit code 2.
2. **cli**: `_run_preflight()` exits with 2 if ffmpeg or ffprobe is missing and warns if deno is missing. `info` passes `require_ffmpeg=False`.
3. **options**: `build_video_params` / `build_clip_params` / `build_audio_params` / `build_info_params` start from `build_common_params` and add the command-specific settings.
4. **downloader**: `download()` adds the runtime-only parameters (logger, `progress_hooks`, `postprocessor_hooks`, `post_hooks`, and quiet FFmpeg arguments when not verbose), then calls `ydl.download([url])` for each URL. A `DownloadError` marks the URL as failed and prints a hint.
5. **yt-dlp**: extracts the info (using Deno for JS challenges), picks formats, downloads (natively, or FFmpeg for ranges and HLS), then runs the post-processors in order.
6. **cli**: `_print_report()` prints "✓ Saved …" for each final path (from `post_hooks`) and exits with 1 if any URL failed.

## yt-dlp parameters by command

Common (from `build_common_params`): `outtmpl`, `paths.home`, `windowsfilenames=True`, `noplaylist=not --playlist`, `retries=10`, `fragment_retries=10`, `noprogress=True`, plus optional `writesubtitles`/`subtitleslangs`, `writethumbnail`, `cookiesfrombrowser`, `download_archive`, `ratelimit`, `sleep_interval`.

| Command | Format selector | Other key parameters | Post-processors (in order) |
|---|---|---|---|
| `video` | `bv*[height<=H]+ba/b[height<=H]` | `merge_output_format`; `--compat` → `format_sort: ["vcodec:h264","acodec:aac"]` | `FFmpegVideoRemuxer` → `FFmpegEmbedSubtitle`? → `FFmpegMetadata` (chapters) → `EmbedThumbnail`? |
| `clip` | same as video | `download_ranges=download_range_func(None, [(start, end)])`, `force_keyframes_at_cuts=--precise`, clip `outtmpl` with `%(section_start>%H-%M-%S)s` | as video, but `FFmpegMetadata` without chapters, no subtitles |
| `audio` | m4a `ba[acodec^=mp4a]/ba/b` · opus `ba[acodec=opus]/ba/b` · mp3/best `ba/b` | `download_archive` → `archive-audio.txt` | `FFmpegExtractAudio` (`preferredcodec`, `preferredquality`?) → `FFmpegMetadata` → `EmbedThumbnail`? |
| `info` | yt-dlp default | `skip_download=True`, `extract_flat="in_playlist"`; `embed_thumbnail=False` | none |

The post-processor order follows the yt-dlp CLI (`yt_dlp/__init__.py`): change the container first, then embed things into the final container.

## Output

| What | Where / format |
|---|---|
| Files | `<output_dir>/Title [id].ext` (default `./downloads`, relative to the current folder) |
| Clips | `<output_dir>/Title [id] HH-MM-SS to HH-MM-SS.ext` |
| Archives | `<output_dir>/archive.txt` (video), `<output_dir>/archive-audio.txt` (audio) |
| Messages | stdout through Rich. For `info --json`, logs go to stderr (`err_console`) and the JSON to stdout. |
| Exit codes | 0 ok · 1 a download or extraction failed · 2 bad usage or a missing required tool |

## yt-dlp quirks this code works around

| Quirk | Where handled |
|---|---|
| Post-processors passed in the params get our `postprocessor_hooks` registered twice, so every step fires twice | `DownloadProgress.postprocessor_hook` skips a repeat of the same `(name, filepath)` |
| When FFmpeg does the downloading (ranges, HLS), its stats go straight to the terminal | `download()` sets `external_downloader_args={"ffmpeg_i1": ["-loglevel","error","-nostats"]}` unless verbose |
| With a `logger` set, all `to_screen` output goes to `logger.debug` | `RichLogger.debug` prints only with `--verbose` |
| Rich treats `[videoID]` in filenames as markup | Paths and titles go through `rich.markup.escape` |
| `noplaylist` only affects watch URLs that also have `&list=`; a pure `playlist?list=` URL always downloads the whole list | Documented; `--playlist` help text is written with this in mind |
| DRC (`-drc`) audio formats are volume-normalised duplicates | `info.audio_rows` skips them |
| Post-processor hook names are `pp_key()` (class name without `FFmpeg`/`PP`), e.g. `Merger`, `ExtractAudio` | `POSTPROCESSOR_LABELS` in `progress.py` |

## Extension points

- **New command:** see the step-by-step guide in [DEVELOPMENT.md](DEVELOPMENT.md#adding-a-new-command).
- **New shared option:** add a field to `CommonOptions`, map it in `build_common_params`, add an `Annotated` alias in `cli.py`, and use it in the commands that need it.
- **New error hint:** add `(substring, hint)` to `ERROR_HINTS`. Put more specific substrings before general ones, since the first match wins.
- **New FFmpeg step label:** add the post-processor's `pp_key()` to `POSTPROCESSOR_LABELS`.
