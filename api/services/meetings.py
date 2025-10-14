"""Utilities for interacting with the external meeting provider."""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

try:  # pragma: no cover - exercised in environments with requests
    import requests  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised in offline test environments
    requests = None  # type: ignore


class MeetingProviderError(RuntimeError):
    """Raised when the meeting provider cannot fulfil a request."""


@dataclass
class MeetingDetails:
    meeting_url: str
    event_id: str


class MeetingProvider:
    """Simple client wrapper around a calendar/video meeting provider."""

    def __init__(self, base_url: Optional[str] = None, session: Optional[Any] = None) -> None:
        self.base_url = base_url or os.getenv("MEETING_PROVIDER_BASE_URL", "https://provider.invalid")
        if session is not None:
            self._session = session
        elif requests is not None:
            self._session = requests.Session()
        else:
            self._session = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def create_meeting(
        self,
        *,
        topic: str,
        start_time: datetime,
        meeting_type: str,
        location: Optional[str],
        max_participants: Optional[int],
    ) -> MeetingDetails:
        payload = {
            "topic": topic,
            "start_time": start_time.isoformat(),
            "meeting_type": meeting_type,
            "location": location,
            "max_participants": max_participants,
        }
        response_data = self._post("/meetings", payload)
        return MeetingDetails(
            meeting_url=response_data["meeting_url"],
            event_id=response_data["event_id"],
        )

    def update_meeting(self, *, event_id: str, start_time: datetime) -> MeetingDetails:
        payload = {
            "start_time": start_time.isoformat(),
        }
        response_data = self._patch(f"/meetings/{event_id}", payload)
        return MeetingDetails(
            meeting_url=response_data.get("meeting_url", ""),
            event_id=event_id,
        )

    def delete_meeting(self, *, event_id: str) -> None:
        self._delete(f"/meetings/{event_id}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("post", path, payload)

    def _patch(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("patch", path, payload)

    def _delete(self, path: str) -> Dict[str, Any]:
        return self._request("delete", path, None)

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if self._session is None:
            # Offline fallback that still produces deterministic looking data.
            if method.lower() == "post":
                event_id = uuid.uuid4().hex
                return {
                    "meeting_url": f"https://meet.stub/{event_id}",
                    "event_id": event_id,
                }
            return {}

        url = f"{self.base_url}{path}"
        try:
            request_method = getattr(self._session, method.lower())
        except AttributeError as exc:  # pragma: no cover - defensive programming
            raise MeetingProviderError(f"Unsupported HTTP method: {method}") from exc

        try:
            response = request_method(url, json=payload, timeout=10)
        except Exception as exc:  # pragma: no cover - network errors are not expected in tests
            raise MeetingProviderError("Failed to reach meeting provider") from exc

        if response.status_code >= 400:
            raise MeetingProviderError(
                f"Meeting provider returned status {response.status_code}: {response.text}"
            )

        if response.content:
            return response.json()
        return {}


meeting_provider = MeetingProvider()

__all__ = ["MeetingProvider", "MeetingProviderError", "MeetingDetails", "meeting_provider"]
