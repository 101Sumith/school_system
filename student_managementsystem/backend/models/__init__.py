from backend.models.course import Course
from backend.models.department import Department
from backend.models.erp import Attendance, Exam, Faculty, Mark, Subject, TimetableEntry
from backend.models.student import Student
from backend.models.user import User

__all__ = [
    "Attendance", "Course", "Department", "Exam", "Faculty", "Mark",
    "Student", "Subject", "TimetableEntry", "User",
]
