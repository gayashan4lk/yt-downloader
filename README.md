# yt-downloader

> **Note:** The tool will be one program, `ytdl`, with subcommands, the same way `git` has `git commit` and `git push`. Each subcommand is a separate job with its own options:
>
> | Subcommand | What it does | Example | How FFmpeg is used |
> |---|---|---|---|
> | **`video`** | Downloads the full video at the best quality you allow | `ytdl video URL --max-height 1080` | Merges YouTube's separate video and audio streams into one MP4 or MKV, and embeds metadata and the thumbnail |
> | **`audio`** | Downloads only the sound, e.g. podcasts, music, lectures | `ytdl audio URL --codec mp3` | Converts the audio stream to MP3, M4A or Opus |
> | **`clip`** | Downloads just part of a video | `ytdl clip URL --start 1:30 --end 2:45` | Cuts that time range cleanly so you don't download the whole thing |
> | **`info`** | Shows details without downloading anything: title, duration, and the available resolutions and codecs | `ytdl info URL` | Not used. Handy for checking a URL or picking a quality first. |
