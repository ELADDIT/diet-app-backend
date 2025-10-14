from flask import Blueprint, request, jsonify, render_template
from datetime import datetime
from typing import Dict, Optional, Tuple
from werkzeug.security import generate_password_hash
from database import SessionLocal
from models import User, UserProgress, DietPlan, WorkoutPlan, Message, Appointment


def _iso_datetime(value, field_name, *, default: Optional[datetime] = None) -> Optional[datetime]:
    """Parse an ISO 8601 datetime (or date) value from the request payload."""
    if value is None:
        return default
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            trimmed = value.strip()
            if len(trimmed) == 10:
                return datetime.strptime(trimmed, "%Y-%m-%d")
            return datetime.fromisoformat(trimmed)
        except ValueError as exc:  # pragma: no cover - defensive: ValueError path tested via API
            raise ValueError(
                f"Invalid date format for {field_name}. Expected ISO 8601 string."
            ) from exc
    raise ValueError(f"Invalid type for {field_name}. Expected ISO 8601 string.")


def _decimal_to_float(value):
    return float(value) if value is not None else None


DEFAULT_PROGRESS_UNITS = {"weight": "kg", "circumference": "cm"}
WEIGHT_CONVERSIONS = {"kg": 1.0, "lb": 0.45359237}
CIRCUMFERENCE_CONVERSIONS = {"cm": 1.0, "in": 2.54}


def _normalize_unit(unit, measurement_name, conversions, default_unit):
    if unit is None:
        return default_unit
    if not isinstance(unit, str):
        raise ValueError(f"Invalid {measurement_name}_unit '{unit}'. Allowed units: {', '.join(sorted(conversions))}.")
    normalized = unit.lower()
    if normalized not in conversions:
        allowed = ", ".join(sorted(conversions))
        raise ValueError(f"Invalid {measurement_name}_unit '{unit}'. Allowed units: {allowed}.")
    return normalized


def _convert_measurement(value, unit, conversions, field_name):
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        readable = field_name.replace("_", " ").capitalize()
        raise ValueError(f"{readable} must be a number.") from exc
    return numeric * conversions[unit]


def _parse_optional_float(value, field_name):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        readable = field_name.replace("_", " ").capitalize()
        raise ValueError(f"{readable} must be a number.") from exc


def _serialize_progress(progress: UserProgress, units: Optional[Dict[str, str]] = None) -> Dict:
    payload = {
        "progress_id": progress.progress_id,
        "user_id": progress.user_id,
        "recorded_at": progress.recorded_at.isoformat() if progress.recorded_at else None,
        "weight": _decimal_to_float(progress.weight),
        "bmi": _decimal_to_float(progress.bmi),
        "body_fat_percentage": _decimal_to_float(progress.body_fat_percentage),
        "neck_circumference": _decimal_to_float(progress.neck_circumference),
        "abdomen_circumference": _decimal_to_float(progress.abdomen_circumference),
        "hip_circumference": _decimal_to_float(progress.hip_circumference),
        "notes": progress.notes,
    }
    payload["units"] = units or DEFAULT_PROGRESS_UNITS.copy()
    return payload


def _serialize_workout_plan(plan: WorkoutPlan) -> Dict:
    return {
        "workout_id": plan.workout_id,
        "user_id": plan.user_id,
        "trainer_id": plan.trainer_id,
        "start_date": plan.start_date.isoformat() if plan.start_date else None,
        "end_date": plan.end_date.isoformat() if plan.end_date else None,
        "workout_details": plan.workout_details,
        "notes": plan.notes,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }


def _error_response(message, status_code=400):
    return jsonify({"error": message}), status_code


def _progress_creation_fields(data: Dict) -> Tuple[Dict, Dict[str, str]]:
    if not isinstance(data, dict):
        raise ValueError("Invalid JSON payload.")

    fields: Dict = {}
    recorded_at = _iso_datetime(data.get("recorded_at"), "recorded_at", default=datetime.utcnow())
    fields["recorded_at"] = recorded_at

    weight_unit = _normalize_unit(
        data.get("weight_unit"),
        "weight",
        WEIGHT_CONVERSIONS,
        DEFAULT_PROGRESS_UNITS["weight"],
    )
    weight_value = _convert_measurement(
        data.get("weight"), weight_unit, WEIGHT_CONVERSIONS, "weight"
    )
    if weight_value is not None:
        fields["weight"] = weight_value

    bmi_value = _parse_optional_float(data.get("bmi"), "bmi")
    if bmi_value is not None:
        fields["bmi"] = bmi_value

    body_fat_value = _parse_optional_float(
        data.get("body_fat_percentage"), "body_fat_percentage"
    )
    if body_fat_value is not None:
        if not 0 <= body_fat_value <= 100:
            raise ValueError("body_fat_percentage must be between 0 and 100.")
        fields["body_fat_percentage"] = body_fat_value

    circumference_unit = _normalize_unit(
        data.get("circumference_unit"),
        "circumference",
        CIRCUMFERENCE_CONVERSIONS,
        DEFAULT_PROGRESS_UNITS["circumference"],
    )
    for field in ("neck_circumference", "abdomen_circumference", "hip_circumference"):
        value = data.get(field)
        if value is not None:
            fields[field] = _convert_measurement(
                value, circumference_unit, CIRCUMFERENCE_CONVERSIONS, field
            )

    if "notes" in data:
        fields["notes"] = data.get("notes")

    units = DEFAULT_PROGRESS_UNITS.copy()
    return fields, units


def _apply_progress_update(progress: UserProgress, data: Dict) -> Dict[str, str]:
    if not isinstance(data, dict):
        raise ValueError("Invalid JSON payload.")

    units = DEFAULT_PROGRESS_UNITS.copy()

    if "recorded_at" in data:
        progress.recorded_at = _iso_datetime(data.get("recorded_at"), "recorded_at")

    if "notes" in data:
        progress.notes = data.get("notes")

    if "bmi" in data:
        progress.bmi = _parse_optional_float(data.get("bmi"), "bmi")

    if "body_fat_percentage" in data:
        body_fat_value = _parse_optional_float(
            data.get("body_fat_percentage"), "body_fat_percentage"
        )
        if body_fat_value is not None and not 0 <= body_fat_value <= 100:
            raise ValueError("body_fat_percentage must be between 0 and 100.")
        progress.body_fat_percentage = body_fat_value

    if "weight" in data or "weight_unit" in data:
        if "weight" not in data:
            raise ValueError("weight must be provided when specifying weight_unit.")
        weight_unit = _normalize_unit(
            data.get("weight_unit"),
            "weight",
            WEIGHT_CONVERSIONS,
            DEFAULT_PROGRESS_UNITS["weight"],
        )
        progress.weight = _convert_measurement(
            data.get("weight"), weight_unit, WEIGHT_CONVERSIONS, "weight"
        )

    circumference_fields = [
        field
        for field in ("neck_circumference", "abdomen_circumference", "hip_circumference")
        if field in data
    ]
    if "circumference_unit" in data and not circumference_fields:
        _normalize_unit(
            data.get("circumference_unit"),
            "circumference",
            CIRCUMFERENCE_CONVERSIONS,
            DEFAULT_PROGRESS_UNITS["circumference"],
        )
    if circumference_fields:
        circumference_unit = _normalize_unit(
            data.get("circumference_unit"),
            "circumference",
            CIRCUMFERENCE_CONVERSIONS,
            DEFAULT_PROGRESS_UNITS["circumference"],
        )
        for field in circumference_fields:
            setattr(
                progress,
                field,
                _convert_measurement(
                    data.get(field), circumference_unit, CIRCUMFERENCE_CONVERSIONS, field
                ),
            )

    return units


def _workout_fields_from_payload(
    data: Dict, *, partial: bool = False, existing_plan: Optional[WorkoutPlan] = None
) -> Dict:
    if not isinstance(data, dict):
        raise ValueError("Invalid JSON payload.")

    fields: Dict = {}
    start_reference = existing_plan.start_date if existing_plan else None
    end_reference = existing_plan.end_date if existing_plan else None

    if partial:
        if "start_date" in data:
            start_reference = _iso_datetime(data.get("start_date"), "start_date")
            fields["start_date"] = start_reference
        if "end_date" in data:
            end_reference = _iso_datetime(data.get("end_date"), "end_date")
            fields["end_date"] = end_reference
    else:
        start_reference = _iso_datetime(data.get("start_date"), "start_date")
        end_reference = _iso_datetime(data.get("end_date"), "end_date")
        if start_reference is None or end_reference is None:
            raise ValueError("start_date and end_date are required.")
        fields["start_date"] = start_reference
        fields["end_date"] = end_reference

    if start_reference and end_reference and end_reference < start_reference:
        raise ValueError("end_date cannot be earlier than start_date.")

    if not partial:
        details = data.get("workout_details")
        if not details:
            raise ValueError("workout_details is required.")
        fields["workout_details"] = details
    elif "workout_details" in data:
        details = data.get("workout_details")
        if details is None or details == "":
            raise ValueError("workout_details cannot be empty.")
        fields["workout_details"] = details

    if "trainer_id" in data:
        fields["trainer_id"] = data.get("trainer_id")

    if "notes" in data:
        fields["notes"] = data.get("notes")

    return fields

bp = Blueprint('api', __name__)

# --------------------------------
# Simple Frontend
# --------------------------------
@bp.route('/')
def index():
    return render_template('index.html')

# --------------------------------
# Users Endpoints
# --------------------------------
@bp.route('/users', methods=['GET'])
def get_users():
    session = SessionLocal()
    users = session.query(User).all()
    result = []
    for user in users:
        result.append({
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "gender": user.gender,
            "age": user.age,
            "weight": float(user.weight) if user.weight else None,
            "height": float(user.height) if user.height else None,
            "goal": user.goal
        })
    session.close()
    return jsonify(result)

@bp.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    session = SessionLocal()

    # Support clients sending either a plain password or a precomputed hash
    raw_password = data.get('password')
    password_hash = data.get('password_hash')
    if raw_password is not None:
        password_hash = generate_password_hash(raw_password)
    if password_hash is None:
        session.close()
        return jsonify({"error": "Password is required"}), 400

    new_user = User(
        username=data['username'],
        email=data['email'],
        password_hash=password_hash,
        full_name=data.get('full_name'),
        gender=data.get('gender'),
        age=data.get('age'),
        weight=data.get('weight'),
        height=data.get('height'),
        goal=data.get('goal'),
        neck_circumference=data.get('neck_circumference'),
        abdomen_circumference=data.get('abdomen_circumference'),
        hip_circumference=data.get('hip_circumference'),
        underlying_medical_conditions=data.get('underlying_medical_conditions')
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    session.close()
    return jsonify({"message": "User created successfully", "user_id": new_user.user_id}), 201

# --------------------------------
# Diet Plans Endpoints
# --------------------------------
@bp.route('/users/<int:user_id>/diet_plans', methods=['GET'])
def get_diet_plans(user_id):
    session = SessionLocal()
    diet_plans = session.query(DietPlan).filter(DietPlan.user_id == user_id).all()
    result = []
    for plan in diet_plans:
        result.append({
            "diet_id": plan.diet_id,
            "start_date": plan.start_date.isoformat() if plan.start_date else None,
            "end_date": plan.end_date.isoformat() if plan.end_date else None,
            "meal_details": plan.meal_details,
            "preferences_client_notes": plan.preferences_client_notes,
            "notes": plan.notes
        })
    session.close()
    return jsonify(result)

@bp.route('/users/<int:user_id>/diet_plans', methods=['POST'])
def create_diet_plan(user_id):
    data = request.get_json()
    session = SessionLocal()
    try:
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "Invalid date format. Expected YYYY-MM-DD."}), 400

        new_diet_plan = DietPlan(
            user_id=user_id,
            nutritionist_id=data.get('nutritionist_id'),
            start_date=start_date,
            end_date=end_date,
            meal_details=data['meal_details'],
            preferences_client_notes=data.get('preferences_client_notes'),
            notes=data.get('notes')
        )
        session.add(new_diet_plan)
        session.commit()
        session.refresh(new_diet_plan)
        return jsonify({"message": "Diet plan created successfully", "diet_id": new_diet_plan.diet_id}), 201
    finally:
        session.close()

# --------------------------------
# User Progress Endpoints
# --------------------------------
@bp.route('/users/<int:user_id>/progress', methods=['GET', 'POST', 'PATCH'])
def manage_user_progress(user_id):
    session = SessionLocal()
    try:
        if request.method == 'GET':
            entries = (
                session.query(UserProgress)
                .filter(UserProgress.user_id == user_id)
                .order_by(UserProgress.recorded_at.asc(), UserProgress.progress_id.asc())
                .all()
            )
            return jsonify([_serialize_progress(entry) for entry in entries])

        data = request.get_json() or {}
        if not isinstance(data, dict):
            return _error_response("Invalid JSON payload.")

        if request.method == 'POST':
            try:
                fields, units = _progress_creation_fields(data)
            except ValueError as exc:
                session.rollback()
                return _error_response(str(exc))

            new_progress = UserProgress(user_id=user_id, **fields)
            session.add(new_progress)
            session.commit()
            session.refresh(new_progress)
            return (
                jsonify(
                    {
                        "message": "Progress entry recorded successfully",
                        "progress": _serialize_progress(new_progress, units),
                    }
                ),
                201,
            )

        progress_id = data.get('progress_id')
        if not progress_id:
            return _error_response("progress_id is required for updates.")

        progress = (
            session.query(UserProgress)
            .filter(
                UserProgress.user_id == user_id,
                UserProgress.progress_id == progress_id,
            )
            .first()
        )
        if not progress:
            return _error_response("Progress entry not found", status_code=404)

        try:
            units = _apply_progress_update(progress, data)
        except ValueError as exc:
            session.rollback()
            return _error_response(str(exc))

        session.commit()
        session.refresh(progress)
        return (
            jsonify(
                {
                    "message": "Progress entry updated successfully",
                    "progress": _serialize_progress(progress, units),
                }
            ),
            200,
        )
    finally:
        session.close()

# --------------------------------
# Workout Plan Endpoints
# --------------------------------
@bp.route('/users/<int:user_id>/workout_plans', methods=['GET', 'POST', 'PATCH'])
def manage_workout_plans(user_id):
    session = SessionLocal()
    try:
        if request.method == 'GET':
            plans = (
                session.query(WorkoutPlan)
                .filter(WorkoutPlan.user_id == user_id)
                .order_by(WorkoutPlan.start_date.asc(), WorkoutPlan.workout_id.asc())
                .all()
            )
            return jsonify([_serialize_workout_plan(plan) for plan in plans])

        data = request.get_json() or {}
        if not isinstance(data, dict):
            return _error_response("Invalid JSON payload.")

        if request.method == 'POST':
            try:
                fields = _workout_fields_from_payload(data)
            except ValueError as exc:
                session.rollback()
                return _error_response(str(exc))

            workout_plan = WorkoutPlan(user_id=user_id, **fields)
            session.add(workout_plan)
            session.commit()
            session.refresh(workout_plan)
            return (
                jsonify(
                    {
                        "message": "Workout plan created successfully",
                        "workout_plan": _serialize_workout_plan(workout_plan),
                    }
                ),
                201,
            )

        workout_id = data.get('workout_id')
        if not workout_id:
            return _error_response("workout_id is required for updates.")

        plan = (
            session.query(WorkoutPlan)
            .filter(
                WorkoutPlan.user_id == user_id,
                WorkoutPlan.workout_id == workout_id,
            )
            .first()
        )
        if not plan:
            return _error_response("Workout plan not found", status_code=404)

        try:
            updates = _workout_fields_from_payload(data, partial=True, existing_plan=plan)
        except ValueError as exc:
            session.rollback()
            return _error_response(str(exc))

        for key, value in updates.items():
            setattr(plan, key, value)

        session.commit()
        session.refresh(plan)
        return (
            jsonify(
                {
                    "message": "Workout plan updated successfully",
                    "workout_plan": _serialize_workout_plan(plan),
                }
            ),
            200,
        )
    finally:
        session.close()

# --------------------------------
# Messages Endpoints
# --------------------------------
@bp.route('/messages', methods=['POST'])
def send_message():
    data = request.get_json()
    session = SessionLocal()
    new_message = Message(
        sender_id=data['sender_id'],
        receiver_id=data['receiver_id'],
        message_content=data['message_content']
    )
    session.add(new_message)
    session.commit()
    session.refresh(new_message)
    session.close()
    return jsonify({"message": "Message sent successfully", "message_id": new_message.message_id}), 201

@bp.route('/messages/conversation', methods=['GET'])
def get_conversation():
    user1_id = request.args.get('user1_id', type=int)
    user2_id = request.args.get('user2_id', type=int)
    session = SessionLocal()
    messages = session.query(Message).filter(
        ((Message.sender_id == user1_id) & (Message.receiver_id == user2_id)) |
        ((Message.sender_id == user2_id) & (Message.receiver_id == user1_id))
    ).order_by(Message.sent_at).all()
    result = []
    for msg in messages:
        result.append({
            "message_id": msg.message_id,
            "sender_id": msg.sender_id,
            "receiver_id": msg.receiver_id,
            "sent_at": msg.sent_at.isoformat(),
            "message_content": msg.message_content,
            "is_read": msg.is_read
        })
    session.close()
    return jsonify(result)

# --------------------------------
# Appointments Endpoints
# --------------------------------
@bp.route('/appointments', methods=['POST'])
def create_appointment():
    data = request.get_json()
    session = SessionLocal()
    try:
        try:
            scheduled_at = datetime.strptime(data['scheduled_at'], '%Y-%m-%d %H:%M:%S')
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "Invalid datetime format. Expected YYYY-MM-DD HH:MM:SS."}), 400

        new_appointment = Appointment(
            client_id=data['client_id'],
            nutritionist_id=data['nutritionist_id'],
            scheduled_at=scheduled_at,
            status=data.get('status', 'scheduled'),
            google_calendar_event_id=data.get('google_calendar_event_id')
        )
        session.add(new_appointment)
        session.commit()
        session.refresh(new_appointment)
        return jsonify({"message": "Appointment created successfully", "appointment_id": new_appointment.appointment_id}), 201
    finally:
        session.close()

@bp.route('/appointments/<int:appointment_id>', methods=['GET'])
def get_appointment(appointment_id):
    session = SessionLocal()
    appointment = session.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
    if appointment:
        result = {
            "appointment_id": appointment.appointment_id,
            "client_id": appointment.client_id,
            "nutritionist_id": appointment.nutritionist_id,
            "scheduled_at": appointment.scheduled_at.isoformat(),
            "status": appointment.status,
            "google_calendar_event_id": appointment.google_calendar_event_id
        }
        session.close()
        return jsonify(result)
    else:
        session.close()
        return jsonify({"message": "Appointment not found"}), 404

@bp.route('/appointments', methods=['GET'])
def list_appointments():
    session = SessionLocal()
    appointments = session.query(Appointment).all()
    result = []
    for appt in appointments:
        result.append({
            "appointment_id": appt.appointment_id,
            "client_id": appt.client_id,
            "nutritionist_id": appt.nutritionist_id,
            "scheduled_at": appt.scheduled_at.isoformat(),
            "status": appt.status
        })
    session.close()
    return jsonify(result)
