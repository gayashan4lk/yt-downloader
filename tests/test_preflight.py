from yt_downloader import preflight


def fake_which(installed):
    return lambda name: f"/usr/local/bin/{name}" if name in installed else None


def test_all_tools_present(monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", fake_which({"ffmpeg", "ffprobe", "deno"}))
    result = preflight.check_tools()
    assert result.ok
    assert result.missing_optional == []


def test_missing_ffmpeg_is_fatal(monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", fake_which({"ffprobe", "deno"}))
    result = preflight.check_tools()
    assert not result.ok
    assert [t.name for t in result.missing_required] == ["ffmpeg"]


def test_missing_deno_is_only_a_warning(monkeypatch):
    monkeypatch.setattr(preflight.shutil, "which", fake_which({"ffmpeg", "ffprobe"}))
    result = preflight.check_tools()
    assert result.ok
    assert [t.name for t in result.missing_optional] == ["deno"]
