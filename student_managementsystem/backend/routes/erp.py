import csv
import io
import math
import re
import uuid
from datetime import date

from flask import Blueprint, Response, g, jsonify, request
from sqlalchemy.exc import IntegrityError

from backend.extensions import db
from backend.models import (
    Attendance,
    Course,
    Department,
    Exam,
    Faculty,
    Mark,
    Student,
    Subject,
    TimetableEntry,
)

erp = Blueprint("erp", __name__, url_prefix="/api")
TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
ATTENDANCE_STATUSES = {"Present", "Absent", "Late", "Excused"}
ASSESSMENT_TYPES = {"Internal", "Semester"}
EXAM_TYPES = {"Internal", "Semester", "Practical"}
RESOURCE_MODELS = {
    "faculty": Faculty,
    "subjects": Subject,
    "attendance": Attendance,
    "marks": Mark,
    "exams": Exam,
    "timetable": TimetableEntry,
}


def success(payload, status=200):
    return jsonify({"data": payload}), status


def error(message, status=400):
    return jsonify({"error": message}), status


def text_value(payload, key, label, maximum, optional=False):
    value = payload.get(key, "" if optional else None)
    if not isinstance(value, str) or (not optional and not value.strip()):
        raise ValueError(f"{label} is required.")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{label} must be {maximum} characters or fewer.")
    return value


def int_value(payload, key, label, minimum=1, maximum=None):
    try:
        raw_value = payload.get(key)
        if isinstance(raw_value, bool):
            raise ValueError
        value = int(raw_value)
        if isinstance(raw_value, float) and not raw_value.is_integer():
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.") from None
    if value < minimum or (maximum is not None and value > maximum):
        upper = f" and {maximum}" if maximum is not None else ""
        raise ValueError(f"{label} must be between {minimum}{upper}.")
    return value


def date_value(payload, key, label):
    try:
        return date.fromisoformat(payload.get(key, ""))
    except (TypeError, ValueError):
        raise ValueError(f"Enter a valid {label}.") from None


def valid_time(value, label):
    if not isinstance(value, str) or not TIME_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must use 24-hour HH:MM format.")
    return value


def related(model, identity, label):
    record = db.session.get(model, identity)
    if not record:
        raise ValueError(f"The selected {label} does not exist.")
    return record


def can_manage_subject(subject_id):
    user = g.current_user
    if user.role == "admin":
        return True
    if user.role == "faculty":
        faculty = user.faculty
        return bool(faculty and any(item.id == subject_id for item in faculty.subjects))
    return False


def scoped_query(resource, query):
    user = g.current_user
    if resource in {"attendance", "marks"}:
        if user.role == "student":
            return query.filter(
                RESOURCE_MODELS[resource].student_id == user.student_id
            )
        if user.role == "faculty":
            return query.join(Subject).join(Subject.faculty).filter(
                Faculty.id == user.faculty_id
            )
    if resource == "timetable":
        if user.role == "faculty":
            return query.filter(TimetableEntry.faculty_id == user.faculty_id)
        if user.role == "student":
            return query.join(Subject).filter(
                Subject.course_id == user.student.course_id
            )
    if resource == "faculty" and user.role == "faculty":
        return query.filter(Faculty.id == user.faculty_id)
    if resource == "faculty" and user.role == "student":
        return query.join(Faculty.subjects).join(Subject).filter(
            Subject.course_id == user.student.course_id
        )
    if resource == "subjects" and user.role == "student":
        return query.join(Course).filter(Course.id == user.student.course_id)
    if resource == "subjects" and user.role == "faculty":
        return query.join(Subject.faculty).filter(Faculty.id == user.faculty_id)
    if resource == "exams" and user.role == "student":
        return query.join(Subject).filter(Subject.course_id == user.student.course_id)
    if resource == "exams" and user.role == "faculty":
        return query.join(Subject).join(Subject.faculty).filter(
            Faculty.id == user.faculty_id
        )
    return query


def serialize_record(record):
    return record.to_dict()


def record_is_visible(resource, record):
    if g.current_user.role == "admin":
        return True
    return (
        scoped_query(resource, RESOURCE_MODELS[resource].query)
        .filter(RESOURCE_MODELS[resource].id == record.id)
        .first()
        is not None
    )


def validate_record(resource, payload):
    if not isinstance(payload, dict):
        raise ValueError("A JSON request body is required.")
    if resource == "faculty":
        department_id = int_value(payload, "department_id", "Department")
        related(Department, department_id, "department")
        email = text_value(payload, "email", "Email", 254).lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Enter a valid email address.")
        return {
            "employee_number": text_value(
                payload, "employee_number", "Employee number", 24, optional=True
            ) or f"FAC-{uuid.uuid4().hex[:10].upper()}",
            "name": text_value(payload, "name", "Name", 120),
            "email": email,
            "phone": text_value(payload, "phone", "Phone", 30, optional=True),
            "title": text_value(payload, "title", "Title", 100, optional=True),
            "department_id": department_id,
        }
    if resource == "subjects":
        course_id = int_value(payload, "course_id", "Course")
        related(Course, course_id, "course")
        try:
            credits = int_value(payload, "credits", "Credits", 1, 30)
            semester = int_value(payload, "semester", "Semester", 1, 16)
        except ValueError:
            raise
        faculty_ids = payload.get("faculty_ids", [])
        if not isinstance(faculty_ids, list):
            raise ValueError("Faculty allocation must be a list of IDs.")
        faculty_ids = list(dict.fromkeys(int(item) for item in faculty_ids))
        for faculty_id in faculty_ids:
            faculty = related(Faculty, faculty_id, "faculty member")
            if faculty.department_id != related(Course, course_id, "course").department_id:
                raise ValueError("Allocated faculty must belong to the course department.")
        return {
            "values": {
                "code": text_value(payload, "code", "Subject code", 24).upper(),
                "name": text_value(payload, "name", "Subject name", 120),
                "course_id": course_id,
                "credits": credits,
                "semester": semester,
            },
            "faculty_ids": faculty_ids,
        }
    if resource == "attendance":
        student = related(
            Student, int_value(payload, "student_id", "Student"), "student"
        )
        subject = related(
            Subject, int_value(payload, "subject_id", "Subject"), "subject"
        )
        if student.course_id != subject.course_id:
            raise ValueError("The subject does not belong to the student's course.")
        status = payload.get("status")
        if status not in ATTENDANCE_STATUSES:
            raise ValueError("Status must be Present, Absent, Late, or Excused.")
        return {
            "student_id": student.id,
            "subject_id": subject.id,
            "attendance_date": date_value(payload, "attendance_date", "attendance date"),
            "status": status,
        }
    if resource == "marks":
        student = related(
            Student, int_value(payload, "student_id", "Student"), "student"
        )
        subject = related(
            Subject, int_value(payload, "subject_id", "Subject"), "subject"
        )
        if student.course_id != subject.course_id:
            raise ValueError("The subject does not belong to the student's course.")
        assessment_type = payload.get("assessment_type")
        if assessment_type not in ASSESSMENT_TYPES:
            raise ValueError("Assessment type must be Internal or Semester.")
        try:
            marks_obtained = float(payload.get("marks_obtained"))
            max_marks = float(payload.get("max_marks", 100))
        except (ValueError, TypeError):
            raise ValueError("Marks must be valid numbers.") from None
        if (
            not math.isfinite(marks_obtained)
            or not math.isfinite(max_marks)
            or max_marks <= 0
            or marks_obtained < 0
            or marks_obtained > max_marks
        ):
            raise ValueError("Marks must be between zero and the maximum marks.")
        return {
            "student_id": student.id,
            "subject_id": subject.id,
            "semester": int_value(payload, "semester", "Semester", 1, 16),
            "assessment_type": assessment_type,
            "marks_obtained": marks_obtained,
            "max_marks": max_marks,
        }
    if resource == "exams":
        subject_id = int_value(payload, "subject_id", "Subject")
        related(Subject, subject_id, "subject")
        exam_type = payload.get("exam_type", "Semester")
        if exam_type not in EXAM_TYPES:
            raise ValueError("Exam type must be Internal, Semester, or Practical.")
        start = valid_time(payload.get("start_time"), "Start time")
        end = valid_time(payload.get("end_time"), "End time")
        if start >= end:
            raise ValueError("End time must be after start time.")
        return {
            "title": text_value(payload, "title", "Exam title", 120),
            "subject_id": subject_id,
            "exam_date": date_value(payload, "exam_date", "exam date"),
            "start_time": start,
            "end_time": end,
            "room": text_value(payload, "room", "Room", 80, optional=True),
            "exam_type": exam_type,
        }
    if resource == "timetable":
        subject_id = int_value(payload, "subject_id", "Subject")
        related(Subject, subject_id, "subject")
        faculty_id = payload.get("faculty_id")
        if faculty_id not in (None, ""):
            faculty_id = int_value(payload, "faculty_id", "Faculty")
            related(Faculty, faculty_id, "faculty member")
        else:
            faculty_id = None
        day = int_value(payload, "day_of_week", "Day", 0, 6)
        start = valid_time(payload.get("start_time"), "Start time")
        end = valid_time(payload.get("end_time"), "End time")
        if start >= end:
            raise ValueError("End time must be after start time.")
        return {
            "subject_id": subject_id,
            "faculty_id": faculty_id,
            "day_of_week": day,
            "start_time": start,
            "end_time": end,
            "room": text_value(payload, "room", "Room", 80, optional=True),
        }
    raise ValueError("Unknown ERP resource.")


def user_can_write(resource, payload):
    user = g.current_user
    if user.role == "admin":
        return True
    if user.role != "faculty" or resource not in {"attendance", "marks"}:
        return False
    try:
        subject_id = int(payload.get("subject_id"))
    except (TypeError, ValueError):
        return False
    return can_manage_subject(subject_id)


@erp.get("/faculty")
@erp.get("/subjects")
@erp.get("/attendance")
@erp.get("/marks")
@erp.get("/exams")
@erp.get("/timetable")
def list_records():
    resource = request.path.rsplit("/", 1)[-1]
    query = scoped_query(resource, RESOURCE_MODELS[resource].query)
    for key in ("student_id", "subject_id", "course_id", "faculty_id"):
        value = request.args.get(key)
        if value and hasattr(RESOURCE_MODELS[resource], key):
            query = query.filter(getattr(RESOURCE_MODELS[resource], key) == value)
    day = request.args.get("date")
    if day and resource == "attendance":
        try:
            query = query.filter(Attendance.attendance_date == date.fromisoformat(day))
        except ValueError:
            return error("Enter a valid date filter.")
    if day and resource == "exams":
        try:
            query = query.filter(Exam.exam_date == date.fromisoformat(day))
        except ValueError:
            return error("Enter a valid date filter.")
    if resource == "exams":
        query = query.order_by(Exam.exam_date, Exam.start_time)
    elif resource == "attendance":
        query = query.order_by(Attendance.attendance_date.desc(), Attendance.id.desc())
    else:
        query = query.order_by(RESOURCE_MODELS[resource].id.desc())
    return success([serialize_record(item) for item in query.all()])


@erp.post("/faculty")
@erp.post("/subjects")
@erp.post("/attendance")
@erp.post("/marks")
@erp.post("/exams")
@erp.post("/timetable")
def create_record():
    resource = request.path.rsplit("/", 1)[-1]
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error("A JSON request body is required.")
    if not user_can_write(resource, payload):
        return error("You do not have permission to create this record.", 403)
    try:
        values = validate_record(resource, payload)
        if resource == "subjects":
            faculty_ids = values.pop("faculty_ids")
            record = Subject(**values["values"])
            record.faculty = [related(Faculty, identity, "faculty member") for identity in faculty_ids]
        else:
            record = RESOURCE_MODELS[resource](**values)
        db.session.add(record)
        db.session.commit()
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        return error(str(exc))
    except IntegrityError:
        db.session.rollback()
        return error("A record with the same unique identifier already exists.", 409)
    return success(serialize_record(record), 201)


@erp.post("/attendance/bulk")
def create_attendance_batch():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        return error("Provide a records array for the attendance session.")
    if g.current_user.role not in {"admin", "faculty"}:
        return error("Faculty or administrator access is required.", 403)
    if not payload["records"] or len(payload["records"]) > 500:
        return error("A session must contain between 1 and 500 attendance records.")
    records = []
    try:
        for item in payload["records"]:
            values = validate_record("attendance", item)
            if not can_manage_subject(values["subject_id"]):
                return error("You are not allocated to the selected subject.", 403)
            records.append(Attendance(**values))
        db.session.add_all(records)
        db.session.commit()
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        return error(str(exc))
    except IntegrityError:
        db.session.rollback()
        return error("Attendance already exists for a student, subject, and date.", 409)
    return success([record.to_dict() for record in records], 201)


@erp.get("/<string:resource>/<int:record_id>")
def get_record(resource, record_id):
    if resource not in RESOURCE_MODELS:
        return error("Unknown ERP resource.", 404)
    record = db.session.get(RESOURCE_MODELS[resource], record_id)
    if not record or not record_is_visible(resource, record):
        return error("Record not found.", 404)
    return success(serialize_record(record))


@erp.put("/<string:resource>/<int:record_id>")
def update_record(resource, record_id):
    if resource not in RESOURCE_MODELS:
        return error("Unknown ERP resource.", 404)
    record = db.session.get(RESOURCE_MODELS[resource], record_id)
    if not record or not record_is_visible(resource, record):
        return error("Record not found.", 404)
    payload = request.get_json(silent=True)
    if not user_can_write(resource, payload or {}):
        return error("You do not have permission to update this record.", 403)
    try:
        values = validate_record(resource, payload)
        if resource == "subjects":
            faculty_ids = values.pop("faculty_ids")
            values = values["values"]
        else:
            faculty_ids = None
        for field, value in values.items():
            setattr(record, field, value)
        if faculty_ids is not None:
            record.faculty = [
                related(Faculty, identity, "faculty member") for identity in faculty_ids
            ]
        db.session.commit()
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        return error(str(exc))
    except IntegrityError:
        db.session.rollback()
        return error("A record with the same unique identifier already exists.", 409)
    return success(serialize_record(record))


@erp.delete("/<string:resource>/<int:record_id>")
def delete_record(resource, record_id):
    if resource not in RESOURCE_MODELS:
        return error("Unknown ERP resource.", 404)
    record = db.session.get(RESOURCE_MODELS[resource], record_id)
    if not record or not record_is_visible(resource, record):
        return error("Record not found.", 404)
    if not user_can_write(resource, {"subject_id": getattr(record, "subject_id", None)}):
        return error("You do not have permission to delete this record.", 403)
    db.session.delete(record)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error("This record is still referenced and cannot be deleted.", 409)
    return success({"message": "Record deleted."})


def marksheet(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        return None
    if g.current_user.role == "student" and student.id != g.current_user.student_id:
        return None
    marks_query = Mark.query.filter_by(student_id=student.id)
    attendance_query = Attendance.query.filter_by(student_id=student.id)
    if g.current_user.role == "faculty":
        marks_query = marks_query.join(Subject).join(Subject.faculty).filter(
            Faculty.id == g.current_user.faculty_id
        )
        attendance_query = attendance_query.join(Subject).join(Subject.faculty).filter(
            Faculty.id == g.current_user.faculty_id
        )
    marks = marks_query.order_by(
        Mark.semester, Mark.subject_id, Mark.assessment_type
    ).all()
    semester_marks = [mark for mark in marks if mark.assessment_type == "Semester"]
    finalized = {(mark.student_id, mark.subject_id, mark.semester) for mark in semester_marks}
    gpa_marks = semester_marks + [
        mark for mark in marks
        if mark.assessment_type == "Internal"
        and (mark.student_id, mark.subject_id, mark.semester) not in finalized
    ]
    credits = sum(mark.subject.credits for mark in gpa_marks)
    gpa = (
        round(
            sum(mark.grade_points * mark.subject.credits for mark in gpa_marks) / credits,
            2,
        )
        if credits else 0
    )
    attendance = attendance_query.all()
    attendance_classes = [
        item for item in attendance if item.status in {"Present", "Absent", "Late"}
    ]
    attendance_percentage = round(
        sum(item.status in {"Present", "Late"} for item in attendance_classes)
        * 100 / len(attendance_classes),
        2,
    ) if attendance_classes else 0
    return {
        "student": student.to_dict(),
        "gpa": gpa,
        "total_credits": credits,
        "attendance_percentage": attendance_percentage,
        "marks": [mark.to_dict() for mark in marks],
    }


@erp.get("/students/<int:student_id>/marksheet")
def get_marksheet(student_id):
    report = marksheet(student_id)
    if not report:
        return error("Student marksheet not found.", 404)
    return success(report)


@erp.get("/students/by-number/<string:student_number>")
def get_student_by_number(student_number):
    student = Student.query.filter_by(student_number=student_number).first()
    if not student or (
        g.current_user.role == "student" and student.id != g.current_user.student_id
    ):
        return error("Student not found.", 404)
    return success(student.to_dict())


@erp.get("/attendance/summary")
def attendance_summary():
    query = scoped_query("attendance", Attendance.query)
    for key in ("student_id", "subject_id"):
        value = request.args.get(key)
        if value:
            query = query.filter(getattr(Attendance, key) == value)
    start = request.args.get("from")
    end = request.args.get("to")
    try:
        if start:
            query = query.filter(
                Attendance.attendance_date >= date.fromisoformat(start)
            )
        if end:
            query = query.filter(
                Attendance.attendance_date <= date.fromisoformat(end)
            )
    except ValueError:
        return error("Attendance date filters must be valid dates.")
    grouped = {}
    for record in query.all():
        key = (record.student_id, record.subject_id)
        item = grouped.setdefault(
            key,
            {
                "student_id": record.student_id,
                "student_number": record.student.student_number,
                "student_name": record.student.name,
                "subject_id": record.subject_id,
                "subject_name": record.subject.name,
                "classes": 0,
                "attended": 0,
            },
        )
        if record.status in {"Present", "Absent", "Late"}:
            item["classes"] += 1
            item["attended"] += record.status in {"Present", "Late"}
    result = []
    for item in grouped.values():
        item["percentage"] = round(
            item["attended"] * 100 / item["classes"], 2
        ) if item["classes"] else 0
        result.append(item)
    return success(result)


def report_rows(report_type):
    user = g.current_user
    if report_type == "attendance":
        query = Attendance.query
        if user.role == "student":
            query = query.filter_by(student_id=user.student_id)
        elif user.role == "faculty":
            query = query.join(Subject).join(Subject.faculty).filter(Faculty.id == user.faculty_id)
        start = request.args.get("from")
        end = request.args.get("to")
        if start:
            query = query.filter(Attendance.attendance_date >= date.fromisoformat(start))
        if end:
            query = query.filter(Attendance.attendance_date <= date.fromisoformat(end))
        rows = query.order_by(Attendance.attendance_date, Attendance.id).all()
        return (
            ["student_number", "student", "subject", "date", "status"],
            [[row.student.student_number, row.student.name, row.subject.name, row.attendance_date.isoformat(), row.status] for row in rows],
        )
    query = Mark.query
    if user.role == "student":
        query = query.filter_by(student_id=user.student_id)
    elif user.role == "faculty":
        query = query.join(Subject).join(Subject.faculty).filter(Faculty.id == user.faculty_id)
    rows = query.order_by(Mark.semester, Mark.student_id, Mark.subject_id).all()
    return (
        ["student_number", "student", "subject", "semester", "type", "marks", "maximum", "percentage", "grade", "grade_points"],
        [[row.student.student_number, row.student.name, row.subject.name, row.semester, row.assessment_type, row.marks_obtained, row.max_marks, row.percentage, row.grade, row.grade_points] for row in rows],
    )


def render_pdf(lines):
    wrapped = []
    for line in lines:
        value = str(line).encode("ascii", "replace").decode("ascii")
        wrapped.extend(value[index:index + 105] for index in range(0, len(value), 105))
    pages = [wrapped[index:index + 58] for index in range(0, len(wrapped), 58)] or [[]]
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    font_id = 3
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids = []
    for lines_on_page in pages:
        page_id = len(objects) + 1
        content_id = page_id + 1
        page_ids.append(page_id)
        content = "BT /F1 9 Tf 40 800 Td 12 TL " + " ".join(
            "(" + line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") Tj T*"
            for line in lines_on_page
        ) + " ET"
        stream = content.encode("ascii")
        objects.extend(
            [
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>".encode("ascii"),
                f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream",
            ]
        )
    objects[1] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{page_id} 0 R' for page_id in page_ids)}] "
        f"/Count {len(page_ids)} >>"
    ).encode("ascii")
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("ascii"))
    return bytes(output)


@erp.get("/reports/<string:report_type>.<string:format>")
def export_report(report_type, format):
    if report_type not in {"attendance", "performance"} or format not in {"csv", "pdf"}:
        return error("Choose attendance or performance in CSV or PDF format.", 404)
    try:
        headers, rows = report_rows(report_type)
    except ValueError:
        return error("Report date filters must be valid dates.")
    if format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)
        return Response(
            stream.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={report_type}-report.csv"},
        )
    lines = [f"Campus {report_type.title()} Report", ", ".join(headers)]
    lines.extend([", ".join(map(str, row)) for row in rows])
    return Response(
        render_pdf(lines),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={report_type}-report.pdf"},
    )
