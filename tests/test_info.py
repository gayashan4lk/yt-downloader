import pytest

from yt_downloader.info import (
    AudioRow,
    ResolutionRow,
    audio_rows,
    codec_family,
    default_choice,
    format_date,
    format_duration,
    resolution_rows,
)

# Trimmed-down formats shaped like yt-dlp's real YouTube output.
FORMATS = [
    {"format_id": "233", "ext": "mp4", "vcodec": "none", "acodec": None, "protocol": "m3u8_native"},
    {"format_id": "140-drc", "vcodec": "none", "acodec": "mp4a.40.2", "abr": 129.8, "filesize": 309_000},
    {"format_id": "140", "vcodec": "none", "acodec": "mp4a.40.2", "abr": 129.7, "filesize": 309_288},
    {"format_id": "139", "vcodec": "none", "acodec": "mp4a.40.5", "abr": 49.1, "filesize": 117_526},
    {"format_id": "251", "vcodec": "none", "acodec": "opus", "abr": 106.0, "filesize": 252_182},
    {"format_id": "160", "height": 144, "fps": 15, "vcodec": "avc1.4d400b", "acodec": "none", "filesize": 195_278},
    {"format_id": "278", "height": 144, "fps": 15, "vcodec": "vp9", "acodec": "none", "filesize": 185_292},
    {"format_id": "229", "height": 240, "fps": 15.0, "vcodec": "avc1.4D400C", "acodec": "none"},  # HLS, no size
    {"format_id": "133", "height": 240, "fps": 15, "vcodec": "avc1.4d400c", "acodec": "none", "filesize": 433_081},
    {"format_id": "395", "height": 240, "fps": 30, "vcodec": "av01.0.00M.08", "acodec": "none", "filesize": 223_779},
    {"format_id": "sb0", "ext": "mhtml", "vcodec": "none", "acodec": "none", "format_note": "storyboard"},
]


@pytest.mark.parametrize(
    "codec, expected",
    [
        ("avc1.4d400c", "H.264"),
        ("av01.0.00M.08.0.110", "AV1"),
        ("vp09.00.10.08", "VP9"),
        ("vp9", "VP9"),
        ("mp4a.40.2", "AAC"),
        ("opus", "Opus"),
        ("none", None),
        (None, None),
        ("weird", "weird"),
    ],
)
def test_codec_family(codec, expected):
    assert codec_family(codec) == expected


@pytest.mark.parametrize("seconds, expected", [(19, "0:19"), (125, "2:05"), (3723, "1:02:03"), (None, "unknown")])
def test_format_duration(seconds, expected):
    assert format_duration(seconds) == expected


def test_format_date():
    assert format_date("20050424") == "2005-04-24"
    assert format_date(None) == "unknown"


def test_resolution_rows_group_by_height_highest_first():
    assert resolution_rows(FORMATS) == [
        ResolutionRow(height=240, codecs=["AV1", "H.264"], fps=30, max_size=433_081),
        ResolutionRow(height=144, codecs=["VP9", "H.264"], fps=15, max_size=195_278),
    ]


def test_audio_rows_best_per_codec_skipping_drc_and_unknown():
    assert audio_rows(FORMATS) == [
        AudioRow(codec="AAC", bitrate=129.7, size=309_288, language=None),
        AudioRow(codec="Opus", bitrate=106.0, size=252_182, language=None),
    ]


def test_audio_rows_keep_languages_separate():
    formats = [
        {"format_id": "140-0", "vcodec": "none", "acodec": "mp4a.40.2", "abr": 128, "language": "en"},
        {"format_id": "140-1", "vcodec": "none", "acodec": "mp4a.40.2", "abr": 128, "language": "si"},
    ]
    assert [r.language for r in audio_rows(formats)] == ["en", "si"]


def test_default_choice():
    info = {"resolution": "1920x1080", "vcodec": "av01.0.08M", "acodec": "opus", "filesize_approx": 10 * 1024 * 1024}
    assert default_choice(info) == "1920x1080 AV1 + Opus (~10.00MiB)"
