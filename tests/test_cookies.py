import pytest

from yt_downloader.cookies import inspect_cookie_file

HEADER = "# Netscape HTTP Cookie File\n"
FAR_FUTURE = 4102444800  # 2100-01-01


def write_cookies(tmp_path, *entries, header=HEADER, name="cookies.txt"):
    """Write a Netscape cookie file. Each entry is (domain, expires, name)."""
    path = tmp_path / name
    # Field 2 must say whether the domain covers subdomains, i.e. whether it has a
    # leading dot. http.cookiejar rejects the file if the two disagree.
    lines = [
        f"{domain}\t{str(domain.startswith('.')).upper()}\t/\tTRUE\t{expires}\t{cookie}\tvalue"
        for domain, expires, cookie in entries
    ]
    path.write_text(header + "\n".join(lines) + "\n")
    return path


def test_reads_a_valid_file(tmp_path):
    path = write_cookies(
        tmp_path,
        (".youtube.com", FAR_FUTURE, "SID"),
        (".youtube.com", FAR_FUTURE, "PREF"),
        (".google.com", FAR_FUTURE, "LOGIN_INFO"),
    )
    report = inspect_cookie_file(path)
    assert report.total == 3
    assert report.domains == {".youtube.com": 2, ".google.com": 1}
    assert report.has_youtube
    assert report.soonest_expiry == FAR_FUTURE


def test_auth_cookies_are_reported_in_a_stable_order(tmp_path):
    # Written LOGIN_INFO first, but AUTH_COOKIES lists SID and HSID before it.
    path = write_cookies(
        tmp_path,
        (".google.com", FAR_FUTURE, "LOGIN_INFO"),
        (".youtube.com", FAR_FUTURE, "HSID"),
        (".youtube.com", FAR_FUTURE, "SID"),
    )
    assert inspect_cookie_file(path).auth_present == ["SID", "HSID", "LOGIN_INFO"]


def test_no_auth_cookies(tmp_path):
    path = write_cookies(tmp_path, (".youtube.com", FAR_FUTURE, "PREF"))
    report = inspect_cookie_file(path)
    assert report.auth_present == []
    assert report.has_youtube  # The domain is there, the session isn't.


def test_session_cookies_have_no_expiry(tmp_path):
    # Expiry 0 means a session cookie; yt-dlp normalises it to None.
    path = write_cookies(tmp_path, (".youtube.com", 0, "SID"))
    assert inspect_cookie_file(path).soonest_expiry is None


def test_soonest_expiry_wins(tmp_path):
    path = write_cookies(
        tmp_path,
        (".youtube.com", FAR_FUTURE, "SID"),
        (".youtube.com", 1000000000, "HSID"),
        (".youtube.com", 0, "SSID"),  # Session cookie: ignored, not treated as expiry 0.
    )
    assert inspect_cookie_file(path).soonest_expiry == 1000000000


def test_unrelated_domains_are_not_youtube(tmp_path):
    path = write_cookies(tmp_path, (".example.com", FAR_FUTURE, "SID"))
    report = inspect_cookie_file(path)
    assert not report.has_youtube
    assert report.youtube_domains == {}


def test_subdomains_count_as_youtube(tmp_path):
    path = write_cookies(tmp_path, ("accounts.google.com", FAR_FUTURE, "SID"))
    assert inspect_cookie_file(path).has_youtube


def test_lookalike_domain_is_not_youtube(tmp_path):
    path = write_cookies(tmp_path, (".notyoutube.com", FAR_FUTURE, "SID"))
    assert not inspect_cookie_file(path).has_youtube


def test_missing_netscape_header(tmp_path):
    path = tmp_path / "bad.txt"
    path.write_text("just some text\nnot cookies\n")
    with pytest.raises(ValueError, match="Netscape"):
        inspect_cookie_file(path)


def test_json_export_is_rejected(tmp_path):
    path = tmp_path / "cookies.json"
    path.write_text('[{"name": "SID", "value": "x"}]\n')
    with pytest.raises(ValueError, match="not JSON"):
        inspect_cookie_file(path)


def test_missing_file(tmp_path):
    with pytest.raises(ValueError):
        inspect_cookie_file(tmp_path / "nope.txt")


def test_yt_dlp_warnings_are_not_printed(tmp_path, capsys):
    # A stray malformed line makes yt-dlp write "skipping cookie file entry" to stderr.
    path = tmp_path / "cookies.txt"
    path.write_text(HEADER + "garbage line\n" + f".youtube.com\tTRUE\t/\tTRUE\t{FAR_FUTURE}\tSID\tvalue\n")
    report = inspect_cookie_file(path)
    assert report.total == 1
    assert capsys.readouterr().err == ""


def test_values_are_not_retained(tmp_path):
    path = write_cookies(tmp_path, (".youtube.com", FAR_FUTURE, "SID"))
    # Cookies are credentials: the report must never carry their values.
    assert "value" not in repr(inspect_cookie_file(path))
