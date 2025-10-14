from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    DECIMAL,
    Text,
    Boolean,
    ForeignKey,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    full_name = Column(String(100))
    gender = Column(String(10))
    age = Column(Integer)
    weight = Column(DECIMAL(5, 2))
    height = Column(DECIMAL(5, 2))
    goal = Column(String(100))
    sub_status = Column(Boolean, default=False)
    subscription_expiry = Column(DateTime)
    neck_circumference = Column(DECIMAL(5, 2))
    abdomen_circumference = Column(DECIMAL(5, 2))
    hip_circumference = Column(DECIMAL(5, 2))
    underlying_medical_conditions = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    progress = relationship('UserProgress', back_populates='user')
    diet_plans = relationship('DietPlan', back_populates='user')
    workout_plans = relationship('WorkoutPlan', back_populates='user')
    subscription = relationship('Subscription', back_populates='user', uselist=False)

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

    user = relationship('User', back_populates='progress')

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

    user = relationship('User', back_populates='diet_plans')

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

    user = relationship('User', back_populates='workout_plans')

class Message(Base):
    __tablename__ = 'messages'
    message_id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    receiver_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    sent_at = Column(DateTime, default=func.now())
    message_content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)

class Appointment(Base):
    __tablename__ = 'appointments'
    appointment_id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    nutritionist_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())
    status = Column(String(50), default='scheduled')
    meeting_provider_event_id = Column(String(255))
    meeting_url = Column(String(255))
    location = Column(String(255))
    meeting_type = Column(String(50), default='virtual')
    max_participants = Column(Integer, default=1)
    group_session_id = Column(Integer, ForeignKey('group_sessions.group_session_id'))

    client = relationship('User', foreign_keys=[client_id])
    nutritionist = relationship('User', foreign_keys=[nutritionist_id])
    group_session = relationship('GroupSession', back_populates='appointments')


class GroupSession(Base):
    __tablename__ = 'group_sessions'
    group_session_id = Column(Integer, primary_key=True)
    nutritionist_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    topic = Column(String(100), nullable=False)
    description = Column(Text)
    start_time = Column(DateTime, nullable=False)
    recurrence_rule = Column(String(100))
    meeting_type = Column(String(50), default='virtual')
    location = Column(String(255))
    meeting_url = Column(String(255))
    max_participants = Column(Integer)
    meeting_provider_event_id = Column(String(255))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    nutritionist = relationship('User')
    appointments = relationship('Appointment', back_populates='group_session')


class Subscription(Base):
    __tablename__ = 'subscriptions'
    subscription_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, unique=True)
    plan_name = Column(String(100), nullable=False)
    monthly_session_quota = Column(Integer, nullable=False)
    sessions_booked_this_month = Column(Integer, default=0)
    period_start = Column(DateTime, default=func.now())

    user = relationship('User', back_populates='subscription')
