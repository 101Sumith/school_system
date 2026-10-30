from backend.extensions import db


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    code = db.Column(db.String(20), nullable=False, unique=True)
    description = db.Column(db.String(500), nullable=False, default="")
    courses = db.relationship("Course", back_populates="department", lazy=True)
    students = db.relationship("Student", back_populates="department", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "course_count": len(self.courses),
        }
