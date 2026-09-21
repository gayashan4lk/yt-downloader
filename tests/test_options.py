from pathlib import Path

import pytest

from yt_downloader.options import (
    CommonOptions,
    VideoOptions,
    build_common_params,
    build_format,
    build_video_params,
    parse_rate_limit,
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
