from sqlalchemy import inspect, text

from backend.extensions import db


def migrate_existing_schema():
    inspector = inspect(db.engine)
    if "students" in inspector.get_table_names():
        student_columns = {column["name"] for column in inspector.get_columns("students")}
        if "student_number" not in student_columns:
            db.session.execute(
                text("ALTER TABLE students ADD COLUMN student_number VARCHAR(24)")
            )
            db.session.execute(
                text(
                    "UPDATE students SET student_number = "
                    "'STU-LEGACY-' || printf('%06d', id) "
                    "WHERE student_number IS NULL"
                )
                if db.engine.dialect.name == "sqlite"
                else text(
                    "UPDATE students SET student_number = "
                    "'STU-LEGACY-' || id::text "
                    "WHERE student_number IS NULL"
                )
            )
    inspector = inspect(db.engine)
    if "courses" in inspector.get_table_names():
        course_columns = {column["name"] for column in inspector.get_columns("courses")}
        if "credits" not in course_columns:
            db.session.execute(
                text("ALTER TABLE courses ADD COLUMN credits INTEGER NOT NULL DEFAULT 3")
            )
    db.session.commit()
    if "students" in inspect(db.engine).get_table_names():
        db.session.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "uq_students_student_number ON students (student_number)"
            )
        )
        db.session.commit()
