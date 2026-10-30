from backend.extensions import db


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    code = db.Column(db.String(20), nullable=False, unique=True)
    department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), nullable=False, index=True
    )
    duration = db.Column(db.String(80), nullable=False, default="")
    description = db.Column(db.String(500), nullable=False, default="")
    credits = db.Column(db.Integer, nullable=False, default=3)
    department = db.relationship("Department", back_populates="courses")
    students = db.relationship("Student", back_populates="course", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "department_id": self.department_id,
            "department_name": self.department.name,
            "duration": self.duration,
            "description": self.description,
            "credits": self.credits,
            "student_count": len(self.students),
        }
