import json
from datetime import datetime

from flask import Blueprint, request, jsonify, render_template
from werkzeug.security import generate_password_hash
from database import SessionLocal
from models import (
    User,
    UserProgress,
    DietPlan,
    WorkoutPlan,
    Message,
    Appointment,
    AIInteraction,
)
from services import AIServiceError, ai_service

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


@bp.route('/users/<int:user_id>/ai/diet_plan', methods=['POST'])
def generate_ai_diet_plan(user_id):
    data = request.get_json() or {}
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        goal = data.get("goal") or user.goal
        if not goal:
            return jsonify({"error": "A goal is required to generate a diet plan."}), 400

        start_date = None
        end_date = None
        if data.get("start_date"):
            try:
                start_date = datetime.strptime(data["start_date"], '%Y-%m-%d')
            except ValueError:
                return jsonify({"error": "Invalid start_date format. Expected YYYY-MM-DD."}), 400
        if data.get("end_date"):
            try:
                end_date = datetime.strptime(data["end_date"], '%Y-%m-%d')
            except ValueError:
                return jsonify({"error": "Invalid end_date format. Expected YYYY-MM-DD."}), 400

        try:
            ai_result = ai_service.generate_diet_plan(
                user=user,
                metrics=data.get("metrics"),
                goal=goal,
            )
        except AIServiceError as exc:
            session.rollback()
            return jsonify({"error": str(exc)}), 502

        diet_plan = DietPlan(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            meal_details=ai_result["response"],
            preferences_client_notes=data.get("preferences_client_notes"),
            notes=data.get("notes"),
        )
        session.add(diet_plan)

        interaction = AIInteraction(
            user_id=user_id,
            interaction_type='diet_plan',
            prompt=ai_result["prompt"],
            response=ai_result["response"],
            context=json.dumps({"metrics": data.get("metrics"), "goal": goal}, default=str),
        )
        session.add(interaction)

        session.commit()
        session.refresh(diet_plan)
        session.refresh(interaction)

        return (
            jsonify(
                {
                    "diet_plan_id": diet_plan.diet_id,
                    "diet_plan": ai_result["response"],
                    "interaction_id": interaction.interaction_id,
                }
            ),
            201,
        )
    finally:
        session.close()


@bp.route('/users/<int:user_id>/ai/chat', methods=['POST'])
def ai_chat(user_id):
    data = request.get_json() or {}
    message = data.get("message")
    if not message:
        return jsonify({"error": "A message is required."}), 400

    session = SessionLocal()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        history = data.get("history")
        try:
            chat_result = ai_service.chat(user=user, message=message, history=history)
        except AIServiceError as exc:
            session.rollback()
            return jsonify({"error": str(exc)}), 502

        interaction = AIInteraction(
            user_id=user_id,
            interaction_type='chat',
            prompt=chat_result["prompt"],
            response=chat_result["response"],
            context=json.dumps({"history": history}, default=str) if history else None,
        )
        session.add(interaction)

        workout_plan = None
        workout_interaction = None
        if data.get("generate_workout_plan"):
            workout_goal = data.get("workout_goal") or data.get("goal") or user.goal
            if not workout_goal:
                session.rollback()
                return jsonify(
                    {
                        "error": "A workout_goal or goal is required when generate_workout_plan is true.",
                    }
                ), 400
            try:
                workout_result = ai_service.generate_workout_plan(
                    user=user,
                    metrics=data.get("metrics"),
                    goal=workout_goal,
                )
            except AIServiceError as exc:
                session.rollback()
                return jsonify({"error": str(exc)}), 502

            workout_plan = WorkoutPlan(
                user_id=user_id,
                workout_details=workout_result["response"],
                notes=data.get("workout_notes"),
            )
            session.add(workout_plan)

            workout_interaction = AIInteraction(
                user_id=user_id,
                interaction_type='workout_plan',
                prompt=workout_result["prompt"],
                response=workout_result["response"],
                context=json.dumps(
                    {"metrics": data.get("metrics"), "goal": workout_goal},
                    default=str,
                ),
            )
            session.add(workout_interaction)

        session.commit()
        session.refresh(interaction)

        response_payload = {
            "message": chat_result["response"],
            "interaction_id": interaction.interaction_id,
        }

        if workout_plan and workout_interaction:
            session.refresh(workout_plan)
            session.refresh(workout_interaction)
            response_payload.update(
                {
                    "workout_plan_id": workout_plan.workout_id,
                    "workout_plan": workout_plan.workout_details,
                    "workout_interaction_id": workout_interaction.interaction_id,
                }
            )

        return jsonify(response_payload), 200
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
