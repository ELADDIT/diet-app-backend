from flask import Blueprint, request, jsonify, render_template, g
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_
from database import SessionLocal
from models import User, UserProgress, DietPlan, WorkoutPlan, Message, Appointment
from auth import access_token_expires_in, create_access_token, current_user, jwt_required

bp = Blueprint('api', __name__)

VALID_ROLES = {'client', 'nutritionist', 'admin'}

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
@jwt_required(roles={'admin'})
def get_users():
    session = SessionLocal()
    try:
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
                "goal": user.goal,
                "role": user.role,
            })
        return jsonify(result)
    finally:
        session.close()

@bp.route('/users', methods=['POST'])
def create_user():
    data = request.get_json() or {}
    session = SessionLocal()

    # Support clients sending either a plain password or a precomputed hash
    raw_password = data.get('password')
    password_hash = data.get('password_hash')
    if raw_password is not None:
        password_hash = generate_password_hash(raw_password)
    if password_hash is None:
        session.close()
        return jsonify({"error": "Password is required"}), 400

    role = data.get('role', 'client')
    if role not in VALID_ROLES:
        session.close()
        return jsonify({"error": "Invalid role"}), 400

    try:
        new_user = User(
            username=data['username'],
            email=data['email'],
            password_hash=password_hash,
            role=role,
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
        return jsonify({"message": "User created successfully", "user_id": new_user.user_id, "role": new_user.role}), 201
    finally:
        session.close()


# --------------------------------
# Authentication Endpoints
# --------------------------------
@bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    identifier = data.get('username') or data.get('email')
    password = data.get('password')
    if not identifier or not password:
        return jsonify({"error": "Username/email and password are required"}), 400

    session = SessionLocal()
    try:
        user = session.query(User).filter(
            or_(User.username == identifier, User.email == identifier)
        ).first()
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({"error": "Invalid credentials"}), 401

        token = create_access_token(user_id=user.user_id, role=user.role)
        return jsonify({
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": access_token_expires_in(),
            "user": {
                "user_id": user.user_id,
                "username": user.username,
                "role": user.role,
            },
        })
    finally:
        session.close()


# --------------------------------
# Diet Plans Endpoints
# --------------------------------
@bp.route('/users/<int:user_id>/diet_plans', methods=['GET'])
@jwt_required(roles={'admin', 'nutritionist'}, allow_self_kw='user_id')
def get_diet_plans(user_id):
    session = SessionLocal()
    try:
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
        return jsonify(result)
    finally:
        session.close()

@bp.route('/users/<int:user_id>/diet_plans', methods=['POST'])
@jwt_required(roles={'admin', 'nutritionist'}, allow_self_kw='user_id')
def create_diet_plan(user_id):
    data = request.get_json() or {}
    session = SessionLocal()
    try:
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d')
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "Invalid date format. Expected YYYY-MM-DD."}), 400

        acting_user = current_user()
        if acting_user['role'] == 'client' and acting_user['user_id'] != user_id:
            return jsonify({"error": "Forbidden"}), 403

        new_diet_plan = DietPlan(
            user_id=user_id,
            nutritionist_id=data.get('nutritionist_id') or (
                acting_user['user_id'] if acting_user['role'] in {'nutritionist', 'admin'} else None
            ),
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
# Messages Endpoints
# --------------------------------
@bp.route('/messages', methods=['POST'])
@jwt_required()
def send_message():
    data = request.get_json() or {}
    sender_id = data.get('sender_id')
    receiver_id = data.get('receiver_id')
    message_content = data.get('message_content')

    if sender_id is None or receiver_id is None or not message_content:
        return jsonify({"error": "sender_id, receiver_id, and message_content are required"}), 400

    acting_user = current_user()
    if acting_user['role'] != 'admin' and acting_user['user_id'] != sender_id:
        return jsonify({"error": "Forbidden"}), 403

    session = SessionLocal()
    try:
        new_message = Message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_content=message_content
        )
        session.add(new_message)
        session.commit()
        session.refresh(new_message)
        return jsonify({"message": "Message sent successfully", "message_id": new_message.message_id}), 201
    finally:
        session.close()


@bp.route('/messages/conversation', methods=['GET'])
@jwt_required()
def get_conversation():
    user1_id = request.args.get('user1_id', type=int)
    user2_id = request.args.get('user2_id', type=int)

    if user1_id is None or user2_id is None:
        return jsonify({"error": "user1_id and user2_id are required"}), 400

    acting_user = current_user()
    if acting_user['role'] != 'admin' and acting_user['user_id'] not in {user1_id, user2_id}:
        return jsonify({"error": "Forbidden"}), 403

    session = SessionLocal()
    try:
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
        return jsonify(result)
    finally:
        session.close()

# --------------------------------
# Appointments Endpoints
# --------------------------------
@bp.route('/appointments', methods=['POST'])
@jwt_required()
def create_appointment():
    data = request.get_json() or {}
    session = SessionLocal()
    try:
        try:
            scheduled_at = datetime.strptime(data['scheduled_at'], '%Y-%m-%d %H:%M:%S')
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "Invalid datetime format. Expected YYYY-MM-DD HH:MM:SS."}), 400

        client_id = data.get('client_id')
        nutritionist_id = data.get('nutritionist_id')
        if client_id is None or nutritionist_id is None:
            return jsonify({"error": "client_id and nutritionist_id are required"}), 400

        acting_user = current_user()
        allowed_roles = {'admin', 'nutritionist'}
        if acting_user['role'] not in allowed_roles and acting_user['user_id'] not in {client_id, nutritionist_id}:
            return jsonify({"error": "Forbidden"}), 403

        new_appointment = Appointment(
            client_id=client_id,
            nutritionist_id=nutritionist_id,
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
@jwt_required()
def get_appointment(appointment_id):
    session = SessionLocal()
    try:
        appointment = session.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
        if not appointment:
            return jsonify({"message": "Appointment not found"}), 404

        acting_user = current_user()
        allowed_roles = {'admin', 'nutritionist'}
        if acting_user['role'] not in allowed_roles and acting_user['user_id'] not in {appointment.client_id, appointment.nutritionist_id}:
            return jsonify({"error": "Forbidden"}), 403

        result = {
            "appointment_id": appointment.appointment_id,
            "client_id": appointment.client_id,
            "nutritionist_id": appointment.nutritionist_id,
            "scheduled_at": appointment.scheduled_at.isoformat(),
            "status": appointment.status,
            "google_calendar_event_id": appointment.google_calendar_event_id
        }
        return jsonify(result)
    finally:
        session.close()


@bp.route('/appointments', methods=['GET'])
@jwt_required(roles={'admin', 'nutritionist'})
def list_appointments():
    session = SessionLocal()
    try:
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
        return jsonify(result)
    finally:
        session.close()
