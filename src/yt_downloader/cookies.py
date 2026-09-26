"""Inspect Netscape-format cookie files before handing them to yt-dlp.

Everything here is pure (reads one file, no network) so it can be unit-tested.

A stale cookie file fails with the same "Sign in to confirm you're not a bot" error
as no cookies at all, so `ytdl cookies check` exists to tell a live session from a
dead one without spending a download attempt.

Never print or log cookie *values*: they are credentials. Names, domains and expiry
times are safe to show.
"""

import contextlib
import http.cookiejar
import io
from dataclasses import dataclass
from pathlib import Path

from yt_dlp.cookies import YoutubeDLCookieJar

# Cookies that carry a signed-in YouTube session. Without at least one of these the
# file is just anonymous browsing state and won't get past the bot check.
AUTH_COOKIES = (
    "SID",
    "HSID",
    "SSID",
    "APISID",
    "SAPISID",
    "__Secure-1PSID",
    "__Secure-3PSID",
    "LOGIN_INFO",
)
# YouTube auth is split across both domains, so either one counts.
YOUTUBE_DOMAINS = ("youtube.com", "google.com")


@dataclass(frozen=True)
class CookieReport:
    """What a cookie file contains. Values are deliberately not included."""

    total: int
    domains: dict[str, int]
    auth_present: list[str]
    soonest_expiry: int | None  # Unix timestamp; None when every cookie is a session cookie.

    @property
    def has_youtube(self) -> bool:
        return any(self._is_youtube(domain) for domain in self.domains)

    @property
    def youtube_domains(self) -> dict[str, int]:
        return {domain: count for domain, count in self.domains.items() if self._is_youtube(domain)}

    @staticmethod
    def _is_youtube(domain: str) -> bool:
        bare = domain.lstrip(".")
        return any(bare == known or bare.endswith(f".{known}") for known in YOUTUBE_DOMAINS)


def inspect_cookie_file(path: Path) -> CookieReport:
    """Load a Netscape cookie file and summarise it.

    Raises ValueError (with yt-dlp's own message) if the file can't be read or isn't
    Netscape-formatted, so the caller decides the exit code.
    """
    jar = YoutubeDLCookieJar(str(path))
    try:
        # yt-dlp writes "skipping cookie file entry" warnings straight to stderr;
        # swallow them so our own message is the only output.
        with contextlib.redirect_stderr(io.StringIO()):
            jar.load()
    except http.cookiejar.LoadError as err:
        raise ValueError(str(err)) from err
    except OSError as err:
        raise ValueError(f"could not read {path}: {err.strerror or err}") from err

    domains: dict[str, int] = {}
    auth_present: list[str] = []
    expiries: list[int] = []
    for cookie in jar:
        domains[cookie.domain] = domains.get(cookie.domain, 0) + 1
        if cookie.name in AUTH_COOKIES and cookie.name not in auth_present:
            auth_present.append(cookie.name)
        # load() normalises session cookies (expires 0 or empty) to None.
        if cookie.expires is not None:
            expiries.append(cookie.expires)

    return CookieReport(
        total=sum(domains.values()),
        domains=domains,
        # Report in AUTH_COOKIES order rather than file order, so output is stable.
        auth_present=[name for name in AUTH_COOKIES if name in auth_present],
        soonest_expiry=min(expiries) if expiries else None,
    )
