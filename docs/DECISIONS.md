# Decision Log

Short architecture decision records (ADRs). Add a new entry at the bottom whenever you make a choice that someone might later wonder about. Don't rewrite old entries: mark them **Superseded by ADR-N** and add a new one.

Format: **Context** (the situation) · **Decision** (what we chose) · **Consequences** (trade-offs).

---

### ADR-1: Use yt-dlp for extraction and FFmpeg for processing
*2026-09-21 · Accepted*

**Context.** FFmpeg can't read YouTube pages: stream URLs are protected by signature and "n" challenges and proof-of-origin tokens. The options were yt-dlp, pytubefix, or scraping ourselves.
**Decision.** Use yt-dlp's Python API (`YoutubeDL`) and let it drive FFmpeg through its post-processors.
**Consequences.** yt-dlp is the most actively maintained and gets YouTube fixes within days. We depend on its option names and hook behaviour. pytubefix was rejected because it breaks more often.

### ADR-2: Python rather than JavaScript
*2026-09-21 · Accepted*

**Context.** JS was an option. The only reliable extractor is yt-dlp, which is written in Python. The JS libraries (ytdl-core and its forks) were unreliable, and JS wrappers just run the yt-dlp program.
**Decision.** Python, calling yt-dlp directly.
**Consequences.** Typed options, callbacks and exceptions, with no parsing of yt-dlp's text output.

### ADR-3: uv, Python 3.12, `src/` layout, Typer + Rich
*2026-09-21 · Accepted*

**Context.** The system Python is 3.9; yt-dlp needs 3.10 or newer.
**Decision.** uv manages Python 3.12 and a lock file. `uv init --package` gives the `src/yt_downloader` layout and the `ytdl` command. Typer handles the CLI (options from type hints) and Rich the output.
**Consequences.** Run everything with `uv run`. Dev tools: pytest and ruff.

### ADR-4: Deno as the JavaScript runtime
*2026-09-21 · Accepted*

**Context.** Since late 2025, yt-dlp needs an external JS runtime for full YouTube support. Deno is the only runtime it enables by default.
**Decision.** Require Deno (installed with Homebrew). Preflight warns, rather than fails, if it's missing.
**Consequences.** Node and Bun would need an explicit `js_runtimes` setting; not supported for now.

### ADR-5: Keep all yt-dlp settings in pure `options.py` builders
*2026-09-21 · Accepted*

**Context.** yt-dlp settings are the core logic, and they're easy to get subtly wrong.
**Decision.** CLI flags → dataclasses → `build_*_params()` return plain dicts. No network or filesystem access in `options.py`.
**Consequences.** Fast unit tests with no network. `cli.py` stays thin. Runtime-only settings (hooks, logger) are added in `downloader.py`.

### ADR-6: Filenames `Title [id].ext`, keeping Unicode
*2026-09-21 · Accepted*

**Context.** `restrictfilenames` turns non-ASCII titles (e.g. Sinhala) into underscores.
**Decision.** Use `windowsfilenames=True` (removes only characters invalid on any OS) and include the video ID so names are unique.
**Consequences.** Readable names in any language. Very long multi-byte titles could still exceed the 255-byte filename limit (see ROADMAP).

### ADR-7: Default video quality is "best", not "compatible"
*2026-09-21 · Accepted (open question in PRD)*

**Context.** YouTube's best streams are usually AV1 + Opus. In MP4, VLC, IINA and browsers play them, but QuickTime and iOS may not.
**Decision.** Default to best quality (`bv*+ba/b`). `--compat` sorts H.264/AAC first without re-encoding.
**Consequences.** Users on Apple devices may need `--compat`. Revisit if that turns out to be the common case.

### ADR-8: Download one URL at a time and keep going on failure
*2026-09-21 · Accepted*

**Decision.** Loop over URLs inside one `YoutubeDL`, catching `DownloadError` for each. The report collects saved files (from `post_hooks`) and failed URLs. Exit with 1 if any failed.
**Consequences.** One bad URL doesn't stop a batch. Errors are printed by our logger, and hints are added afterwards.

### ADR-9: Clips are frame-exact by default
*2026-09-21 · Accepted*

**Context.** Without `force_keyframes_at_cuts`, cuts snap to keyframes and can be seconds off. With it, FFmpeg re-encodes.
**Decision.** `--precise` is the default; `--fast` turns it off. Clip filenames include the range. Chapters aren't embedded (their times would be wrong). No `--subs`, `--archive` or `--playlist` for clips.
**Consequences.** Precise clips come out as H.264/AAC, so they play everywhere, but they're slower for long ranges.

### ADR-10: Audio defaults to m4a, copied without re-encoding
*2026-09-21 · Accepted*

**Context.** YouTube serves AAC (m4a, around 128k) and Opus (around 130k). Converting a lossy stream to another lossy format loses quality.
**Decision.** Pick the stream that matches the target (`ba[acodec^=mp4a]` for m4a, `ba[acodec=opus]` for opus) so FFmpeg copies it. Only mp3 re-encodes, with VBR 2 by default. FLAC/WAV are left out because the source is already lossy.
**Consequences.** Fast, no quality loss, m4a plays everywhere.

### ADR-11: A separate archive file for audio
*2026-09-21 · Accepted*

**Context.** yt-dlp's download archive only records `extractor id`, not what was downloaded. With one shared archive, downloading a video would make `audio` skip it.
**Decision.** `video` uses `archive.txt`; `audio` uses `archive-audio.txt`. `clip` has no archive.

### ADR-12: `info` doesn't need FFmpeg, and `--json` keeps stdout clean
*2026-09-21 · Accepted*

**Decision.** `_run_preflight(require_ffmpeg=False)` for `info`. With `--json`, logs and errors go to stderr (`err_console`) and only JSON goes to stdout. Playlists use `extract_flat="in_playlist"`.
**Consequences.** `ytdl info URL --json | jq` is safe to use in scripts, and playlist info is fast.

### ADR-13: Quieten FFmpeg and remove duplicate hook calls ourselves
*2026-09-21 · Accepted*

**Context.** Two yt-dlp behaviours made the output messy: FFmpeg's stats print directly when it does the downloading, and post-processor hooks are registered twice.
**Decision.** Pass `-loglevel error -nostats` before the first FFmpeg input when not verbose. Skip consecutive repeats of `(postprocessor, filepath)`.
**Consequences.** Clean output that still shows real FFmpeg errors. If yt-dlp fixes the double registration, the de-duplication does no harm.

### ADR-14: Cookie files (`--cookies`) alongside `--cookies-from-browser`
*2026-09-26 · Accepted*

**Context.** YouTube's bot check (`Sign in to confirm you're not a bot`) started blocking downloads even with yt-dlp at the latest stable and Deno installed. `--cookies-from-browser` was the only cookie source we had, and it has two structural problems: it can't read a private/incognito window, and cookies taken from a browser you actively use get rotated and invalidated by YouTube within a download or two. The workaround that holds up is a throwaway login session exported to a file — which needs a file flag.

**Decision.** Add `--cookies <file>` (yt-dlp's `cookiefile`) to all four commands, plus `ytdl cookies check <file>`. Three sub-decisions:

- **Keep yt-dlp's cookie writeback.** `cookiefile` is read *and* written: yt-dlp dumps refreshed cookies back after each run. Copying to a temp file would keep the user's export pristine but let the session go stale within a few runs, defeating the point.
- **No auto-discovered default path** (e.g. `~/.config/ytdl/cookies.txt`). The flag is always explicit. Credentials picked up implicitly are a surprise, and a shell alias covers the convenience case. Revisit if the config-file item on the roadmap lands.
- **Validate at parse time, not download time.** `_validate_cookies` runs `inspect_cookie_file` in a Typer callback, so a malformed or non-YouTube file exits 2 before any network call, per the repo's exit-code rule.

**Consequences.** `inspect_cookie_file` reuses `yt_dlp.cookies.YoutubeDLCookieJar.load()` rather than parsing Netscape format ourselves — it already rejects JSON exports with a useful message, handles the `#HttpOnly_` prefix, and normalises session cookies (`expires` 0 → `None`). That ties `cookies.py` to a yt-dlp internal module, which is a narrower API than the documented options dict; if it moves, the fallback is `http.cookiejar.MozillaCookieJar` plus our own JSON check. `check` needs a separate exit code for "parses but unusable" (1) versus "doesn't parse" (2).

Cookie files are credentials, so `check` prints only names, domains and expiry — never values — and nothing logs the file's contents, including under `--verbose`. This is enforced by a test in both `tests/test_cookies.py` and `tests/test_cli.py`.
