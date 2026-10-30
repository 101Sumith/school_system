from backend.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), unique=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculty.id"), unique=True)
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.current_timestamp()
    )
    student = db.relationship("Student")
    faculty = db.relationship("Faculty")

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "student_id": self.student_id,
            "faculty_id": self.faculty_id,
        }
