"""Utility helpers for issuing and validating JWT access tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Iterable, Optional, Set

try:  # pragma: no cover - exercised when PyJWT is installed
    import jwt  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback implementation
    jwt = None

from flask import Response, g, jsonify, request


class AuthError(Exception):
    """Raised when authentication fails."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.status_code = status_code


def _get_secret_key() -> str:
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        # Provide a deterministic secret for testing environments while encouraging
        # production deployments to configure one explicitly.
        secret = "dev-secret-key"
    return secret


def _get_expiry_delta() -> timedelta:
    raw = os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "3600")
    try:
        seconds = int(raw)
    except ValueError as exc:  # pragma: no cover - guardrail for misconfiguration
        raise AuthError("Invalid JWT_ACCESS_TOKEN_EXPIRES value", status_code=500) from exc
    return timedelta(seconds=seconds)


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _encode_jwt(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_segment = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_segment = _b64encode(signature)
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def _decode_jwt(token: str, secret: str) -> dict:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise AuthError("Invalid token") from exc

    signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
    expected_signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_signature = _b64decode(signature_segment)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise AuthError("Invalid token")

    header = json.loads(_b64decode(header_segment))
    if header.get("alg") != "HS256":
        raise AuthError("Unsupported token algorithm")

    return json.loads(_b64decode(payload_segment))


def create_access_token(*, user_id: int, role: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT encoding the user identifier and role."""

    expiry = expires_delta or _get_expiry_delta()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + expiry).timestamp()),
    }
    secret = _get_secret_key()
    if jwt is not None:
        token = jwt.encode(payload, secret, algorithm="HS256")
        if isinstance(token, bytes):  # pragma: no cover - depends on PyJWT configuration
            token = token.decode("utf-8")
        return token
    return _encode_jwt(payload, secret)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT, returning the embedded payload."""
    secret = _get_secret_key()
    if jwt is not None:
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("Token has expired") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthError("Invalid token") from exc
    else:
        payload = _decode_jwt(token, secret)
        exp_timestamp = payload.get("exp")
        if exp_timestamp is None:
            raise AuthError("Token missing expiration")
        if datetime.now(timezone.utc).timestamp() > float(exp_timestamp):
            raise AuthError("Token has expired")

    if "sub" not in payload:
        raise AuthError("Token missing subject")
    if "role" not in payload:
        raise AuthError("Token missing role")
    return payload


def _extract_bearer_token() -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise AuthError("Authorization header missing")

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("Invalid authorization header")
    return parts[1]


def jwt_required(
    *, roles: Optional[Iterable[str]] = None, allow_self_kw: Optional[str] = None
):
    """Decorator enforcing that the request contains a valid JWT.

    Args:
        roles: Optional collection of roles allowed to access the endpoint.
        allow_self_kw: Name of a keyword argument that identifies a user id in the
            route. If supplied, a caller whose ``sub`` matches that value is
            permitted even if their role is not present in ``roles``.
    """

    allowed_roles: Optional[Set[str]] = set(roles) if roles is not None else None

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                token = _extract_bearer_token()
                payload = decode_access_token(token)
            except AuthError as exc:
                return jsonify({"error": str(exc)}), exc.status_code

            current_user = {
                "user_id": payload.get("sub"),
                "role": payload.get("role"),
            }
            g.current_user = current_user

            authorized = True
            if allowed_roles is not None:
                authorized = current_user["role"] in allowed_roles

            if not authorized and allow_self_kw is not None:
                target_user_id = kwargs.get(allow_self_kw)
                if target_user_id is not None and target_user_id == current_user["user_id"]:
                    authorized = True

            if not authorized:
                return jsonify({"error": "Forbidden"}), 403

            response: Response = func(*args, **kwargs)
            return response

        return wrapper

    return decorator


def current_user() -> Optional[dict]:
    """Return the JWT payload for the active request, if present."""

    return getattr(g, "current_user", None)


def access_token_expires_in() -> int:
    """Return the configured lifetime (in seconds) for generated tokens."""

    return int(_get_expiry_delta().total_seconds())

