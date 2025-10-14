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
    role = Column(String(20), nullable=False, default='client')
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
    subscriptions = relationship('UserSubscription', back_populates='user', cascade='all, delete-orphan')

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
    google_calendar_event_id = Column(String(255))


class SubscriptionPlan(Base):
    __tablename__ = 'subscription_plans'

    plan_id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    price = Column(DECIMAL(8, 2), nullable=False)
    billing_interval = Column(String(50), nullable=False)
    one_on_one_session_limit = Column(Integer, default=0)
    group_session_limit = Column(Integer, default=0)
    allow_one_on_one = Column(Boolean, default=False)
    allow_group_sessions = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    subscriptions = relationship('UserSubscription', back_populates='plan', cascade='all, delete-orphan')


class UserSubscription(Base):
    __tablename__ = 'user_subscriptions'

    subscription_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    plan_id = Column(Integer, ForeignKey('subscription_plans.plan_id'), nullable=False)
    status = Column(String(50), default='pending', nullable=False)
    checkout_session_id = Column(String(255), unique=True)
    external_customer_id = Column(String(255))
    external_subscription_id = Column(String(255))
    renewal_date = Column(DateTime)
    activated_at = Column(DateTime)
    canceled_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship('User', back_populates='subscriptions')
    plan = relationship('SubscriptionPlan', back_populates='subscriptions')
