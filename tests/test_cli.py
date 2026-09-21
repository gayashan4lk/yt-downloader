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
    assert hint_for("ERROR: something unrelated") is None
