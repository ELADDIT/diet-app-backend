import json
import hmac
import hashlib
import time
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

try:  # pragma: no cover - exercised when requests is available
    import requests  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - offline fallback
    from . import _requests_stub as requests


def create_user(base_url, username, email, **extra):
    payload = {
        "username": username,
        "email": email,
        "password": "strongpassword",
        "full_name": extra.get("full_name", "Test User"),
        "gender": extra.get("gender", "non-binary"),
        "age": extra.get("age", 30),
        "weight": extra.get("weight", 70.5),
        "height": extra.get("height", 175.0),
        "goal": extra.get("goal", "Maintain weight"),
    }
    response = requests.post(f"{base_url}/users", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()
    assert "user_id" in data
    return data["user_id"]


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


def test_index_page_loads(base_url):
    response = requests.get(f"{base_url}/")
    assert response.status_code == 200
    assert "Welcome to the Diet Appointments Dashboard" in response.text


def test_user_creation_and_listing(base_url):
    username = "integration_user"
    email = "integration@example.com"
    response = requests.post(
        f"{base_url}/users",
        json={
            "username": username,
            "email": email,
            "password": "anotherpassword",
            "full_name": "Integration Tester",
            "gender": "female",
            "age": 28,
            "weight": 62.3,
            "height": 168.2,
            "goal": "Build muscle",
            "neck_circumference": 34.1,
            "abdomen_circumference": 72.4,
            "hip_circumference": 95.0,
            "underlying_medical_conditions": "None",
        },
    )
    assert response.status_code == 201
    user_id = response.json()["user_id"]
    assert user_id > 0

    list_response = requests.get(f"{base_url}/users")
    assert list_response.status_code == 200
    users = list_response.json()
    assert len(users) == 1
    user = users[0]
    assert user["username"] == username
    assert user["email"] == email
    assert user["goal"] == "Build muscle"
    assert user["weight"] == 62.3
    assert user["height"] == 168.2


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


def test_user_creation_accepts_prehashed_password(base_url):
    hashed_password = generate_password_hash("already_secure")
    response = requests.post(
        f"{base_url}/users",
        json={
            "username": "prehashed",
            "email": "prehashed@example.com",
            "password_hash": hashed_password,
        },
    )
    assert response.status_code == 201

    users = requests.get(f"{base_url}/users").json()
    assert users[0]["username"] == "prehashed"


def test_diet_plan_creation_and_retrieval(base_url):
    user_id = create_user(base_url, "dietuser", "diet@example.com")

    start_date = datetime.utcnow().date()
    end_date = start_date + timedelta(days=30)
    response = requests.post(
        f"{base_url}/users/{user_id}/diet_plans",
        json={
            "nutritionist_id": 42,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "meal_details": "High protein diet",
            "preferences_client_notes": "No peanuts",
            "notes": "Follow-up in two weeks",
        },
    )
    assert response.status_code == 201
    diet_id = response.json()["diet_id"]
    assert diet_id > 0

    list_response = requests.get(f"{base_url}/users/{user_id}/diet_plans")
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
    response = requests.post(
        f"{base_url}/users/{user_id}/diet_plans",
        json={
            "nutritionist_id": 99,
            "start_date": "invalid-date",
            "end_date": "also-invalid",
            "meal_details": "Details",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "Invalid date format. Expected YYYY-MM-DD."


def test_message_conversation_flow(base_url):
    sender_id = create_user(base_url, "sender", "sender@example.com")
    receiver_id = create_user(base_url, "receiver", "receiver@example.com")

    first_message = {
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "message_content": "Hello there!",
    }
    response = requests.post(f"{base_url}/messages", json=first_message)
    assert response.status_code == 201

    time.sleep(0.05)

    second_message = {
        "sender_id": receiver_id,
        "receiver_id": sender_id,
        "message_content": "Hi! Great to hear from you.",
    }
    response = requests.post(f"{base_url}/messages", json=second_message)
    assert response.status_code == 201

    conversation = requests.get(
        f"{base_url}/messages/conversation",
        params={"user1_id": sender_id, "user2_id": receiver_id},
    )
    assert conversation.status_code == 200
    messages = conversation.json()
    assert [m["message_content"] for m in messages] == [
        "Hello there!",
        "Hi! Great to hear from you.",
    ]
    assert messages[0]["sender_id"] == sender_id
    assert messages[1]["sender_id"] == receiver_id


def test_appointment_workflow(base_url):
    client_id = create_user(base_url, "client", "client@example.com")
    nutritionist_id = create_user(base_url, "nutritionist", "nutritionist@example.com")

    scheduled_at = datetime.utcnow().replace(microsecond=0)
    response = requests.post(
        f"{base_url}/appointments",
        json={
            "client_id": client_id,
            "nutritionist_id": nutritionist_id,
            "scheduled_at": scheduled_at.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "confirmed",
            "google_calendar_event_id": "event123",
        },
    )
    assert response.status_code == 201
    appointment_id = response.json()["appointment_id"]

    detail_response = requests.get(f"{base_url}/appointments/{appointment_id}")
    assert detail_response.status_code == 200
    appointment = detail_response.json()
    assert appointment["appointment_id"] == appointment_id
    assert appointment["client_id"] == client_id
    assert appointment["nutritionist_id"] == nutritionist_id
    assert appointment["status"] == "confirmed"
    assert appointment["google_calendar_event_id"] == "event123"
    assert appointment["scheduled_at"].startswith(scheduled_at.isoformat())

    list_response = requests.get(f"{base_url}/appointments")
    assert list_response.status_code == 200
    appointments = list_response.json()
    assert len(appointments) == 1
    assert appointments[0]["appointment_id"] == appointment_id

    not_found = requests.get(f"{base_url}/appointments/{appointment_id + 1}")
    assert not_found.status_code == 404
    assert not_found.json()["message"] == "Appointment not found"


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
    response = requests.post(
        f"{base_url}/appointments",
        json={
            "client_id": client_id,
            "nutritionist_id": nutritionist_id,
            "scheduled_at": "invalid",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "Invalid datetime format. Expected YYYY-MM-DD HH:MM:SS."
