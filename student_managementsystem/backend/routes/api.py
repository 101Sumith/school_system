import re
import uuid
from datetime import date

from flask import Blueprint, g, jsonify, request
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from backend.extensions import db
from backend.models import Attendance, Course, Department, Faculty, Mark, Student, Subject

api = Blueprint("api", __name__, url_prefix="/api")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_PATTERN = re.compile(r"^[+()\d.\-\s]{7,30}$")


def success(payload, status=200):
    return jsonify({"data": payload}), status


def error(message, status=400):
    return jsonify({"error": message}), status


def required_text(payload, field, label, maximum):
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required.")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{label} must be {maximum} characters or fewer.")
    return value


def optional_text(payload, field, label, maximum):
    value = payload.get(field, "")
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{label} must be {maximum} characters or fewer.")
    return value


def integer_id(payload, field, label):
    value = payload.get(field)
    try:
        if isinstance(value, bool):
            raise ValueError
        parsed = int(value)
        if isinstance(value, float) and not value.is_integer():
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError(f"Select a valid {label}.") from None
    if parsed < 1:
        raise ValueError(f"Select a valid {label}.")
    return parsed


def validate_department(payload):
    return {
        "name": required_text(payload, "name", "Department name", 100),
        "code": required_text(payload, "code", "Department code", 20).upper(),
        "description": optional_text(payload, "description", "Description", 500),
    }


def validate_course(payload):
    try:
        credits = int(payload.get("credits", 3))
    except (TypeError, ValueError):
        raise ValueError("Credits must be a whole number between 1 and 30.") from None
    if not 1 <= credits <= 30:
        raise ValueError("Credits must be a whole number between 1 and 30.")
    values = {
        "name": required_text(payload, "name", "Course name", 120),
        "code": required_text(payload, "code", "Course code", 20).upper(),
        "department_id": integer_id(payload, "department_id", "department"),
        "duration": optional_text(payload, "duration", "Duration", 80),
        "description": optional_text(payload, "description", "Description", 500),
        "credits": credits,
    }
    if not db.session.get(Department, values["department_id"]):
        raise ValueError("The selected department does not exist.")
    return values


def validate_student(payload):
    name = required_text(payload, "name", "Name", 120)
    email = required_text(payload, "email", "Email", 254).lower()
    phone = required_text(payload, "phone", "Phone", 30)
    if not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    if not PHONE_PATTERN.fullmatch(phone):
        raise ValueError("Enter a valid phone number.")

    department_id = integer_id(payload, "department_id", "department")
    course_id = integer_id(payload, "course_id", "course")
    department = db.session.get(Department, department_id)
    course = db.session.get(Course, course_id)
    if not department:
        raise ValueError("The selected department does not exist.")
    if not course:
        raise ValueError("The selected course does not exist.")
    if course.department_id != department_id:
        raise ValueError("The selected course does not belong to that department.")

    raw_date = payload.get("admission_date")
    try:
        admission_date = date.fromisoformat(raw_date)
    except (TypeError, ValueError):
        raise ValueError("Enter a valid admission date.") from None
    return {
        "name": name,
        "email": email,
        "phone": phone,
        "department_id": department_id,
        "course_id": course_id,
        "admission_date": admission_date,
    }


def commit_or_conflict():
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error(
            "That email, code, or name is already in use, or this record is still referenced.",
            409,
        )
    return None


@api.get("/health")
def health():
    return success({"status": "ok"})


@api.before_request
def enforce_api_authentication():
    if request.endpoint == "api.health" or request.method == "OPTIONS":
        return None
    user = getattr(g, "current_user", None)
    if not user:
        return error("Authentication required.", 401)
    if request.method not in {"GET", "HEAD", "OPTIONS"} and user.role != "admin":
        return error("Administrator access is required.", 403)
    return None


@api.get("/dashboard")
def dashboard():
    student_query = Student.query
    attendance_query = Attendance.query
    marks_query = Mark.query
    course_count = Course.query.count()
    department_count = Department.query.count()
    faculty_count = Faculty.query.count()
    if g.current_user.role == "student":
        student = g.current_user.student
        student_query = student_query.filter(Student.id == student.id)
        attendance_query = attendance_query.filter(Attendance.student_id == student.id)
        marks_query = marks_query.filter(Mark.student_id == student.id)
        course_count = 1
        department_count = 1
        faculty_count = 0
    elif g.current_user.role == "faculty":
        marks_query = marks_query.join(Subject).join(Subject.faculty).filter(
            Faculty.id == g.current_user.faculty_id
        )
    attendance_total = attendance_query.filter(
        Attendance.status.in_(("Present", "Absent", "Late"))
    ).count()
    attendance_present = attendance_query.filter(
        Attendance.status.in_(("Present", "Late"))
    ).count()
    marks = marks_query.all()
    students = student_query.order_by(Student.created_at.desc(), Student.id.desc())
    visible_students = students.all() if g.current_user.role == "student" else []
    return success(
        {
            "total_students": len(visible_students) if g.current_user.role == "student" else Student.query.count(),
            "active_students": sum(item.status == "Active" for item in visible_students) if g.current_user.role == "student" else Student.query.filter_by(status="Active").count(),
            "total_courses": course_count,
            "total_departments": department_count,
            "total_faculty": faculty_count,
            "attendance_percentage": round(
                attendance_present * 100 / attendance_total, 2
            ) if attendance_total else 0,
            "average_marks": round(
                sum(mark.percentage for mark in marks) / len(marks), 2
            ) if marks else 0,
            "recent_students": [
                student.to_dict()
                for student in students.limit(6).all()
            ],
        }
    )


@api.get("/students")
def list_students():
    query = Student.query
    if g.current_user.role == "student":
        query = query.filter(Student.id == g.current_user.student_id)
    search = request.args.get("search", "").strip()
    if search:
        pattern = f"%{search}%"
        query = query.join(Student.department).join(Student.course).filter(
            or_(
                Student.name.ilike(pattern),
                Student.student_number.ilike(pattern),
                Student.email.ilike(pattern),
                Student.phone.ilike(pattern),
                Department.name.ilike(pattern),
                Course.name.ilike(pattern),
            )
        )
    department_id = request.args.get("department_id")
    course_id = request.args.get("course_id")
    if department_id:
        query = query.filter(Student.department_id == department_id)
    if course_id:
        query = query.filter(Student.course_id == course_id)
    students = query.order_by(Student.created_at.desc(), Student.id.desc()).all()
    return success([student.to_dict() for student in students])


@api.post("/students")
def create_student():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("A JSON request body is required.")
    try:
        student = Student(
            **validate_student(payload),
            student_number=f"STU-{uuid.uuid4().hex[:12].upper()}",
        )
    except ValueError as exc:
        return error(str(exc))
    db.session.add(student)
    conflict = commit_or_conflict()
    if conflict:
        return conflict
    return success(student.to_dict(), 201)


@api.get("/students/<int:student_id>")
def get_student(student_id):
    student = db.session.get(Student, student_id)
    if not student or (
        g.current_user.role == "student" and student.id != g.current_user.student_id
    ):
        return error("Student not found.", 404)
    return success(student.to_dict())


@api.put("/students/<int:student_id>")
def update_student(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        return error("Student not found.", 404)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("A JSON request body is required.")
    try:
        values = validate_student(payload)
    except ValueError as exc:
        return error(str(exc))
    for field, value in values.items():
        setattr(student, field, value)
    conflict = commit_or_conflict()
    if conflict:
        return conflict
    return success(student.to_dict())


@api.delete("/students/<int:student_id>")
def delete_student(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        return error("Student not found.", 404)
    db.session.delete(student)
    conflict = commit_or_conflict()
    if conflict:
        return conflict
    return success({"message": "Student deleted."})


@api.get("/departments")
def list_departments():
    departments = Department.query.order_by(Department.name).all()
    return success([department.to_dict() for department in departments])


@api.post("/departments")
def create_department():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("A JSON request body is required.")
    try:
        department = Department(**validate_department(payload))
    except ValueError as exc:
        return error(str(exc))
    db.session.add(department)
    conflict = commit_or_conflict()
    if conflict:
        return conflict
    return success(department.to_dict(), 201)


@api.put("/departments/<int:department_id>")
def update_department(department_id):
    department = db.session.get(Department, department_id)
    if not department:
        return error("Department not found.", 404)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("A JSON request body is required.")
    try:
        values = validate_department(payload)
    except ValueError as exc:
        return error(str(exc))
    for field, value in values.items():
        setattr(department, field, value)
    conflict = commit_or_conflict()
    if conflict:
        return conflict
    return success(department.to_dict())


@api.delete("/departments/<int:department_id>")
def delete_department(department_id):
    department = db.session.get(Department, department_id)
    if not department:
        return error("Department not found.", 404)
    db.session.delete(department)
    conflict = commit_or_conflict()
    if conflict:
        return conflict
    return success({"message": "Department deleted."})


@api.get("/courses")
def list_courses():
    department_id = request.args.get("department_id")
    query = Course.query
    if department_id:
        query = query.filter(Course.department_id == department_id)
    courses = query.order_by(Course.name).all()
    return success([course.to_dict() for course in courses])


@api.post("/courses")
def create_course():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("A JSON request body is required.")
    try:
        course = Course(**validate_course(payload))
    except ValueError as exc:
        return error(str(exc))
    db.session.add(course)
    conflict = commit_or_conflict()
    if conflict:
        return conflict
    return success(course.to_dict(), 201)


@api.put("/courses/<int:course_id>")
def update_course(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        return error("Course not found.", 404)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("A JSON request body is required.")
    try:
        values = validate_course(payload)
    except ValueError as exc:
        return error(str(exc))
    for field, value in values.items():
        setattr(course, field, value)
    conflict = commit_or_conflict()
    if conflict:
        return conflict
    return success(course.to_dict())


@api.delete("/courses/<int:course_id>")
def delete_course(course_id):
    course = db.session.get(Course, course_id)
    if not course:
        return error("Course not found.", 404)
    db.session.delete(course)
    conflict = commit_or_conflict()
    if conflict:
        return conflict
    return success({"message": "Course deleted."})
