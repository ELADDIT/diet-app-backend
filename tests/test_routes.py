import json
import hmac
import hashlib
import time
from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

try:  # pragma: no cover - exercised when requests is available
    import requests  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - offline fallback
    from . import _requests_stub as requests

from services import meetings
from services.meetings import MeetingDetails


class StubMeetingProvider:
    def __init__(self):
        self.created_payloads = []
        self.updated_payloads = []
        self.deleted_event_ids = []

    def create_meeting(self, *, topic, start_time, meeting_type, location, max_participants):
        event_id = f"evt_{len(self.created_payloads) + 1}"
        meeting_url = f"https://meetings.test/{event_id}"
        self.created_payloads.append(
            {
                "topic": topic,
                "start_time": start_time,
                "meeting_type": meeting_type,
                "location": location,
                "max_participants": max_participants,
            }
        )
        return MeetingDetails(meeting_url=meeting_url, event_id=event_id)

    def update_meeting(self, *, event_id, start_time):
        self.updated_payloads.append({"event_id": event_id, "start_time": start_time})
        meeting_url = f"https://meetings.test/{event_id}?updated={len(self.updated_payloads)}"
        return MeetingDetails(meeting_url=meeting_url, event_id=event_id)

    def delete_meeting(self, *, event_id):
        self.deleted_event_ids.append(event_id)


@pytest.fixture(autouse=True)
def stub_meeting_provider(monkeypatch):
    stub = StubMeetingProvider()
    monkeypatch.setattr(meetings, "meeting_provider", stub)
    return stub


DEFAULT_PASSWORD = "strongpassword"


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user(
    base_url: str,
    username: str,
    email: str,
    *,
    password: str | None = DEFAULT_PASSWORD,
    password_hash: str | None = None,
    role: str = "client",
    **extra,
) -> int:
    payload = {
        "username": username,
        "email": email,
        "full_name": extra.get("full_name", "Test User"),
        "gender": extra.get("gender", "non-binary"),
        "age": extra.get("age", 30),
        "weight": extra.get("weight", 70.5),
        "height": extra.get("height", 175.0),
        "goal": extra.get("goal", "Maintain weight"),
        "role": role,
    }

    if password_hash is not None:
        payload["password_hash"] = password_hash
    else:
        payload["password"] = password or DEFAULT_PASSWORD

    response = requests.post(f"{base_url}/users", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert "user_id" in data
    return data["user_id"]


def create_subscription(base_url, user_id, plan_name="Premium", monthly_session_quota=3):
    response = requests.post(
        f"{base_url}/subscriptions",
        json={
            "user_id": user_id,
            "plan_name": plan_name,
            "monthly_session_quota": monthly_session_quota,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["subscription_id"]
def create_plan(base_url, name="Starter", price=49.99, **extra):
    payload = {
        "name": name,
        "price": price,
        "billing_interval": extra.get("billing_interval", "monthly"),
        "description": extra.get("description", "Test plan"),
        "allow_one_on_one": extra.get("allow_one_on_one", True),
        "allow_group_sessions": extra.get("allow_group_sessions", False),
        "one_on_one_session_limit": extra.get("one_on_one_session_limit", 2),
        "group_session_limit": extra.get("group_session_limit", 0),
    }
    response = requests.post(f"{base_url}/subscriptions/plans", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["plan_id"]

def login_user(
    base_url: str,
    *,
    username: str | None = None,
    email: str | None = None,
    password: str = DEFAULT_PASSWORD,
) -> dict:
    credentials: dict[str, str] = {"password": password}
    if username:
        credentials["username"] = username
    if email:
        credentials["email"] = email

    response = requests.post(f"{base_url}/auth/login", json=credentials)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    return data


def create_authenticated_user(
    base_url: str,
    username: str,
    email: str,
    *,
    password: str = DEFAULT_PASSWORD,
    role: str = "client",
    **extra,
) -> dict:
    user_id = create_user(
        base_url,
        username,
        email,
        password=password,
        role=role,
        **extra,
    )
    token_data = login_user(base_url, username=username, password=password)
    token = token_data["access_token"]
    return {
        "user_id": user_id,
        "username": username,
        "email": email,
        "password": password,
        "role": role,
        "token": token,
        "headers": auth_headers(token),
    }


@pytest.fixture
def admin_auth(base_url):
    return create_authenticated_user(
        base_url,
        "admin_user",
        "admin@example.com",
        password="adminpass",
        role="admin",
    )


@pytest.fixture
def nutritionist_auth(base_url):
    return create_authenticated_user(
        base_url,
        "nutritionist",
        "nutritionist@example.com",
        password="nutpass",
        role="nutritionist",
    )


def test_index_page_loads(base_url):
    response = requests.get(f"{base_url}/")
    assert response.status_code == 200
    assert "Welcome to the Diet Appointments Dashboard" in response.text


def test_user_creation_and_listing(base_url, admin_auth):
    username = "integration_user"
    email = "integration@example.com"
    create_user(
        base_url,
        username,
        email,
        password="anotherpassword",
        full_name="Integration Tester",
        gender="female",
        age=28,
        weight=62.3,
        height=168.2,
        goal="Build muscle",
    )

    unauthorized = requests.get(f"{base_url}/users")
    assert unauthorized.status_code == 401

    list_response = requests.get(f"{base_url}/users", headers=admin_auth["headers"])
    assert list_response.status_code == 200
    users = list_response.json()
    matching = [u for u in users if u["username"] == username]
    assert matching
    user = matching[0]
    assert user["email"] == email
    assert user["goal"] == "Build muscle"
    assert user["weight"] == 62.3
    assert user["height"] == 168.2
    assert user["role"] == "client"


def test_user_creation_requires_password(base_url):
    response = requests.post(
        f"{base_url}/users",
        json={
            "username": "no_password_user",
            "email": "nopassword@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "Password is required"


def test_user_creation_accepts_prehashed_password(base_url, admin_auth):
    hashed_password = generate_password_hash("already_secure")
    create_user(
        base_url,
        "prehashed",
        "prehashed@example.com",
        password=None,
        password_hash=hashed_password,
    )

    login_data = login_user(base_url, username="prehashed", password="already_secure")
    assert login_data["user"]["role"] == "client"

    users = requests.get(f"{base_url}/users", headers=admin_auth["headers"]).json()
    assert any(u["username"] == "prehashed" for u in users)


def test_login_returns_token_and_role(base_url):
    password = "safepassword"
    create_user(base_url, "login_user", "login@example.com", password=password)

    response = requests.post(
        f"{base_url}/auth/login",
        json={"username": "login_user", "password": password},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "Bearer"
    assert data["user"]["role"] == "client"


def test_diet_plan_creation_and_retrieval(base_url, nutritionist_auth):
    client = create_authenticated_user(
        base_url,
        "dietclient",
        "dietclient@example.com",
        password="clientpass",
    )

    start_date = datetime.utcnow().date()
    end_date = start_date + timedelta(days=30)
    payload = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "meal_details": "High protein diet",
        "preferences_client_notes": "No peanuts",
        "notes": "Follow-up in two weeks",
    }

    unauthorized = requests.post(
        f"{base_url}/users/{client['user_id']}/diet_plans",
        json=payload,
    )
    assert unauthorized.status_code == 401

    response = requests.post(
        f"{base_url}/users/{client['user_id']}/diet_plans",
        json=payload,
        headers=nutritionist_auth["headers"],
    )
    assert response.status_code == 201
    diet_id = response.json()["diet_id"]
    assert diet_id > 0

    unauthorized_get = requests.get(
        f"{base_url}/users/{client['user_id']}/diet_plans",
    )
    assert unauthorized_get.status_code == 401

    list_response = requests.get(
        f"{base_url}/users/{client['user_id']}/diet_plans",
        headers=client["headers"],
    )
    assert list_response.status_code == 200
    diet_plans = list_response.json()
    assert len(diet_plans) == 1
    plan = diet_plans[0]
    assert plan["diet_id"] == diet_id
    assert plan["meal_details"] == "High protein diet"
    assert plan["preferences_client_notes"] == "No peanuts"
    assert plan["start_date"].startswith(start_date.isoformat())
    assert plan["end_date"].startswith(end_date.isoformat())


def test_subscription_plan_listing(base_url):
    plan_id = create_plan(base_url)

    response = requests.get(f"{base_url}/subscriptions/plans")
    assert response.status_code == 200
    plans = response.json()
    assert any(plan["plan_id"] == plan_id for plan in plans)


def test_diet_plan_creation_with_invalid_dates_returns_400(base_url):
    user_id = create_user(base_url, "dietuser2", "diet2@example.com")
def test_diet_plan_creation_with_invalid_dates_returns_400(base_url, nutritionist_auth):
    client = create_authenticated_user(
        base_url,
        "dietuser2",
        "diet2@example.com",
        password="clientpass2",
    )

    response = requests.post(
        f"{base_url}/users/{client['user_id']}/diet_plans",
        json={
            "start_date": "invalid-date",
            "end_date": "also-invalid",
            "meal_details": "Details",
        },
        headers=nutritionist_auth["headers"],
    )
    assert response.status_code == 400
    assert response.json()["error"] == "Invalid date format. Expected YYYY-MM-DD."


def test_client_cannot_create_plan_for_other_user(base_url):
    client = create_authenticated_user(
        base_url,
        "client_a",
        "client_a@example.com",
        password="clientapass",
    )
    other = create_authenticated_user(
        base_url,
        "client_b",
        "client_b@example.com",
        password="clientbpass",
    )

    response = requests.post(
        f"{base_url}/users/{other['user_id']}/diet_plans",
        json={
            "start_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "end_date": (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d"),
            "meal_details": "Sample",
        },
        headers=client["headers"],
    )
    assert response.status_code == 403
    assert response.json()["error"] == "Forbidden"


def test_message_conversation_flow(base_url):
    sender = create_authenticated_user(
        base_url,
        "sender",
        "sender@example.com",
        password="senderpass",
    )
    receiver = create_authenticated_user(
        base_url,
        "receiver",
        "receiver@example.com",
        password="receiverpass",
    )

    first_message = {
        "sender_id": sender["user_id"],
        "receiver_id": receiver["user_id"],
        "message_content": "Hello there!",
    }

    unauthorized = requests.post(f"{base_url}/messages", json=first_message)
    assert unauthorized.status_code == 401

    wrong_user = requests.post(
        f"{base_url}/messages",
        json=first_message,
        headers=receiver["headers"],
    )
    assert wrong_user.status_code == 403

    response = requests.post(
        f"{base_url}/messages",
        json=first_message,
        headers=sender["headers"],
    )
    assert response.status_code == 201

    time.sleep(0.05)

    second_message = {
        "sender_id": receiver["user_id"],
        "receiver_id": sender["user_id"],
        "message_content": "Hi! Great to hear from you.",
    }
    response = requests.post(
        f"{base_url}/messages",
        json=second_message,
        headers=receiver["headers"],
    )
    assert response.status_code == 201

    conversation_url = f"{base_url}/messages/conversation"
    params = {"user1_id": sender["user_id"], "user2_id": receiver["user_id"]}

    unauthorized_get = requests.get(conversation_url, params=params)
    assert unauthorized_get.status_code == 401

    intruder = create_authenticated_user(
        base_url,
        "intruder",
        "intruder@example.com",
        password="intruderpass",
    )
    forbidden = requests.get(conversation_url, params=params, headers=intruder["headers"])
    assert forbidden.status_code == 403

    conversation = requests.get(conversation_url, params=params, headers=sender["headers"])
    assert conversation.status_code == 200
    messages = conversation.json()
    assert [m["message_content"] for m in messages] == [
        "Hello there!",
        "Hi! Great to hear from you.",
    ]
    assert messages[0]["sender_id"] == sender["user_id"]
    assert messages[1]["sender_id"] == receiver["user_id"]


def test_appointment_workflow(base_url, nutritionist_auth):
    client = create_authenticated_user(
        base_url,
        "client",
        "client@example.com",
        password="clientpass",
    )

    scheduled_at = datetime.utcnow().replace(microsecond=0)
    payload = {
        "client_id": client["user_id"],
        "nutritionist_id": nutritionist_auth["user_id"],
        "scheduled_at": scheduled_at.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "confirmed",
        "google_calendar_event_id": "event123",
    }

    unauthorized = requests.post(f"{base_url}/appointments", json=payload)
    assert unauthorized.status_code == 401

    response = requests.post(
        f"{base_url}/appointments",
        json=payload,
        headers=nutritionist_auth["headers"],
    )
    assert response.status_code == 201
    data = response.json()
    appointment_id = data["appointment_id"]
    assert data["meeting_provider_event_id"] == "evt_1"
    assert data["meeting_url"].startswith("https://meetings.test/evt_1")

    detail_unauthorized = requests.get(f"{base_url}/appointments/{appointment_id}")
    assert detail_unauthorized.status_code == 401

    detail_response = requests.get(
        f"{base_url}/appointments/{appointment_id}",
        headers=client["headers"],
    )
    assert detail_response.status_code == 200
    appointment = detail_response.json()
    assert appointment["appointment_id"] == appointment_id
    assert appointment["client_id"] == client["user_id"]
    assert appointment["nutritionist_id"] == nutritionist_auth["user_id"]
    assert appointment["status"] == "confirmed"
    assert appointment["meeting_provider_event_id"] == "evt_1"
    assert appointment["meeting_type"] == "virtual"
    assert appointment["location"] == "Zoom"
    assert appointment["scheduled_at"].startswith(scheduled_at.isoformat())

    list_response = requests.get(
        f"{base_url}/appointments",
        headers=nutritionist_auth["headers"],
    )
    assert list_response.status_code == 200
    appointments = list_response.json()
    assert len(appointments) == 1
    assert appointments[0]["appointment_id"] == appointment_id

    not_found = requests.get(
        f"{base_url}/appointments/{appointment_id + 1}",
        headers=nutritionist_auth["headers"],
    )
    assert not_found.status_code == 404
    assert not_found.json()["message"] == "Appointment not found"

    # Reschedule the appointment
    new_time = scheduled_at + timedelta(hours=1)
    patch_response = requests.patch(
        f"{base_url}/appointments/{appointment_id}",
        json={"scheduled_at": new_time.strftime("%Y-%m-%d %H:%M:%S"), "location": "In person"},
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["meeting_url"].startswith("https://meetings.test/evt_1?updated=1")

    # Cancel the appointment
    cancel_response = requests.delete(f"{base_url}/appointments/{appointment_id}")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["message"] == "Appointment cancelled"

    # Cancelling again is a no-op
    second_cancel = requests.delete(f"{base_url}/appointments/{appointment_id}")
    assert second_cancel.status_code == 200
    assert second_cancel.json()["message"] == "Appointment already cancelled"

    # After cancellation the quota should be freed, allowing another booking
    response = requests.post(
        f"{base_url}/appointments",
        json={
            "client_id": client_id,
            "nutritionist_id": nutritionist_id,
            "scheduled_at": (scheduled_at + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    assert response.status_code == 201


def _webhook_headers(payload: dict[str, object]) -> dict[str, str]:
    from routes import WEBHOOK_SECRET  # Imported lazily to avoid circular imports

    body = json.dumps(payload)
    signature = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-Signature": signature,
    }


def test_subscription_purchase_and_activation_flow(base_url, monkeypatch):
    plan_id = create_plan(base_url, name="Premium", price=79.0)
    user_id = create_user(base_url, "subbuyer", "subbuyer@example.com")

    class DummyClient:
        def __init__(self):
            self.created = []

        def create_checkout_session(self, *, plan, user):  # pragma: no cover - exercised in test
            session_id = "cs_test_checkout"
            self.created.append((plan.plan_id, user.user_id))
            return {
                "id": session_id,
                "url": f"https://example.test/checkout/{session_id}",
            }

        def cancel_subscription(self, *, external_subscription_id):  # pragma: no cover - not used here
            return {"status": "canceled"}

    dummy = DummyClient()
    monkeypatch.setattr("routes.payment_client", dummy)

    purchase = requests.post(
        f"{base_url}/users/{user_id}/subscription",
        json={"plan_id": plan_id},
    )
    assert purchase.status_code == 201, purchase.text
    data = purchase.json()
    assert data["checkout_session_id"] == "cs_test_checkout"
    assert data["subscription"]["status"] == "pending"

    webhook_payload = {
        "type": "checkout.session.completed",
        "data": {
            "checkout_session_id": "cs_test_checkout",
            "external_subscription_id": "sub_123",
            "external_customer_id": "cus_123",
            "renewal_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        },
    }

    webhook_response = requests.post(
        f"{base_url}/webhooks/payments",
        data=json.dumps(webhook_payload),
        headers=_webhook_headers(webhook_payload),
    )
    assert webhook_response.status_code == 200, webhook_response.text

    subscription_details = requests.get(f"{base_url}/users/{user_id}/subscription")
    assert subscription_details.status_code == 200
    payload = subscription_details.json()
    assert payload["sub_status"] is True
    assert payload["subscription"]["status"] == "active"
    assert payload["subscription"]["external_subscription_id"] == "sub_123"


def test_subscription_cancellation_flow(base_url, monkeypatch):
    plan_id = create_plan(base_url, name="CancelPlan")
    user_id = create_user(base_url, "canceluser", "cancel@example.com")

    class CancelClient:
        def __init__(self):
            self.cancelled = []

        def create_checkout_session(self, *, plan, user):  # pragma: no cover - exercised in test
            return {
                "id": "cs_cancel",
                "url": "https://example.test/checkout/cs_cancel",
            }

        def cancel_subscription(self, *, external_subscription_id):
            self.cancelled.append(external_subscription_id)
            return {"status": "canceled"}

    client = CancelClient()
    monkeypatch.setattr("routes.payment_client", client)

    purchase = requests.post(
        f"{base_url}/users/{user_id}/subscription",
        json={"plan_id": plan_id},
    )
    assert purchase.status_code == 201

    # Activate via webhook to set external IDs
    webhook_payload = {
        "type": "checkout.session.completed",
        "data": {
            "checkout_session_id": "cs_cancel",
            "external_subscription_id": "sub_cancel",
            "external_customer_id": "cus_cancel",
            "renewal_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        },
    }
    requests.post(
        f"{base_url}/webhooks/payments",
        data=json.dumps(webhook_payload),
        headers=_webhook_headers(webhook_payload),
    )

    cancel_response = requests.delete(f"{base_url}/users/{user_id}/subscription")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["message"] == "Subscription canceled"
    assert client.cancelled == ["sub_cancel"]

    details = requests.get(f"{base_url}/users/{user_id}/subscription").json()
    assert details["sub_status"] is False
    assert details["subscription"]["status"] == "canceled"


def test_webhook_signature_verification(base_url):
    payload = {
        "type": "checkout.session.completed",
        "data": {
            "checkout_session_id": "does-not-exist",
        },
    }
    response = requests.post(
        f"{base_url}/webhooks/payments",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json", "X-Signature": "invalid"},
    )
    assert response.status_code == 400
    assert response.json()["error"] == "Invalid signature"


def test_create_appointment_with_invalid_datetime_returns_400(base_url):
    client_id = create_user(base_url, "apptclient", "apptclient@example.com")
    nutritionist_id = create_user(base_url, "apptnut", "apptnut@example.com")
def test_create_appointment_with_invalid_datetime_returns_400(base_url, nutritionist_auth):
    client = create_authenticated_user(
        base_url,
        "apptclient",
        "apptclient@example.com",
        password="apptclientpass",
    )

    response = requests.post(
        f"{base_url}/appointments",
        json={
            "client_id": client["user_id"],
            "nutritionist_id": nutritionist_auth["user_id"],
            "scheduled_at": "invalid",
        },
        headers=nutritionist_auth["headers"],
    )
    assert response.status_code == 400
    assert response.json()["error"] == "Invalid datetime format. Expected YYYY-MM-DD HH:MM:SS."


def test_appointment_creation_respects_subscription_quota(base_url):
    client_id = create_user(base_url, "quota", "quota@example.com")
    nutritionist_id = create_user(base_url, "coach", "coach@example.com")
    create_subscription(base_url, client_id, monthly_session_quota=1)

    scheduled_at = datetime.utcnow().replace(microsecond=0)
    first = requests.post(
        f"{base_url}/appointments",
        json={
            "client_id": client_id,
            "nutritionist_id": nutritionist_id,
            "scheduled_at": scheduled_at.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    assert first.status_code == 201

    second = requests.post(
        f"{base_url}/appointments",
        json={
            "client_id": client_id,
            "nutritionist_id": nutritionist_id,
            "scheduled_at": (scheduled_at + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    assert second.status_code == 409
    assert second.json()["error"] == "Monthly session quota exceeded"


def test_group_session_join_and_withdraw_flow(base_url):
    client_id = create_user(base_url, "groupie", "groupie@example.com")
    coach_id = create_user(base_url, "coachgs", "coachgs@example.com")
    create_subscription(base_url, client_id, monthly_session_quota=2)

    start_time = datetime.utcnow().replace(microsecond=0)
    response = requests.post(
        f"{base_url}/group_sessions",
        json={
            "nutritionist_id": coach_id,
            "topic": "Weekly Group Session",
            "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "max_participants": 5,
        },
    )
    assert response.status_code == 201
    group_session_id = response.json()["group_session_id"]

    join_response = requests.post(
        f"{base_url}/group_sessions/{group_session_id}/join",
        json={"client_id": client_id},
    )
    assert join_response.status_code == 201
    join_data = join_response.json()
    appointment_id = join_data["appointment_id"]

    # Joining again is a no-op but succeeds
    repeat_join = requests.post(
        f"{base_url}/group_sessions/{group_session_id}/join",
        json={"client_id": client_id},
    )
    assert repeat_join.status_code == 200
    assert repeat_join.json()["message"] == "Already joined"

    withdraw = requests.delete(
        f"{base_url}/group_sessions/{group_session_id}/withdraw",
        json={"client_id": client_id},
    )
    assert withdraw.status_code == 200
    assert withdraw.json()["message"] == "Withdrawn from group session"

    # After withdrawing the user can join again
    rejoin = requests.post(
        f"{base_url}/group_sessions/{group_session_id}/join",
        json={"client_id": client_id},
    )
    assert rejoin.status_code == 201
    assert rejoin.json()["appointment_id"] != appointment_id


def test_group_session_enforces_capacity_and_quota(base_url):
    first_client = create_user(base_url, "first", "first@example.com")
    second_client = create_user(base_url, "second", "second@example.com")
    coach_id = create_user(base_url, "coachcap", "coachcap@example.com")
    create_subscription(base_url, first_client, monthly_session_quota=1)
    create_subscription(base_url, second_client, monthly_session_quota=1)

    start_time = datetime.utcnow().replace(microsecond=0)
    response = requests.post(
        f"{base_url}/group_sessions",
        json={
            "nutritionist_id": coach_id,
            "topic": "Limited Group",
            "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "max_participants": 1,
        },
    )
    assert response.status_code == 201
    group_session_id = response.json()["group_session_id"]

    join_first = requests.post(
        f"{base_url}/group_sessions/{group_session_id}/join",
        json={"client_id": first_client},
    )
    assert join_first.status_code == 201

    join_second = requests.post(
        f"{base_url}/group_sessions/{group_session_id}/join",
        json={"client_id": second_client},
    )
    assert join_second.status_code == 409
    assert join_second.json()["error"] == "Group session is full"

    # First client has reached the quota; trying to join a second session fails
    response = requests.post(
        f"{base_url}/group_sessions/{group_session_id}/join",
        json={"client_id": first_client},
    )
    assert response.status_code == 200  # already joined

    # Attempt to join another group session should fail due to quota
    response = requests.post(
        f"{base_url}/group_sessions",
        json={
            "nutritionist_id": coach_id,
            "topic": "Another Group",
            "start_time": (start_time + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"),
        },
    )
    assert response.status_code == 201
    second_session_id = response.json()["group_session_id"]
    join_again = requests.post(
        f"{base_url}/group_sessions/{second_session_id}/join",
        json={"client_id": first_client},
    )
    assert join_again.status_code == 409
    assert join_again.json()["error"] == "Monthly session quota exceeded"
