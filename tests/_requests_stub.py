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


def _request(method: str, url: str, *, params=None, json=None, data=None, headers=None):
    target = _prepare_url(url, params)
    body_data = data
    header_map = {"Content-Type": "application/json"} if json is not None else {}
    if json is not None:
        body_data = json_module.dumps(json).encode("utf-8")
    if headers:
        header_map.update(headers)
    if body_data is not None and isinstance(body_data, str):
        body_data = body_data.encode("utf-8")
    request = Request(target, data=body_data, method=method.upper())
    for key, value in header_map.items():
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


def get(url: str, params=None):
    return _request("GET", url, params=params)


def post(url: str, json=None, data=None, headers=None):
    return _request("POST", url, json=json, data=data, headers=headers)


def delete(url: str, json=None, data=None, headers=None):
    return _request("DELETE", url, json=json, data=data, headers=headers)


exceptions = SimpleNamespace(ConnectionError=ConnectionError)

__all__ = ["get", "post", "delete", "exceptions", "Response", "ConnectionError"]
