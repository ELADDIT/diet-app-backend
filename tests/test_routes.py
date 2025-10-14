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
    create_subscription(base_url, client_id, monthly_session_quota=2)

    scheduled_at = datetime.utcnow().replace(microsecond=0)
    response = requests.post(
        f"{base_url}/appointments",
        json={
            "client_id": client_id,
            "nutritionist_id": nutritionist_id,
            "scheduled_at": scheduled_at.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "confirmed",
            "meeting_type": "virtual",
            "location": "Zoom",
        },
    )
    assert response.status_code == 201
    data = response.json()
    appointment_id = data["appointment_id"]
    assert data["meeting_provider_event_id"] == "evt_1"
    assert data["meeting_url"].startswith("https://meetings.test/evt_1")

    detail_response = requests.get(f"{base_url}/appointments/{appointment_id}")
    assert detail_response.status_code == 200
    appointment = detail_response.json()
    assert appointment["appointment_id"] == appointment_id
    assert appointment["client_id"] == client_id
    assert appointment["nutritionist_id"] == nutritionist_id
    assert appointment["status"] == "confirmed"
    assert appointment["meeting_provider_event_id"] == "evt_1"
    assert appointment["meeting_type"] == "virtual"
    assert appointment["location"] == "Zoom"
    assert appointment["scheduled_at"].startswith(scheduled_at.isoformat())

    list_response = requests.get(f"{base_url}/appointments")
    assert list_response.status_code == 200
    appointments = list_response.json()
    assert len(appointments) == 1
    assert appointments[0]["appointment_id"] == appointment_id

    not_found = requests.get(f"{base_url}/appointments/{appointment_id + 1}")
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


def test_create_appointment_with_invalid_datetime_returns_400(base_url):
    client_id = create_user(base_url, "apptclient", "apptclient@example.com")
    nutritionist_id = create_user(base_url, "apptnut", "apptnut@example.com")
    create_subscription(base_url, client_id)
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
