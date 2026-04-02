"""
HTTP client abstraction built on ``httpx``.

UltraDL uses a shared client for connection pooling, cookie persistence, and
consistent headers. Extractors receive a callable or this client to fetch
pages and manifests without duplicating TLS/session configuration.
"""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional, Union
from urllib.parse import urljoin, urlparse

import httpx

from .logger import get_logger

log = get_logger("network")


def build_browser_headers(user_agent: str, referer: Optional[str] = None) -> Dict[str, str]:
    h: Dict[str, str] = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }
    if referer:
        h["Referer"] = referer
    return h


@dataclass
class FetchResult:
    url: str
    status_code: int
    text: str
    content: bytes
    headers: Mapping[str, str]


class HTTPClient:
    """
    Thin wrapper around ``httpx.Client`` with retry-friendly streaming helpers.

    The client is designed to be long-lived: construct once per download manager
    and reuse across tasks for better TCP/TLS amortization on busy queues.
    """

    def __init__(
        self,
        user_agent: str,
        timeout: float = 60.0,
        *,
        trust_env: bool = True,
        http2: bool = False,
    ) -> None:
        self._timeout = timeout
        self._headers = build_browser_headers(user_agent)
        self._client = httpx.Client(
            headers=self._headers,
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            trust_env=trust_env,
            http2=http2,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HTTPClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def get_bytes(self, url: str, **kwargs: Any) -> FetchResult:
        headers = dict(self._headers)
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        r = self._client.get(url, headers=headers, **kwargs)
        return FetchResult(
            url=str(r.url),
            status_code=r.status_code,
            text=r.text,
            content=r.content,
            headers=r.headers,
        )

    def get_text(self, url: str, **kwargs: Any) -> str:
        return self.get_bytes(url, **kwargs).text

    def head(self, url: str, **kwargs: Any) -> httpx.Response:
        headers = dict(self._headers)
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        return self._client.head(url, headers=headers, **kwargs)

    def resolve_url(self, base: str, relative: str) -> str:
        return urljoin(base, relative)

    def iter_content_stream(
        self,
        url: str,
        chunk_size: int = 1024 * 1024,
        *,
        headers: Optional[Dict[str, str]] = None,
    ) -> Iterator[bytes]:
        """Stream response body in fixed-size chunks for large progressive files."""
        h = dict(self._headers)
        if headers:
            h.update(headers)
        with self._client.stream("GET", url, headers=h) as r:
            r.raise_for_status()
            for chunk in r.iter_bytes(chunk_size):
                yield chunk

    def download_to_path(
        self,
        url: str,
        dest: Path,
        *,
        chunk_size: int = 1024 * 1024,
        headers: Optional[Dict[str, str]] = None,
        resume: bool = False,
    ) -> None:
        """
        Download a single URL to ``dest``.

        ``resume`` uses HTTP Range when the server advertises Accept-Ranges.
        """
        part = dest.with_suffix(dest.suffix + ".part")
        part.parent.mkdir(parents=True, exist_ok=True)
        mode = "ab" if resume else "wb"
        start = part.stat().st_size if resume and part.exists() else 0
        h = dict(self._headers)
        if headers:
            h.update(headers)
        if resume and start > 0:
            h["Range"] = f"bytes={start}-"
        with self._client.stream("GET", url, headers=h) as r:
            if resume and r.status_code == 416:
                log.warning("Server rejected resume range for %s; restarting", url)
                return self.download_to_path(url, dest, chunk_size=chunk_size, headers=headers, resume=False)
            r.raise_for_status()
            with part.open(mode) as f:
                for chunk in r.iter_bytes(chunk_size):
                    f.write(chunk)
        part.replace(dest)


def guess_extension_from_url(url: str) -> Optional[str]:
    path = urlparse(url).path
    ext = Path(path).suffix
    if ext:
        return ext
    return mimetypes.guess_extension(urlparse(url).path.split("/")[-1] or "")
