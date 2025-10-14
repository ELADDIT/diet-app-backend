import json
import os
import uuid
import hmac
import hashlib
from datetime import datetime
from sqlalchemy.exc import IntegrityError


from flask import Blueprint, request, jsonify, render_template, g
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_
from database import SessionLocal
from auth import access_token_expires_in, create_access_token, current_user, jwt_required


from models import (
    User,
    UserProgress,
    DietPlan,
    WorkoutPlan,
    Message,
    Appointment,
    GroupSession,
    Subscription,
)
from services import meetings, AIServiceError, ai_service


class SubscriptionNotFoundError(RuntimeError):
    pass


class QuotaExceededError(RuntimeError):
    pass


def _reset_subscription_period(subscription: Subscription, now: datetime) -> None:
    if subscription.period_start is None:
        subscription.period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        subscription.sessions_booked_this_month = 0
        return

    if (
        subscription.period_start.year != now.year
        or subscription.period_start.month != now.month
    ):
        subscription.period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        subscription.sessions_booked_this_month = 0


def _consume_quota(session, user_id: int, now: datetime) -> Subscription:
    subscription = session.query(Subscription).filter(Subscription.user_id == user_id).first()
    if not subscription:
        raise SubscriptionNotFoundError("Active subscription is required")

    _reset_subscription_period(subscription, now)
    quota = subscription.monthly_session_quota
    if quota is not None and subscription.sessions_booked_this_month >= quota:
        raise QuotaExceededError("Monthly session quota exceeded")

    subscription.sessions_booked_this_month += 1
    session.flush()
    return subscription


def _release_quota(subscription: Subscription) -> None:
    if subscription.sessions_booked_this_month > 0:
        subscription.sessions_booked_this_month -= 1
    SubscriptionPlan,
    UserSubscription,
)


WEBHOOK_SECRET = os.getenv('PAYMENT_WEBHOOK_SECRET', 'test_secret')


class PaymentClient:
    """Very small abstraction over the external payment provider."""

    def create_checkout_session(self, *, plan: SubscriptionPlan, user: User) -> dict:
        checkout_id = f"cs_{uuid.uuid4().hex}"
        return {
            "id": checkout_id,
            "url": f"https://payments.example.com/checkout/{checkout_id}",
        }

    def cancel_subscription(self, *, external_subscription_id: str) -> dict:
        # In a real implementation the external API would be called here.
        return {"status": "canceled", "external_subscription_id": external_subscription_id}


payment_client = PaymentClient()


def _verify_signature(raw_payload: bytes, provided_signature: str | None) -> bool:
    if not provided_signature:
        return False
    expected = hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided_signature)


def _serialize_subscription(subscription: UserSubscription | None) -> dict | None:
    if subscription is None:
        return None
    return {
        "subscription_id": subscription.subscription_id,
        "status": subscription.status,
        "plan": {
            "plan_id": subscription.plan.plan_id,
            "name": subscription.plan.name,
        } if subscription.plan else None,
        "checkout_session_id": subscription.checkout_session_id,
        "external_subscription_id": subscription.external_subscription_id,
        "external_customer_id": subscription.external_customer_id,
        "renewal_date": subscription.renewal_date.isoformat() if subscription.renewal_date else None,
        "activated_at": subscription.activated_at.isoformat() if subscription.activated_at else None,
        "canceled_at": subscription.canceled_at.isoformat() if subscription.canceled_at else None,
    }


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
# Subscription Plans Endpoints
# --------------------------------
@bp.route('/subscriptions/plans', methods=['GET', 'POST'])
def manage_subscription_plans():
    session = SessionLocal()
    try:
        if request.method == 'POST':
            data = request.get_json() or {}
            try:
                price = data['price']
                billing_interval = data['billing_interval']
                name = data['name']
            except KeyError as exc:  # pragma: no cover - defensive guard
                return jsonify({"error": f"Missing required field: {exc.args[0]}"}), 400

            plan = SubscriptionPlan(
                name=name,
                description=data.get('description'),
                price=price,
                billing_interval=billing_interval,
                one_on_one_session_limit=data.get('one_on_one_session_limit', 0),
                group_session_limit=data.get('group_session_limit', 0),
                allow_one_on_one=data.get('allow_one_on_one', False),
                allow_group_sessions=data.get('allow_group_sessions', False),
            )
            session.add(plan)
            session.commit()
            session.refresh(plan)
            return (
                jsonify(
                    {
                        "plan_id": plan.plan_id,
                        "name": plan.name,
                        "billing_interval": plan.billing_interval,
                    }
                ),
                201,
            )

        plans = session.query(SubscriptionPlan).order_by(SubscriptionPlan.plan_id).all()
        serialized = []
        for plan in plans:
            serialized.append(
                {
                    "plan_id": plan.plan_id,
                    "name": plan.name,
                    "description": plan.description,
                    "price": float(plan.price),
                    "billing_interval": plan.billing_interval,
                    "one_on_one_session_limit": plan.one_on_one_session_limit,
                    "group_session_limit": plan.group_session_limit,
                    "allow_one_on_one": plan.allow_one_on_one,
                    "allow_group_sessions": plan.allow_group_sessions,
                }
            )
        return jsonify(serialized)
    finally:
        session.close()


# --------------------------------
# User Subscription Endpoints
# --------------------------------
@bp.route('/users/<int:user_id>/subscription', methods=['GET', 'POST', 'DELETE'])
def manage_user_subscription(user_id: int):
    session = SessionLocal()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user is None:
            return jsonify({"error": "User not found"}), 404

        latest_subscription = (
            session.query(UserSubscription)
            .filter(UserSubscription.user_id == user_id)
            .order_by(UserSubscription.created_at.desc())
            .first()
        )

        if request.method == 'GET':
            return jsonify(
                {
                    "user_id": user.user_id,
                    "sub_status": user.sub_status,
                    "subscription_expiry": user.subscription_expiry.isoformat()
                    if user.subscription_expiry
                    else None,
                    "subscription": _serialize_subscription(latest_subscription),
                }
            )

        if request.method == 'POST':
            data = request.get_json() or {}
            plan_id = data.get('plan_id')
            if plan_id is None:
                return jsonify({"error": "plan_id is required"}), 400

            plan = session.query(SubscriptionPlan).filter(SubscriptionPlan.plan_id == plan_id).first()
            if plan is None:
                return jsonify({"error": "Subscription plan not found"}), 404

            checkout = payment_client.create_checkout_session(plan=plan, user=user)

            subscription = UserSubscription(
                user_id=user.user_id,
                plan_id=plan.plan_id,
                status='pending',
                checkout_session_id=checkout['id'],
            )
            session.add(subscription)
            session.commit()
            session.refresh(subscription)

            return (
                jsonify(
                    {
                        "checkout_session_id": checkout['id'],
                        "checkout_url": checkout['url'],
                        "subscription": _serialize_subscription(subscription),
                    }
                ),
                201,
            )

        # DELETE
        if latest_subscription is None:
            return jsonify({"error": "No subscription to cancel"}), 404

        if latest_subscription.external_subscription_id:
            payment_client.cancel_subscription(
                external_subscription_id=latest_subscription.external_subscription_id
            )

        latest_subscription.status = 'canceled'
        latest_subscription.canceled_at = datetime.utcnow()
        user.sub_status = False
        user.subscription_expiry = None
        session.commit()

        return jsonify({"message": "Subscription canceled"})
    finally:
        session.close()


# --------------------------------
# Webhook Endpoint
# --------------------------------
@bp.route('/webhooks/payments', methods=['POST'])
def payment_webhook():
    raw_payload = request.get_data()
    signature = request.headers.get('X-Signature')

    if not _verify_signature(raw_payload, signature):
        return jsonify({"error": "Invalid signature"}), 400

    try:
        event = json.loads(raw_payload.decode('utf-8'))
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid payload"}), 400

    event_type = event.get('type')
    data = event.get('data', {})

    session = SessionLocal()
    try:
        if event_type == 'checkout.session.completed':
            checkout_id = data.get('checkout_session_id')
            renewal = data.get('renewal_date')
            external_subscription_id = data.get('external_subscription_id')
            external_customer_id = data.get('external_customer_id')

            subscription = (
                session.query(UserSubscription)
                .filter(UserSubscription.checkout_session_id == checkout_id)
                .first()
            )

            if subscription is None:
                return jsonify({"error": "Subscription not found"}), 404

            subscription.status = 'active'
            subscription.external_subscription_id = external_subscription_id
            subscription.external_customer_id = external_customer_id
            subscription.activated_at = datetime.utcnow()
            if renewal:
                subscription.renewal_date = datetime.fromisoformat(renewal)

            user = session.query(User).filter(User.user_id == subscription.user_id).one()
            user.sub_status = True
            user.subscription_expiry = subscription.renewal_date
            session.commit()
            return jsonify({"status": "processed"})

        if event_type in {'customer.subscription.deleted', 'subscription.canceled'}:
            external_subscription_id = data.get('external_subscription_id')
            subscription = (
                session.query(UserSubscription)
                .filter(UserSubscription.external_subscription_id == external_subscription_id)
                .first()
            )
            if subscription is None:
                return jsonify({"error": "Subscription not found"}), 404

            subscription.status = 'canceled'
            subscription.canceled_at = datetime.utcnow()
            user = session.query(User).filter(User.user_id == subscription.user_id).one()
            user.sub_status = False
            user.subscription_expiry = None
            session.commit()
            return jsonify({"status": "processed"})

        return jsonify({"status": "ignored"})
    finally:
        session.close()

# --------------------------------
# Subscriptions Endpoints
# --------------------------------
@bp.route('/subscriptions', methods=['POST'])
def create_subscription():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    plan_name = data.get('plan_name')
    monthly_session_quota = data.get('monthly_session_quota')

    if user_id is None or plan_name is None or monthly_session_quota is None:
        return jsonify({"error": "user_id, plan_name, and monthly_session_quota are required"}), 400

    try:
        monthly_session_quota = int(monthly_session_quota)
    except (TypeError, ValueError):
        return jsonify({"error": "monthly_session_quota must be an integer"}), 400

    session = SessionLocal()
    try:
        subscription = Subscription(
            user_id=user_id,
            plan_name=plan_name,
            monthly_session_quota=monthly_session_quota,
            period_start=datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0),
        )
        session.add(subscription)
        session.commit()
        session.refresh(subscription)
        return jsonify({
            "message": "Subscription created successfully",
            "subscription_id": subscription.subscription_id,
        }), 201
    except IntegrityError:
        session.rollback()
        return jsonify({"error": "Subscription already exists for this user"}), 409
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
# Group Sessions Endpoints
# --------------------------------
@bp.route('/group_sessions', methods=['POST'])
def create_group_session():
    data = request.get_json() or {}
    try:
        start_time = datetime.strptime(data['start_time'], '%Y-%m-%d %H:%M:%S')
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Invalid datetime format. Expected YYYY-MM-DD HH:MM:SS."}), 400

    nutritionist_id = data.get('nutritionist_id')
    topic = data.get('topic')
    if nutritionist_id is None or not topic:
        return jsonify({"error": "nutritionist_id and topic are required"}), 400

    meeting_type = data.get('meeting_type', 'virtual')
    location = data.get('location')
    recurrence_rule = data.get('recurrence_rule')
    raw_max_participants = data.get('max_participants')
    try:
        max_participants = int(raw_max_participants) if raw_max_participants is not None else None
    except (TypeError, ValueError):
        return jsonify({"error": "max_participants must be an integer"}), 400

    session = SessionLocal()
    try:
        try:
            details = meetings.meeting_provider.create_meeting(
                topic=topic,
                start_time=start_time,
                meeting_type=meeting_type,
                location=location,
                max_participants=max_participants,
            )
        except meetings.MeetingProviderError as exc:
            session.rollback()
            return jsonify({"error": str(exc)}), 502

        group_session = GroupSession(
            nutritionist_id=nutritionist_id,
            topic=topic,
            description=data.get('description'),
            start_time=start_time,
            recurrence_rule=recurrence_rule,
            meeting_type=meeting_type,
            location=location,
            meeting_url=details.meeting_url,
            max_participants=max_participants,
            meeting_provider_event_id=details.event_id,
        )
        session.add(group_session)
        session.commit()
        session.refresh(group_session)
        return jsonify({
            "message": "Group session created successfully",
            "group_session_id": group_session.group_session_id,
            "meeting_url": group_session.meeting_url,
        }), 201
    finally:
        session.close()


@bp.route('/group_sessions/<int:group_session_id>/join', methods=['POST'])
def join_group_session(group_session_id):
    data = request.get_json() or {}
    client_id = data.get('client_id')
    if client_id is None:
        return jsonify({"error": "client_id is required"}), 400

    session = SessionLocal()
    try:
        group_session = session.query(GroupSession).filter(GroupSession.group_session_id == group_session_id).first()
        if not group_session:
            return jsonify({"error": "Group session not found"}), 404

        existing = session.query(Appointment).filter(
            Appointment.group_session_id == group_session_id,
            Appointment.client_id == client_id,
            Appointment.status != 'cancelled',
        ).first()
        if existing:
            return jsonify({
                "message": "Already joined",
                "appointment_id": existing.appointment_id,
            })

        active_participants = session.query(Appointment).filter(
            Appointment.group_session_id == group_session_id,
            Appointment.status != 'cancelled',
        ).count()
        if group_session.max_participants is not None and active_participants >= group_session.max_participants:
            return jsonify({"error": "Group session is full"}), 409

        try:
            _consume_quota(session, client_id, group_session.start_time)
        except SubscriptionNotFoundError as exc:
            session.rollback()
            return jsonify({"error": str(exc)}), 400
        except QuotaExceededError as exc:
            session.rollback()
            return jsonify({"error": str(exc)}), 409

        appointment = Appointment(
            client_id=client_id,
            nutritionist_id=group_session.nutritionist_id,
            scheduled_at=group_session.start_time,
            status='scheduled',
            meeting_provider_event_id=group_session.meeting_provider_event_id,
            meeting_url=group_session.meeting_url,
            location=group_session.location,
            meeting_type=group_session.meeting_type,
            max_participants=group_session.max_participants,
            group_session_id=group_session_id,
        )
        session.add(appointment)
        session.commit()
        session.refresh(appointment)
        return jsonify({
            "message": "Joined group session",
            "appointment_id": appointment.appointment_id,
        }), 201
    finally:
        session.close()


@bp.route('/group_sessions/<int:group_session_id>/withdraw', methods=['DELETE'])
def withdraw_group_session(group_session_id):
    data = request.get_json(silent=True) or {}
    client_id = data.get('client_id')
    if client_id is None:
        return jsonify({"error": "client_id is required"}), 400

    session = SessionLocal()
    try:
        appointment = session.query(Appointment).filter(
            Appointment.group_session_id == group_session_id,
            Appointment.client_id == client_id,
            Appointment.status != 'cancelled',
        ).first()
        if not appointment:
            return jsonify({"error": "Enrollment not found"}), 404

        appointment.status = 'cancelled'

        subscription = session.query(Subscription).filter(Subscription.user_id == client_id).first()
        if subscription:
            _reset_subscription_period(subscription, datetime.utcnow())
            _release_quota(subscription)

        session.commit()
        return jsonify({"message": "Withdrawn from group session"})
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
        meeting_type = data.get('meeting_type', 'virtual')
        location = data.get('location')
        raw_max_participants = data.get('max_participants', 1)
        try:
            if raw_max_participants is None:
                max_participants = 1
            else:
                max_participants = int(raw_max_participants)
        except (TypeError, ValueError):
            return jsonify({"error": "max_participants must be an integer"}), 400

        try:
            _consume_quota(session, data['client_id'], scheduled_at)
        except SubscriptionNotFoundError as exc:
            session.rollback()
            return jsonify({"error": str(exc)}), 400
        except QuotaExceededError as exc:
            session.rollback()
            return jsonify({"error": str(exc)}), 409

        try:
            details = meetings.meeting_provider.create_meeting(
                topic=data.get('topic', 'Nutrition Consultation'),
                start_time=scheduled_at,
                meeting_type=meeting_type,
                location=location,
                max_participants=max_participants,
            )
        except meetings.MeetingProviderError as exc:
            session.rollback()
            return jsonify({"error": str(exc)}), 502

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
            meeting_provider_event_id=details.event_id,
            meeting_url=details.meeting_url,
            location=location,
            meeting_type=meeting_type,
            max_participants=max_participants,
        )
        session.add(new_appointment)
        session.commit()
        session.refresh(new_appointment)
        return jsonify({
            "message": "Appointment created successfully",
            "appointment_id": new_appointment.appointment_id,
            "meeting_url": new_appointment.meeting_url,
            "meeting_provider_event_id": new_appointment.meeting_provider_event_id,
        }), 201
    finally:
        session.close()


@bp.route('/appointments/<int:appointment_id>', methods=['PATCH'])
def update_appointment(appointment_id):
    data = request.get_json() or {}
    session = SessionLocal()
    try:
        appointment = session.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
        if not appointment:
            return jsonify({"error": "Appointment not found"}), 404

        new_time = None
        if 'scheduled_at' in data:
            try:
                new_time = datetime.strptime(data['scheduled_at'], '%Y-%m-%d %H:%M:%S')
            except (TypeError, ValueError):
                return jsonify({"error": "Invalid datetime format. Expected YYYY-MM-DD HH:MM:SS."}), 400

        if new_time and appointment.meeting_provider_event_id:
            try:
                details = meetings.meeting_provider.update_meeting(
                    event_id=appointment.meeting_provider_event_id,
                    start_time=new_time,
                )
                if details.meeting_url:
                    appointment.meeting_url = details.meeting_url
            except meetings.MeetingProviderError as exc:
                session.rollback()
                return jsonify({"error": str(exc)}), 502

        if new_time:
            appointment.scheduled_at = new_time

        if 'meeting_type' in data:
            appointment.meeting_type = data['meeting_type']
        if 'location' in data:
            appointment.location = data['location']

        session.commit()
        session.refresh(appointment)
        return jsonify({
            "message": "Appointment updated",
            "appointment_id": appointment.appointment_id,
            "scheduled_at": appointment.scheduled_at.isoformat(),
            "meeting_url": appointment.meeting_url,
        })
    finally:
        session.close()


@bp.route('/appointments/<int:appointment_id>', methods=['DELETE'])
def cancel_appointment(appointment_id):
    session = SessionLocal()
    try:
        appointment = session.query(Appointment).filter(Appointment.appointment_id == appointment_id).first()
        if not appointment:
            return jsonify({"error": "Appointment not found"}), 404

        if appointment.status == 'cancelled':
            return jsonify({"message": "Appointment already cancelled"})

        if appointment.meeting_provider_event_id and appointment.group_session_id is None:
            try:
                meetings.meeting_provider.delete_meeting(event_id=appointment.meeting_provider_event_id)
            except meetings.MeetingProviderError as exc:
                session.rollback()
                return jsonify({"error": str(exc)}), 502

        appointment.status = 'cancelled'

        subscription = session.query(Subscription).filter(Subscription.user_id == appointment.client_id).first()
        if subscription:
            _reset_subscription_period(subscription, datetime.utcnow())
            _release_quota(subscription)

        session.commit()
        return jsonify({"message": "Appointment cancelled"})
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
            "meeting_provider_event_id": appointment.meeting_provider_event_id,
            "meeting_url": appointment.meeting_url,
            "location": appointment.location,
            "meeting_type": appointment.meeting_type,
            "max_participants": appointment.max_participants,
            "group_session_id": appointment.group_session_id,
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
