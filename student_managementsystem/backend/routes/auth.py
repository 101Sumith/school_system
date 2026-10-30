import re

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import IntegrityError

from backend.extensions import db
from backend.models import Faculty, Student, User
from backend.security import (
    bootstrap_token_is_valid,
    issue_token,
    password_hash,
    profile_email,
    require_roles,
    verify_password,
)

auth = Blueprint("auth", __name__, url_prefix="/api/auth")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLES = {"admin", "faculty", "student"}


def success(payload, status=200):
    return jsonify({"data": payload}), status


def error(message, status=400):
    return jsonify({"error": message}), status


def validate_email(payload):
    email = payload.get("email")
    if not isinstance(email, str) or not EMAIL_PATTERN.fullmatch(email.strip()):
        raise ValueError("Enter a valid email address.")
    return email.strip().lower()


def validate_password(payload):
    password = payload.get("password")
    if not isinstance(password, str) or len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")
    if len(password) > 256:
        raise ValueError("Password must be 256 characters or fewer.")
    return password


def account_payload(user):
    data = user.to_dict()
    data["name"] = (
        user.student.name if user.student else
        user.faculty.name if user.faculty else
        user.email.split("@", 1)[0]
    )
    return data


@auth.post("/login")
def login():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("A JSON request body is required.")
    try:
        email = validate_email(payload)
        password = payload.get("password")
        if not isinstance(password, str) or len(password) > 256:
            return error("Email or password is incorrect.", 401)
    except ValueError as exc:
        return error(str(exc))
    user = User.query.filter_by(email=email).first()
    if not user or not verify_password(user, password):
        return error("Email or password is incorrect.", 401)
    return success(
        {
            "token": issue_token(user),
            "expires_in": current_app.config["TOKEN_MAX_AGE_SECONDS"],
            "user": account_payload(user),
        }
    )


@auth.post("/bootstrap")
def bootstrap():
    if User.query.count():
        return error("Administrator bootstrap is already complete.", 409)
    if not bootstrap_token_is_valid(request.headers.get("X-Bootstrap-Token")):
        return error("A valid one-time bootstrap token is required.", 401)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("A JSON request body is required.")
    try:
        email = validate_email(payload)
        password = validate_password(payload)
    except ValueError as exc:
        return error(str(exc))
    user = User(email=email, password_hash=password_hash(password), role="admin")
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error("An account with that email already exists.", 409)
    return success({"user": account_payload(user)}, 201)


@auth.get("/me")
@require_roles()
def current_user():
    from flask import g

    return success(account_payload(g.current_user))


@auth.get("/users")
@require_roles("admin")
def list_users():
    return success([user.to_dict() for user in User.query.order_by(User.id).all()])


@auth.post("/users")
@require_roles("admin")
def create_user():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("A JSON request body is required.")
    try:
        email = validate_email(payload)
        password = validate_password(payload)
        role = payload.get("role")
        if role not in ROLES:
            raise ValueError("Role must be admin, faculty, or student.")
        student_id = payload.get("student_id")
        faculty_id = payload.get("faculty_id")
        if role == "student":
            student_id = int(student_id)
            faculty_id = None
        elif role == "faculty":
            faculty_id = int(faculty_id)
            student_id = None
        else:
            student_id = faculty_id = None
    except (ValueError, TypeError) as exc:
        return error(str(exc) or "A valid profile ID is required.")
    if role in {"student", "faculty"}:
        if not profile_email(role, student_id if role == "student" else faculty_id):
            return error("The selected profile does not exist.")
        if profile_email(role, student_id if role == "student" else faculty_id).lower() != email:
            return error("Account email must match the linked profile email.")
    user = User(
        email=email,
        password_hash=password_hash(password),
        role=role,
        student_id=student_id,
        faculty_id=faculty_id,
    )
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error("That email or profile already has an account.", 409)
    return success(user.to_dict(), 201)


@auth.delete("/users/<int:user_id>")
@require_roles("admin")
def delete_user(user_id):
    from flask import g

    user = db.session.get(User, user_id)
    if not user:
        return error("Account not found.", 404)
    if user.id == g.current_user.id:
        return error("You cannot delete your own administrator account.", 409)
    if user.role == "admin" and User.query.filter_by(role="admin").count() <= 1:
        return error("At least one administrator account must remain.", 409)
    db.session.delete(user)
    db.session.commit()
    return success({"message": "Account deleted."})
