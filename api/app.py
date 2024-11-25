import os
from flask import Flask, jsonify, request
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, DECIMAL, Text, Boolean, ForeignKey, func
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime

app = Flask(__name__)

# Database URL from environment variable or default value
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://my_user:my_password@db:5432/my_database")

# Create a database engine
engine = create_engine(DATABASE_URL)

# Create a configured "Session" class
SessionLocal = sessionmaker(bind=engine)

# Base class for declarative models
Base = declarative_base()

# -----------------------
# Model Definitions
# -----------------------

# 1. Users Table
class User(Base):
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    full_name = Column(String(100))
    gender = Column(String(10))
    age = Column(Integer)
    weight = Column(DECIMAL(5, 2))  # Weight in kg
    height = Column(DECIMAL(5, 2))  # Height in cm
    goal = Column(String(100))  # Examples: "lose weight", "gain muscle"
    sub_status = Column(Boolean, default=False)
    subscription_expiry = Column(DateTime)
    neck_circumference = Column(DECIMAL(5, 2))
    abdomen_circumference = Column(DECIMAL(5, 2))
    hip_circumference = Column(DECIMAL(5, 2))
    underlying_medical_conditions = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    progress = relationship('UserProgress', back_populates='user')
    diet_plans = relationship('DietPlan', back_populates='user')
    workout_plans = relationship('WorkoutPlan', back_populates='user')

# 2. User Progress Table
class UserProgress(Base):
    __tablename__ = 'user_progress'

    progress_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    recorded_at = Column(DateTime, default=func.now())
    weight = Column(DECIMAL(5, 2))
    bmi = Column(DECIMAL(5, 2))
    body_fat_percentage = Column(DECIMAL(5, 2))
    neck_circumference = Column(DECIMAL(5, 2))
    abdomen_circumference = Column(DECIMAL(5, 2))
    hip_circumference = Column(DECIMAL(5, 2))
    notes = Column(Text)

    # Relationships
    user = relationship('User', back_populates='progress')

# 3. Diet Plans Table
class DietPlan(Base):
    __tablename__ = 'diet_plans'

    diet_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    nutritionist_id = Column(Integer)
    created_at = Column(DateTime, default=func.now())
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    meal_details = Column(Text)
    preferences_client_notes = Column(Text)
    notes = Column(Text)

    # Relationships
    user = relationship('User', back_populates='diet_plans')

# 4. Workout Plans Table
class WorkoutPlan(Base):
    __tablename__ = 'workout_plans'

    workout_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    trainer_id = Column(Integer)
    created_at = Column(DateTime, default=func.now())
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    workout_details = Column(Text)
    notes = Column(Text)

    # Relationships
    user = relationship('User', back_populates='workout_plans')

# 5. Messages Table
class Message(Base):
    __tablename__ = 'messages'

    message_id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    receiver_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    sent_at = Column(DateTime, default=func.now())
    message_content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)

# 6. Appointments Table
class Appointment(Base):
    __tablename__ = 'appointments'

    appointment_id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    nutritionist_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())
    status = Column(String(50), default='scheduled')
    google_calendar_event_id = Column(String(255))

# -----------------------
# Create Tables
# -----------------------

# Create all tables in the database
Base.metadata.create_all(bind=engine)

# -----------------------
# API Routes
# -----------------------

@app.route('/')
def index():
    return "Welcome to the API!"

# Users Endpoints

@app.route('/users', methods=['GET'])
def get_users():
    session = SessionLocal()
    users = session.query(User).all()
    result = [
        {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "gender": user.gender,
            "age": user.age,
            "weight": float(user.weight) if user.weight else None,
            "height": float(user.height) if user.height else None,
            "goal": user.goal
            # Add other fields as needed
        }
        for user in users
    ]
    session.close()
    return jsonify(result)

@app.route('/users', methods=['POST'])
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

# Diet Plans Endpoints 

@app.route('/users/<int:user_id>/diet_plans', methods=['GET'])
def get_diet_plans(user_id):
    session = SessionLocal()
    diet_plans = session.query(DietPlan).filter(DietPlan.user_id == user_id).all()
    result = [
        {
            "diet_id": plan.diet_id,
            "start_date": plan.start_date.isoformat() if plan.start_date else None,
            "end_date": plan.end_date.isoformat() if plan.end_date else None,
            "meal_details": plan.meal_details,
            "preferences_client_notes": plan.preferences_client_notes,
            "notes": plan.notes
        }
        for plan in diet_plans
    ]
    session.close()
    return jsonify(result)

@app.route('/users/<int:user_id>/diet_plans', methods=['POST'])
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

# Messages Endpoints

@app.route('/messages', methods=['POST'])
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

@app.route('/messages/conversation', methods=['GET'])
def get_conversation():
    user1_id = request.args.get('user1_id', type=int)
    user2_id = request.args.get('user2_id', type=int)
    session = SessionLocal()
    messages = session.query(Message).filter(
        ((Message.sender_id == user1_id) & (Message.receiver_id == user2_id)) |
        ((Message.sender_id == user2_id) & (Message.receiver_id == user1_id))
    ).order_by(Message.sent_at).all()
    result = [
        {
            "message_id": msg.message_id,
            "sender_id": msg.sender_id,
            "receiver_id": msg.receiver_id,
            "sent_at": msg.sent_at.isoformat(),
            "message_content": msg.message_content,
            "is_read": msg.is_read
        }
        for msg in messages
    ]
    session.close()
    return jsonify(result)

# Appointments Endpoints

@app.route('/appointments', methods=['POST'])
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

@app.route('/appointments/<int:appointment_id>', methods=['GET'])
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

# Run the Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
