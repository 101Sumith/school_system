from backend.extensions import db

subject_faculty = db.Table(
    "subject_faculty",
    db.Column("subject_id", db.Integer, db.ForeignKey("subjects.id"), primary_key=True),
    db.Column("faculty_id", db.Integer, db.ForeignKey("faculty.id"), primary_key=True),
)


class Faculty(db.Model):
    __tablename__ = "faculty"

    id = db.Column(db.Integer, primary_key=True)
    employee_number = db.Column(db.String(24), nullable=False, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(30), nullable=False, default="")
    title = db.Column(db.String(100), nullable=False, default="")
    department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), nullable=False, index=True
    )
    department = db.relationship("Department")
    subjects = db.relationship(
        "Subject", secondary=subject_faculty, back_populates="faculty"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "employee_number": self.employee_number,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "title": self.title,
            "department_id": self.department_id,
            "department_name": self.department.name,
            "subjects": [{"id": item.id, "name": item.name} for item in self.subjects],
        }


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(24), nullable=False, unique=True)
    name = db.Column(db.String(120), nullable=False)
    course_id = db.Column(
        db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True
    )
    credits = db.Column(db.Integer, nullable=False, default=3)
    semester = db.Column(db.Integer, nullable=False, default=1)
    course = db.relationship("Course")
    faculty = db.relationship(
        "Faculty", secondary=subject_faculty, back_populates="subjects"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "course_id": self.course_id,
            "course_name": self.course.name,
            "department_id": self.course.department_id,
            "credits": self.credits,
            "semester": self.semester,
            "faculty": [{"id": item.id, "name": item.name} for item in self.faculty],
            "faculty_ids": [item.id for item in self.faculty],
        }


class Attendance(db.Model):
    __tablename__ = "attendance"
    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "subject_id", "attendance_date", name="uq_attendance_day"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id"), nullable=False, index=True
    )
    subject_id = db.Column(
        db.Integer, db.ForeignKey("subjects.id"), nullable=False, index=True
    )
    attendance_date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False)
    student = db.relationship("Student")
    subject = db.relationship("Subject")

    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "student_number": self.student.student_number,
            "student_name": self.student.name,
            "subject_id": self.subject_id,
            "subject_name": self.subject.name,
            "course_id": self.subject.course_id,
            "attendance_date": self.attendance_date.isoformat(),
            "status": self.status,
        }


class Mark(db.Model):
    __tablename__ = "marks"
    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "subject_id", "semester", "assessment_type",
            name="uq_student_subject_assessment",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id"), nullable=False, index=True
    )
    subject_id = db.Column(
        db.Integer, db.ForeignKey("subjects.id"), nullable=False, index=True
    )
    semester = db.Column(db.Integer, nullable=False)
    assessment_type = db.Column(db.String(20), nullable=False)
    marks_obtained = db.Column(db.Float, nullable=False)
    max_marks = db.Column(db.Float, nullable=False, default=100)
    student = db.relationship("Student")
    subject = db.relationship("Subject")

    @property
    def percentage(self):
        return round(self.marks_obtained * 100 / self.max_marks, 2)

    @property
    def grade(self):
        score = self.percentage
        if score >= 90:
            return "A+"
        if score >= 80:
            return "A"
        if score >= 70:
            return "B"
        if score >= 60:
            return "C"
        if score >= 50:
            return "D"
        return "F"

    @property
    def grade_points(self):
        return max(0, min(10, round(self.percentage / 10, 2)))

    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "student_number": self.student.student_number,
            "student_name": self.student.name,
            "subject_id": self.subject_id,
            "subject_name": self.subject.name,
            "credits": self.subject.credits,
            "semester": self.semester,
            "assessment_type": self.assessment_type,
            "marks_obtained": self.marks_obtained,
            "max_marks": self.max_marks,
            "percentage": self.percentage,
            "grade": self.grade,
            "grade_points": self.grade_points,
        }


class Exam(db.Model):
    __tablename__ = "exams"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    subject_id = db.Column(
        db.Integer, db.ForeignKey("subjects.id"), nullable=False, index=True
    )
    exam_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    room = db.Column(db.String(80), nullable=False, default="")
    exam_type = db.Column(db.String(20), nullable=False, default="Semester")
    subject = db.relationship("Subject")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "subject_id": self.subject_id,
            "subject_name": self.subject.name,
            "course_name": self.subject.course.name,
            "exam_date": self.exam_date.isoformat(),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "room": self.room,
            "exam_type": self.exam_type,
        }


class TimetableEntry(db.Model):
    __tablename__ = "timetable"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(
        db.Integer, db.ForeignKey("subjects.id"), nullable=False, index=True
    )
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), index=True)
    day_of_week = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    room = db.Column(db.String(80), nullable=False, default="")
    subject = db.relationship("Subject")
    faculty = db.relationship("Faculty")

    def to_dict(self):
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "subject_name": self.subject.name,
            "course_name": self.subject.course.name,
            "faculty_id": self.faculty_id,
            "faculty_name": self.faculty.name if self.faculty else "",
            "day_of_week": self.day_of_week,
            "day": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][self.day_of_week],
            "start_time": self.start_time,
            "end_time": self.end_time,
            "room": self.room,
        }
