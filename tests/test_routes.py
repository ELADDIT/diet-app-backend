import time
from datetime import datetime, timedelta

import pytest
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


def test_progress_entry_creation_and_history(base_url):
    user_id = create_user(base_url, "progressuser", "progress@example.com")

    recorded_at = datetime.utcnow().replace(microsecond=0)
    payload = {
        "recorded_at": recorded_at.isoformat(),
        "weight": 180,
        "weight_unit": "lb",
        "neck_circumference": 16,
        "circumference_unit": "in",
        "body_fat_percentage": 18.5,
        "notes": "Felt energized",
    }

    response = requests.post(f"{base_url}/users/{user_id}/progress", json=payload)
    assert response.status_code == 201
    created = response.json()["progress"]
    assert created["progress_id"] > 0
    assert created["units"] == {"weight": "kg", "circumference": "cm"}
    assert created["recorded_at"].startswith(recorded_at.isoformat())
    assert created["weight"] == pytest.approx(81.6466, rel=1e-3)
    assert created["neck_circumference"] == pytest.approx(40.64, rel=1e-3)
    assert created["body_fat_percentage"] == pytest.approx(18.5)

    history_response = requests.get(f"{base_url}/users/{user_id}/progress")
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) == 1
    history_entry = history[0]
    assert history_entry["progress_id"] == created["progress_id"]
    assert history_entry["units"] == {"weight": "kg", "circumference": "cm"}
    assert history_entry["weight"] == pytest.approx(created["weight"], rel=1e-9)


def test_progress_entry_rejects_invalid_units(base_url):
    user_id = create_user(base_url, "invalidunits", "invalidunits@example.com")

    response = requests.post(
        f"{base_url}/users/{user_id}/progress",
        json={
            "weight": 70,
            "weight_unit": "stone",
        },
    )
    assert response.status_code == 400
    assert "Invalid weight_unit" in response.json()["error"]


def test_workout_plan_creation_and_update(base_url):
    user_id = create_user(base_url, "workoutuser", "workout@example.com")

    start_date = datetime.utcnow().date()
    end_date = start_date + timedelta(days=14)
    response = requests.post(
        f"{base_url}/users/{user_id}/workout_plans",
        json={
            "trainer_id": 7,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "workout_details": "Strength training 3x per week",
            "notes": "Focus on recovery",
        },
    )
    assert response.status_code == 201
    created_plan = response.json()["workout_plan"]
    workout_id = created_plan["workout_id"]

    list_response = requests.get(f"{base_url}/users/{user_id}/workout_plans")
    assert list_response.status_code == 200
    plans = list_response.json()
    assert len(plans) == 1
    assert plans[0]["workout_id"] == workout_id

    updated_end = end_date + timedelta(days=7)
    patch_response = requests.patch(
        f"{base_url}/users/{user_id}/workout_plans",
        json={
            "workout_id": workout_id,
            "end_date": updated_end.isoformat(),
            "notes": "Add light cardio warm-ups",
        },
    )
    assert patch_response.status_code == 200
    updated_plan = patch_response.json()["workout_plan"]
    assert updated_plan["notes"] == "Add light cardio warm-ups"
    assert updated_plan["end_date"].startswith(updated_end.isoformat())

    refreshed_list = requests.get(f"{base_url}/users/{user_id}/workout_plans")
    assert refreshed_list.status_code == 200
    refreshed_plan = refreshed_list.json()[0]
    assert refreshed_plan["notes"] == "Add light cardio warm-ups"


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
