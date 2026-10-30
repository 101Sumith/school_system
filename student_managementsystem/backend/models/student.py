from backend.extensions import db


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    student_number = db.Column(db.String(24), nullable=False, unique=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(30), nullable=False)
    department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), nullable=False, index=True
    )
    course_id = db.Column(
        db.Integer, db.ForeignKey("courses.id"), nullable=False, index=True
    )
    admission_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Active")
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.current_timestamp()
    )
    department = db.relationship("Department", back_populates="students")
    course = db.relationship("Course", back_populates="students")

    def to_dict(self):
        return {
            "id": self.id,
            "student_number": self.student_number,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "department_id": self.department_id,
            "department_name": self.department.name,
            "course_id": self.course_id,
            "course_name": self.course.name,
            "admission_date": self.admission_date.isoformat(),
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
