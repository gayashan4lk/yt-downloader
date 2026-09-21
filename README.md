# yt-downloader

> **Note:** The tool will be one program, `ytdl`, with subcommands, the same way `git` has `git commit` and `git push`. Each subcommand is a separate job with its own options:
>
> | Subcommand | What it does | Example | How FFmpeg is used |
> |---|---|---|---|
> | **`video`** | Downloads the full video at the best quality you allow | `ytdl video URL --max-height 1080` | Merges YouTube's separate video and audio streams into one MP4 or MKV, and embeds metadata and the thumbnail |
> | **`audio`** | Downloads only the sound, e.g. podcasts, music, lectures | `ytdl audio URL --codec mp3` | Converts the audio stream to MP3, M4A or Opus |
> | **`clip`** | Downloads just part of a video | `ytdl clip URL --start 1:30 --end 2:45` | Cuts that time range cleanly so you don't download the whole thing |
> | **`info`** | Shows details without downloading anything: title, duration, and the available resolutions and codecs | `ytdl info URL` | Not used. Handy for checking a URL or picking a quality first. |

## Setup

Requires [uv](https://docs.astral.sh/uv/), FFmpeg and Deno (yt-dlp uses Deno to solve YouTube's JavaScript challenges):

```bash
brew install uv ffmpeg deno
uv sync
```

## Usage

```bash
uv run ytdl video URL                        # best quality, MP4, saved to ./downloads
uv run ytdl video URL --max-height 1080      # cap the resolution
uv run ytdl video URL --compat               # H.264 + AAC: plays in QuickTime, iOS, TVs
uv run ytdl video URL -f mkv                 # MKV container
uv run ytdl video URL1 URL2 -o ~/Videos      # several URLs, custom folder
uv run ytdl video URL --subs en,si           # embed subtitles
uv run ytdl video PLAYLIST_URL --archive     # whole playlist, skip already-downloaded
uv run ytdl video --help                     # all options
```

### Audio

```bash
uv run ytdl audio URL                        # m4a (AAC): copied as-is, no quality loss, plays everywhere
uv run ytdl audio URL -c mp3                 # mp3: re-encoded by FFmpeg (VBR quality 2 by default)
uv run ytdl audio URL -c mp3 -q 320k         # mp3 at a fixed bitrate
uv run ytdl audio URL -c opus                # opus: YouTube's best audio, smallest files, copied as-is
uv run ytdl audio PLAYLIST_URL --archive     # whole playlist, skip already-downloaded
uv run ytdl audio --help                     # all options
```

`--quality` only matters when FFmpeg re-encodes: `0` (best) to `10` (smallest), or a bitrate like `192k`.
Audio downloads use their own `archive-audio.txt`, so downloading a video doesn't make `audio` skip it.

### Clips

Only the chosen range is downloaded. Times can be `90`, `1:30` or `1:02:03`.

```bash
uv run ytdl clip URL --start 1:30 --end 2:45  # frame-exact cut (re-encodes to H.264/AAC)
uv run ytdl clip URL -s 1:30 -e 2:45 --fast   # no re-encode, faster, may be off by a few seconds
uv run ytdl clip URL -s 10:00                 # from 10:00 to the end
uv run ytdl clip URL -e 0:30                  # first 30 seconds
uv run ytdl clip --help                       # all options
```

Clips are saved as `Title [id] 00-01-30 to 00-02-45.mp4`, so they never overwrite the full video.

### Info

Nothing is downloaded, and FFmpeg isn't needed.

```bash
uv run ytdl info URL                         # title, channel, duration, subtitles, qualities by resolution and codec
uv run ytdl info URL -F                      # also list every format (like yt-dlp -F)
uv run ytdl info URL --json | jq .title      # full metadata as JSON for scripts
uv run ytdl info PLAYLIST_URL                # playlist title and its videos
```

The "ytdl video gets" line shows what `ytdl video` would download with no options. Use the resolution table to choose `--max-height`: if H.264 is listed at a resolution, `--compat` can get it.

Update yt-dlp regularly, since YouTube changes often break older versions:

```bash
uv lock --upgrade-package yt-dlp && uv sync
```

## Development

```bash
uv run pytest
uv run ruff check src tests && uv run ruff format src tests
```

## Documentation

| Document | What's in it |
|---|---|
| [docs/PRD.md](docs/PRD.md) | Goals, users, requirements for each command and their status, risks, open questions |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Modules, request flow, yt-dlp settings per command, yt-dlp quirks worked around |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decision log: why yt-dlp, Python, the m4a default, precise clips, … |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Prioritised backlog, known limitations, maintenance tasks |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Setup, workflow, testing strategy, real-URL checklist, adding a command, troubleshooting |
| [CLAUDE.md](CLAUDE.md) | Short brief for AI coding assistants |

Only download content you have the right to: your own, Creative Commons, public domain, or with permission.
