from pathlib import Path

import pytest

from yt_downloader.options import (
    ClipOptions,
    CommonOptions,
    VideoOptions,
    build_clip_params,
    build_common_params,
    build_format,
    build_video_params,
    parse_rate_limit,
    parse_timestamp,
)


def pp_keys(params):
    return [pp["key"] for pp in params["postprocessors"]]


def test_format_without_height_limit():
    assert build_format(None) == "bv*+ba/b"


def test_format_with_height_limit_applies_to_both_branches():
    assert build_format(1080) == "bv*[height<=1080]+ba/b[height<=1080]"


def test_common_defaults():
    params = build_common_params(CommonOptions())
    assert params["paths"] == {"home": "downloads"}
    assert params["outtmpl"] == {"default": "%(title)s [%(id)s].%(ext)s"}
    assert params["noplaylist"] is True
    assert params["windowsfilenames"] is True
    assert params["writethumbnail"] is True
    for absent in ("cookiesfrombrowser", "download_archive", "ratelimit", "sleep_interval", "writesubtitles"):
        assert absent not in params


def test_common_optional_settings():
    params = build_common_params(
        CommonOptions(
            output_dir=Path("out"),
            subtitle_langs=["en", "si"],
            embed_thumbnail=False,
            cookies_from_browser="chrome",
            use_archive=True,
            playlist=True,
            rate_limit="2M",
            sleep_seconds=3,
        )
    )
    assert params["subtitleslangs"] == ["en", "si"]
    assert params["writesubtitles"] is True
    assert "writethumbnail" not in params
    assert params["cookiesfrombrowser"] == ("chrome",)
    assert params["download_archive"] == str(Path("out") / "archive.txt")
    assert params["noplaylist"] is False
    assert params["ratelimit"] == 2 * 1024 * 1024
    assert params["sleep_interval"] == 3


def test_video_defaults():
    params = build_video_params(CommonOptions(), VideoOptions())
    assert params["format"] == "bv*+ba/b"
    assert params["merge_output_format"] == "mp4"
    assert "format_sort" not in params
    assert pp_keys(params) == ["FFmpegVideoRemuxer", "FFmpegMetadata", "EmbedThumbnail"]
    assert params["postprocessors"][0]["preferedformat"] == "mp4"


def test_video_mkv_with_subs_and_no_thumbnail():
    params = build_video_params(
        CommonOptions(subtitle_langs=["en"], embed_thumbnail=False),
        VideoOptions(max_height=720, container="mkv"),
    )
    assert params["format"] == "bv*[height<=720]+ba/b[height<=720]"
    assert params["merge_output_format"] == "mkv"
    assert pp_keys(params) == ["FFmpegVideoRemuxer", "FFmpegEmbedSubtitle", "FFmpegMetadata"]


def test_video_compat_prefers_h264_aac():
    params = build_video_params(CommonOptions(), VideoOptions(compat=True))
    assert params["format_sort"] == ["vcodec:h264", "acodec:aac"]


@pytest.mark.parametrize("value, expected", [("500K", 500 * 1024), ("2M", 2 * 1024 * 1024), ("1024", 1024)])
def test_parse_rate_limit(value, expected):
    assert parse_rate_limit(value) == expected


@pytest.mark.parametrize("value", ["fast", "", "2X"])
def test_parse_rate_limit_rejects_garbage(value):
    with pytest.raises(ValueError):
        parse_rate_limit(value)


# --- clip ---


@pytest.mark.parametrize(
    "value, expected",
    [("90", 90), ("1:30", 90), ("01:02:03", 3723), ("1:30.5", 90.5), ("0", 0), (" 2:00 ", 120)],
)
def test_parse_timestamp(value, expected):
    assert parse_timestamp(value) == expected


@pytest.mark.parametrize("value", ["", "abc", "1:2:3:4", "1:60", "-5", "1:-3"])
def test_parse_timestamp_rejects_garbage(value):
    with pytest.raises(ValueError):
        parse_timestamp(value)


def ranges_of(params):
    return list(params["download_ranges"]({"id": "x", "duration": 600}, None))


def test_clip_params():
    params = build_clip_params(CommonOptions(), VideoOptions(max_height=720), ClipOptions(start=90, end=165))
    assert ranges_of(params) == [{"start_time": 90, "end_time": 165}]
    assert params["force_keyframes_at_cuts"] is True
    assert params["format"] == "bv*[height<=720]+ba/b[height<=720]"
    assert "section_start" in params["outtmpl"]["default"]
    metadata = next(pp for pp in params["postprocessors"] if pp["key"] == "FFmpegMetadata")
    assert metadata["add_chapters"] is False


def test_clip_without_end_runs_to_end_of_video():
    params = build_clip_params(CommonOptions(), VideoOptions(), ClipOptions(start=30, precise=False))
    assert ranges_of(params) == [{"start_time": 30, "end_time": float("inf")}]
    assert params["force_keyframes_at_cuts"] is False


def test_clip_rejects_end_before_start():
    with pytest.raises(ValueError):
        build_clip_params(CommonOptions(), VideoOptions(), ClipOptions(start=60, end=30))


def test_video_keeps_chapters():
    params = build_video_params(CommonOptions(), VideoOptions())
    metadata = next(pp for pp in params["postprocessors"] if pp["key"] == "FFmpegMetadata")
    assert metadata["add_chapters"] is True
