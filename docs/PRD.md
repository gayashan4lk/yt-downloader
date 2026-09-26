# Product Requirements: yt-downloader (`ytdl`)

| | |
|---|---|
| **Status** | v0.1.0 – all four core commands shipped (`video`, `clip`, `audio`, `info`) |
| **Owner** | gayashan4lk |
| **Last updated** | 2026-09-21 |
| **Related** | [Architecture](ARCHITECTURE.md) · [Decisions](DECISIONS.md) · [Roadmap](ROADMAP.md) · [Development guide](DEVELOPMENT.md) |

## 1. Summary

`ytdl` is a command-line tool for downloading YouTube videos, audio and clips. It wraps **yt-dlp**, which extracts the media, and **FFmpeg**, which merges, converts and cuts it. The aim is to make the common cases a single short command with sensible defaults, and to explain failures in plain language.

## 2. Problem

- **FFmpeg can't download from YouTube on its own.** YouTube hides its stream URLs behind signature and JavaScript challenges and proof-of-origin tokens.
- **yt-dlp can, but it has hundreds of options.** Common jobs need options that are easy to get wrong: `-f "bv*+ba/b"`, `--merge-output-format`, `--download-sections`, `--force-keyframes-at-cuts`, `-x --audio-format`, and so on.
- **High-quality YouTube video comes as separate video and audio streams.** They have to be merged, and the default codecs (AV1 and Opus) don't play everywhere.
- **Errors are cryptic.** Messages like "Sign in to confirm you're not a bot" or "Requested format is not available" don't say what to do next.

## 3. Goals

1. **One command per job:** `video`, `audio`, `clip`, `info`.
2. **Best quality by default,** with simple controls for resolution, container, codec and compatibility.
3. **No needless re-encoding.** Copy streams when possible; re-encode only when the user asks for it (mp3, precise clips).
4. **Clear feedback:** progress bars, named FFmpeg steps, the saved path and size, and a plain-language hint for known errors.
5. **Easy to keep working.** yt-dlp is updated with one command, and the tool checks its external dependencies before starting.
6. **Maintainable.** The logic that turns options into settings is pure and unit-tested without network access.

## 4. Non-goals

- A GUI or web interface.
- Supporting sites other than YouTube. yt-dlp supports many, and they may partly work, but they aren't tested or designed for.
- Getting around DRM, paywalls or members-only restrictions. Cookies only give yt-dlp the access the user's own account already has.
- Redistributing or re-hosting content.
- Replacing yt-dlp for power users. They should use yt-dlp directly.

## 5. Users

| Persona | Needs |
|---|---|
| **Personal archiver** | Save videos, lectures or playlists offline at good quality; re-run a playlist and only fetch new videos |
| **Listener** | Podcasts, talks or music as audio files that play on a phone |
| **Creator or editor** | Short clips of their own or licensed content, cut on the exact frame |
| **Scripter** | Machine-readable metadata (`info --json`) and dependable exit codes |

## 6. Functional requirements

Status: ✅ shipped · 🔜 planned (see [ROADMAP.md](ROADMAP.md))

### 6.1 `ytdl video URL...` ✅
| ID | Requirement | Status |
|---|---|---|
| V1 | Download the best video and audio and merge them with FFmpeg into MP4 (default) or MKV (`-f`) | ✅ |
| V2 | Cap the resolution (`--max-height`) | ✅ |
| V3 | Compatibility mode (`--compat`): prefer H.264 and AAC so the file plays in QuickTime, iOS and TVs, without re-encoding | ✅ |
| V4 | Embed metadata, chapters and thumbnail (thumbnail can be turned off) | ✅ |
| V5 | Embed subtitles for the given languages (`--subs en,si`) | ✅ |
| V6 | Several URLs in one run; one failure doesn't stop the others; exit code 1 if any failed | ✅ |
| V7 | Playlists: a pure playlist URL downloads the whole list; a watch URL with `&list=` downloads just that video unless `--playlist` is passed | ✅ |
| V8 | Archive (`--archive`): skip videos already downloaded | ✅ |
| V9 | Politeness and throttling: `--rate-limit`, `--sleep` | ✅ |
| V10 | Access to age-restricted videos and past bot checks using cookies, from a browser (`--cookies-from-browser`) or a Netscape cookies.txt file (`--cookies`), with `ytdl cookies check` to verify a file before use | ✅ |

### 6.2 `ytdl clip URL --start --end` ✅
| ID | Requirement | Status |
|---|---|---|
| C1 | Download only the requested time range. Times as `SS`, `MM:SS`, `HH:MM:SS`, decimals allowed | ✅ |
| C2 | Start only (to the end) or end only (from 0:00) | ✅ |
| C3 | Frame-exact cuts by default (`--precise`, re-encodes); `--fast` keeps the original streams | ✅ |
| C4 | The filename includes the range, so clips never overwrite the full video or each other | ✅ |
| C5 | Reject invalid ranges (end before start, bad format) before any network request | ✅ |
| C6 | Several ranges in one command | 🔜 |
| C7 | Audio-only clips | 🔜 |

### 6.3 `ytdl audio URL...` ✅
| ID | Requirement | Status |
|---|---|---|
| A1 | `--codec m4a` (default): fetch YouTube's AAC stream and copy it without re-encoding | ✅ |
| A2 | `--codec opus`: fetch the Opus stream and copy it; `best`: keep whatever the best stream is | ✅ |
| A3 | `--codec mp3`: re-encode; `--quality` as a VBR level 0–10 or a 32k–512k bitrate; default VBR 2 | ✅ |
| A4 | Embed metadata, chapters and cover art | ✅ |
| A5 | Separate archive (`archive-audio.txt`), so earlier video downloads don't block audio | ✅ |
| A6 | Playlists, archive, rate limit, sleep and cookies, as for `video` | ✅ |
| A7 | Lossless targets (FLAC/WAV) for editing workflows | 🔜 (deliberately left out; see DECISIONS) |

### 6.4 `ytdl info URL` ✅
| ID | Requirement | Status |
|---|---|---|
| I1 | Summary: title, channel, date, duration, views, chapters, subtitles, auto-caption count | ✅ |
| I2 | "ytdl video gets": what `video` would download with no options | ✅ |
| I3 | Qualities grouped by resolution (codecs, FPS, size) and by audio codec (bitrate, size, language) | ✅ |
| I4 | `-F`: every raw format | ✅ |
| I5 | `--json`: full metadata on stdout, logs on stderr | ✅ |
| I6 | Playlist or channel URL: list the videos without fetching each one | ✅ |
| I7 | Works without FFmpeg installed | ✅ |

### 6.5 Shared behaviour ✅
| ID | Requirement |
|---|---|
| S1 | Check for tools before starting: ffmpeg and ffprobe are required (except for `info`); a missing deno gives a warning |
| S2 | Default output folder `./downloads`; change it with `-o` |
| S3 | Filenames `Title [videoID].ext`. Unicode titles (e.g. Sinhala) are kept; characters invalid on Windows are removed |
| S4 | Progress bar for each stream, a named line for each FFmpeg step, then "✓ Saved <path> (<size>)" |
| S5 | Hints for known errors: bot check, age restriction, private, members-only, no matching format, unavailable, missing playlist, missing JS runtime |
| S6 | `-v/--verbose` shows yt-dlp's and FFmpeg's full output |
| S7 | Exit codes: `0` success, `1` one or more downloads failed, `2` bad usage or a missing required tool |

## 7. Non-functional requirements

| Area | Requirement |
|---|---|
| Platform | macOS (primary; Apple Silicon tested). Linux should work. Windows is untested. |
| Runtime | Python ≥ 3.12 via uv; FFmpeg ≥ 6 (9.0 tested); Deno ≥ 2 (2.9 tested) |
| Dependencies | yt-dlp (`[default,curl-cffi]`), typer, rich. Keep the list short. |
| Reliability | yt-dlp is updated easily and often. Retries: 10 per download and 10 per fragment. |
| Testability | Option-building and rendering are pure functions. Unit tests make no network calls. Real-URL checks are manual (see DEVELOPMENT.md). |
| Code quality | ruff lint and format pass (line length 120, rules `E F I UP B SIM`) |
| Performance | No re-encoding unless required. `info` on a playlist uses flat extraction. |

## 8. Constraints and risks

| Risk | Impact | Mitigation |
|---|---|---|
| YouTube changes break extraction | Downloads fail | Update yt-dlp: `uv lock --upgrade-package yt-dlp && uv sync` |
| JS challenges and PO tokens need Deno | Some or all formats missing | Deno is checked before starting; there's a hint for runtime errors |
| Bot detection or rate limiting | "Sign in to confirm…" errors | Hint suggests `--sleep`, cookies, retrying later |
| **Legal:** YouTube's Terms of Service only allow downloading through YouTube's own features or with the rights holder's permission | Misuse | Intended for your own content, Creative Commons or public-domain videos, or with permission. No DRM circumvention. |

## 9. Success criteria

- Each of the four commands works on a real public video with the default options.
- Real-URL checks from [DEVELOPMENT.md](DEVELOPMENT.md#manual-real-url-checks) pass after each yt-dlp upgrade.
- `uv run pytest` and `uv run ruff check` pass on every PR.

## 10. Open questions

1. Should `video` default to `--compat` (H.264/AAC) for easy playback on Apple devices, at the cost of lower maximum resolution? Currently: best quality by default.
2. Should the default output folder be fixed (e.g. `~/Downloads/ytdl`) instead of relative to where the command is run?
3. Is a config file (defaults per user) worth adding? See ROADMAP.
