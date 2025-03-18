from flask import Blueprint, request, jsonify, render_template
from datetime import datetime
from database import SessionLocal
from models import User, UserProgress, DietPlan, WorkoutPlan, Message, Appointment

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
    new_user = User(
        username=data['username'],
        email=data['email'],
        password_hash=data['password_hash'],
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
    new_diet_plan = DietPlan(
        user_id=user_id,
        nutritionist_id=data.get('nutritionist_id'),
        start_date=datetime.strptime(data['start_date'], '%Y-%m-%d'),
        end_date=datetime.strptime(data['end_date'], '%Y-%m-%d'),
        meal_details=data['meal_details'],
        preferences_client_notes=data.get('preferences_client_notes'),
        notes=data.get('notes')
    )
    session.add(new_diet_plan)
    session.commit()
    session.refresh(new_diet_plan)
    session.close()
    return jsonify({"message": "Diet plan created successfully", "diet_id": new_diet_plan.diet_id}), 201

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
    new_appointment = Appointment(
        client_id=data['client_id'],
        nutritionist_id=data['nutritionist_id'],
        scheduled_at=datetime.strptime(data['scheduled_at'], '%Y-%m-%d %H:%M:%S'),
        status=data.get('status', 'scheduled'),
        google_calendar_event_id=data.get('google_calendar_event_id')
    )
    session.add(new_appointment)
    session.commit()
    session.refresh(new_appointment)
    session.close()
    return jsonify({"message": "Appointment created successfully", "appointment_id": new_appointment.appointment_id}), 201

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
