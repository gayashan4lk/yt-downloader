import json

import pytest
from typer.testing import CliRunner

from yt_downloader import cli
from yt_downloader.downloader import DownloadReport, hint_for
from yt_downloader.preflight import PreflightResult

runner = CliRunner()


def stub(monkeypatch, report=None):
    """Replace preflight and the network download; return the captured call."""
    captured = {}

    def fake_download(urls, params, console, verbose=False):
        captured.update(urls=urls, params=params, verbose=verbose)
        return report or DownloadReport()

    monkeypatch.setattr(cli, "check_tools", lambda: PreflightResult([], []))
    monkeypatch.setattr(cli, "download", fake_download)
    return captured


def test_video_passes_options_to_downloader(monkeypatch):
    captured = stub(monkeypatch)
    result = runner.invoke(
        cli.app,
        ["video", "https://youtu.be/a", "https://youtu.be/b", "--max-height", "720", "-f", "mkv", "--subs", "en, si"],
    )
    assert result.exit_code == 0, result.output
    assert captured["urls"] == ["https://youtu.be/a", "https://youtu.be/b"]
    assert captured["params"]["format"] == "bv*[height<=720]+ba/b[height<=720]"
    assert captured["params"]["merge_output_format"] == "mkv"
    assert captured["params"]["subtitleslangs"] == ["en", "si"]


def test_video_rejects_unknown_container(monkeypatch):
    stub(monkeypatch)
    result = runner.invoke(cli.app, ["video", "https://youtu.be/a", "-f", "avi"])
    assert result.exit_code == 2


def test_video_rejects_bad_rate_limit(monkeypatch):
    stub(monkeypatch)
    result = runner.invoke(cli.app, ["video", "https://youtu.be/a", "--rate-limit", "fast"])
    assert result.exit_code == 2


def test_video_exit_code_on_failure(monkeypatch):
    stub(monkeypatch, report=DownloadReport(failed=["https://youtu.be/a"]))
    result = runner.invoke(cli.app, ["video", "https://youtu.be/a"])
    assert result.exit_code == 1


def test_missing_ffmpeg_stops_before_download(monkeypatch):
    captured = stub(monkeypatch)
    from yt_downloader.preflight import TOOLS

    monkeypatch.setattr(cli, "check_tools", lambda: PreflightResult([TOOLS[0]], []))
    result = runner.invoke(cli.app, ["video", "https://youtu.be/a"])
    assert result.exit_code == 2
    assert "ffmpeg" in result.output
    assert captured == {}


def test_hint_for_bot_check():
    assert "cookies" in hint_for("ERROR: [youtube] x: Sign in to confirm you're not a bot")
    assert "unavailable" in hint_for("ERROR: [youtube] x: This video is unavailable")
    assert "playlist" in hint_for("ERROR: [youtube:tab] x: YouTube said: The playlist does not exist.")
    assert hint_for("ERROR: something unrelated") is None


def test_clip_passes_range_to_downloader(monkeypatch):
    captured = stub(monkeypatch)
    result = runner.invoke(cli.app, ["clip", "https://youtu.be/a", "--start", "1:30", "--end", "2:45", "--fast"])
    assert result.exit_code == 0, result.output
    assert captured["urls"] == ["https://youtu.be/a"]
    ranges = list(captured["params"]["download_ranges"]({"id": "a"}, None))
    assert ranges == [{"start_time": 90, "end_time": 165}]
    assert captured["params"]["force_keyframes_at_cuts"] is False


def test_clip_start_only(monkeypatch):
    captured = stub(monkeypatch)
    result = runner.invoke(cli.app, ["clip", "https://youtu.be/a", "-s", "30"])
    assert result.exit_code == 0, result.output
    ranges = list(captured["params"]["download_ranges"]({"id": "a"}, None))
    assert ranges == [{"start_time": 30, "end_time": float("inf")}]


def test_clip_requires_a_time(monkeypatch):
    captured = stub(monkeypatch)
    result = runner.invoke(cli.app, ["clip", "https://youtu.be/a"])
    assert result.exit_code == 2
    assert captured == {}


@pytest.mark.parametrize(
    "args",
    [["--start", "2:00", "--end", "1:00"], ["--start", "abc"], ["--end", "1:75"]],
)
def test_clip_rejects_bad_times(monkeypatch, args):
    captured = stub(monkeypatch)
    result = runner.invoke(cli.app, ["clip", "https://youtu.be/a", *args])
    assert result.exit_code == 2
    assert captured == {}


def test_audio_passes_codec_and_quality(monkeypatch):
    captured = stub(monkeypatch)
    result = runner.invoke(
        cli.app, ["audio", "https://youtu.be/a", "https://youtu.be/b", "-c", "mp3", "-q", "192k", "--archive"]
    )
    assert result.exit_code == 0, result.output
    assert captured["urls"] == ["https://youtu.be/a", "https://youtu.be/b"]
    extract = captured["params"]["postprocessors"][0]
    assert extract == {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
    assert captured["params"]["download_archive"].endswith("archive-audio.txt")


def test_audio_defaults_to_m4a(monkeypatch):
    captured = stub(monkeypatch)
    result = runner.invoke(cli.app, ["audio", "https://youtu.be/a"])
    assert result.exit_code == 0, result.output
    assert captured["params"]["postprocessors"][0]["preferredcodec"] == "m4a"


@pytest.mark.parametrize("args", [["--codec", "wav"], ["--quality", "loud"], ["-q", "11"]])
def test_audio_rejects_bad_options(monkeypatch, args):
    captured = stub(monkeypatch)
    result = runner.invoke(cli.app, ["audio", "https://youtu.be/a", *args])
    assert result.exit_code == 2
    assert captured == {}


# --- info ---

VIDEO_INFO = {
    "id": "abc123",
    "title": "Test [video]",
    "channel": "Someone",
    "upload_date": "20240102",
    "duration": 125,
    "view_count": 1234567,
    "webpage_url": "https://www.youtube.com/watch?v=abc123",
    "resolution": "1280x720",
    "vcodec": "avc1.64001f",
    "acodec": "mp4a.40.2",
    "subtitles": {"en": [], "si": []},
    "formats": [
        {"format_id": "22", "height": 720, "fps": 30, "vcodec": "avc1.64001f", "acodec": "none", "filesize": 5_000_000},
        {"format_id": "140", "vcodec": "none", "acodec": "mp4a.40.2", "abr": 128, "filesize": 2_000_000},
    ],
}

PLAYLIST_INFO = {
    "_type": "playlist",
    "title": "My playlist",
    "channel": "Someone",
    "playlist_count": 2,
    "entries": [
        {"id": "a1", "title": "First", "duration": 60},
        {"id": "b2", "title": "Second", "duration": 90},
    ],
}


def stub_info(monkeypatch, data, tools=None):
    captured = {}

    def fake_fetch(url, params, console, verbose=False):
        captured.update(url=url, params=params)
        return data

    monkeypatch.setattr(cli, "check_tools", lambda: tools or PreflightResult([], []))
    monkeypatch.setattr(cli, "fetch_info", fake_fetch)
    return captured


def test_info_shows_summary_and_qualities(monkeypatch):
    captured = stub_info(monkeypatch, VIDEO_INFO)
    result = runner.invoke(cli.app, ["info", "https://youtu.be/abc123"], env={"COLUMNS": "120"})
    assert result.exit_code == 0, result.output
    assert captured["params"]["skip_download"] is True
    for text in ["Test [video]", "2024-01-02", "2:05", "1,234,567", "en, si", "720p", "H.264", "AAC", "128k"]:
        assert text in result.output
    assert "All formats" not in result.output


def test_info_formats_flag_lists_every_format(monkeypatch):
    stub_info(monkeypatch, VIDEO_INFO)
    result = runner.invoke(cli.app, ["info", "https://youtu.be/abc123", "-F"], env={"COLUMNS": "150"})
    assert result.exit_code == 0, result.output
    assert "All formats" in result.output


def test_info_json_is_valid_json(monkeypatch):
    stub_info(monkeypatch, VIDEO_INFO)
    result = runner.invoke(cli.app, ["info", "https://youtu.be/abc123", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["id"] == "abc123"


def test_info_playlist(monkeypatch):
    stub_info(monkeypatch, PLAYLIST_INFO)
    result = runner.invoke(cli.app, ["info", "https://youtube.com/playlist?list=x"], env={"COLUMNS": "120"})
    assert result.exit_code == 0, result.output
    for text in ["My playlist", "First", "Second", "2:30"]:
        assert text in result.output


def test_info_failure_exits_1(monkeypatch):
    stub_info(monkeypatch, None)
    result = runner.invoke(cli.app, ["info", "https://youtu.be/gone"])
    assert result.exit_code == 1


def test_info_works_without_ffmpeg(monkeypatch):
    from yt_downloader.preflight import TOOLS

    stub_info(monkeypatch, VIDEO_INFO, tools=PreflightResult([TOOLS[0]], []))
    result = runner.invoke(cli.app, ["info", "https://youtu.be/abc123"])
    assert result.exit_code == 0, result.output
