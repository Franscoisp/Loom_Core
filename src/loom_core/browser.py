"""Controlled Web Browser Tool (spec §12).

A well-behaved web-fetching tool that loops can call for documentation lookup,
research, version checks, etc. Results are distillable into Loom Memory.

Safety: domain allowlist by default; untrusted URLs require an explicit flag.
Uses stdlib `urllib` + `html.parser` — no extra dependencies.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from io import StringIO
from urllib.parse import urlparse

# Domains that can be fetched without the allow_untrusted flag.
_DEFAULT_ALLOWED: set[str] = {
    "docs.python.org",
    "pypi.org",
    "github.com",
    "raw.githubusercontent.com",
    "python.org",
    "readthedocs.io",
}


class _TextExtractor(HTMLParser):
    """Extract visible text from HTML, stripping tags and scripts/styles."""

    def __init__(self) -> None:
        super().__init__()
        self._text = StringIO()
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = False
        if tag in ("p", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "div", "tr"):
            self._text.write("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._text.write(data)

    def get_text(self) -> str:
        raw = self._text.getvalue()
        return re.sub(r"\n{3,}", "\n\n", raw).strip()


def _fetch_raw(url: str, timeout: int = 15) -> tuple[int, str, str | None]:
    """Return (http_status, body_text, error_message)."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Loom-Core-WebBrowser/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.status, body.decode(charset, errors="replace"), None
    except urllib.error.HTTPError as exc:
        return exc.code, "", str(exc)
    except Exception as exc:
        return 0, "", str(exc)


def _extract_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.get_text()


class WebBrowser:
    """Controlled web-fetching tool (spec §12). Results are distillable."""

    def __init__(
        self,
        allowed_domains: set[str] | None = None,
        timeout: int = 15,
        max_chars: int = 50_000,
    ) -> None:
        self.allowed = allowed_domains or _DEFAULT_ALLOWED
        self.timeout = timeout
        self.max_chars = max_chars

    def _check_domain(self, url: str, allow_untrusted: bool) -> None:
        if allow_untrusted:
            return
        host = urlparse(url).hostname or ""
        for allowed in self.allowed:
            if host == allowed or host.endswith("." + allowed):
                return
        raise PermissionError(
            f"domain {host!r} is not in the allowlist. "
            f"Use allow_untrusted=True to bypass."
        )

    def fetch(
        self,
        url: str,
        *,
        allow_untrusted: bool = False,
    ) -> dict[str, object]:
        """Fetch a URL and return structured content.

        Returns a dict with keys: url, status, ok, text, length, error.
        """
        self._check_domain(url, allow_untrusted)
        status, html, error = _fetch_raw(url, self.timeout)
        if error:
            return {
                "url": url,
                "status": status,
                "ok": False,
                "text": "",
                "length": 0,
                "error": error,
            }
        text = _extract_text(html)
        if len(text) > self.max_chars:
            text = text[: self.max_chars] + "\n\n... (truncated)"
        return {
            "url": url,
            "status": status,
            "ok": status < 400,
            "text": text,
            "length": len(text),
            "error": None,
        }
