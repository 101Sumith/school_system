import hmac
from functools import wraps

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from backend.extensions import db
from backend.models import Faculty, Student, User


def serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="campus-auth-v1")


def issue_token(user):
    return serializer().dumps({"user_id": user.id})


def load_token(token):
    try:
        identity = serializer().loads(
            token, max_age=current_app.config["TOKEN_MAX_AGE_SECONDS"]
        )
    except (BadSignature, SignatureExpired):
        return None
    return db.session.get(User, identity.get("user_id"))


def password_hash(password):
    return generate_password_hash(password, method="scrypt")


def verify_password(user, password):
    return check_password_hash(user.password_hash, password)


def require_roles(*roles):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if not user:
                return jsonify({"error": "Authentication required."}), 401
            if roles and user.role not in roles:
                return jsonify({"error": "You do not have permission for this action."}), 403
            return view(*args, **kwargs)

        return wrapped

    return decorate


def bootstrap_token_is_valid(candidate):
    expected = current_app.config.get("ERP_BOOTSTRAP_TOKEN", "")
    return bool(expected and candidate and hmac.compare_digest(candidate, expected))


def profile_email(role, profile_id):
    model = Student if role == "student" else Faculty
    profile = db.session.get(model, profile_id)
    return profile.email if profile else None
