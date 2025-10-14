"""Minimal fallback implementation of a subset of the requests API for offline testing."""

from __future__ import annotations

import json as json_module
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


class ConnectionError(Exception):
    """Simplified connection error used to mimic requests.exceptions.ConnectionError."""


def _prepare_url(url: str, params: dict | None) -> str:
    if not params:
        return url
    parsed = urlparse(url)
    query = urlencode(params, doseq=True)
    new_query = f"{parsed.query}&{query}" if parsed.query else query
    return urlunparse(parsed._replace(query=new_query))


class Response:
    def __init__(self, status_code: int, headers, body: bytes):
        self.status_code = status_code
        self.headers = headers
        self._body = body

    @property
    def text(self) -> str:
        return self._body.decode("utf-8")

    def json(self):
        return json_module.loads(self._body.decode("utf-8"))


def _request(method: str, url: str, *, params=None, json=None, headers=None):
    target = _prepare_url(url, params)
    data = None
    request_headers = headers.copy() if headers else {}
    if json is not None:
        data = json_module.dumps(json).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(target, data=data, method=method.upper())
    for key, value in request_headers.items():
        request.add_header(key, value)
    try:
        with urlopen(request) as response:  # nosec B310 - only used in tests
            body = response.read()
            return Response(response.status, response.headers, body)
    except HTTPError as exc:  # pragma: no cover - error path is exercised in tests
        body = exc.read() or b""
        return Response(exc.code, exc.headers, body)
    except URLError as exc:  # pragma: no cover - connection failures are rare
        raise ConnectionError(str(exc)) from exc


def get(url: str, params=None, headers=None):
    return _request("GET", url, params=params, headers=headers)


def post(url: str, json=None, headers=None):
    return _request("POST", url, json=json, headers=headers)


exceptions = SimpleNamespace(ConnectionError=ConnectionError)

__all__ = ["get", "post", "exceptions", "Response", "ConnectionError"]
