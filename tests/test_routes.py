import time
from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

try:  # pragma: no cover - exercised when requests is available
    import requests  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - offline fallback
    from . import _requests_stub as requests


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
    appointment_id = response.json()["appointment_id"]

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
    assert appointment["google_calendar_event_id"] == "event123"
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
