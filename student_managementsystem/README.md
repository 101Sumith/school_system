# Campus — Students Management System

A responsive college ERP that extends the existing Campus student system. It uses Flask REST APIs, SQLAlchemy, SQLite locally, and PostgreSQL in production.

## Features

- Dashboard with student, faculty, course, attendance, average-mark, and department totals.
- Student profiles and unique student numbers; search, register, update, and delete.
- Faculty profiles and subject allocations; course and department management.
- Subject-wise attendance, daily/bulk attendance, and automatic attendance summaries.
- Internal/semester marks, grades, GPA, and student marksheets.
- Exam schedules, weekly timetables, and attendance/performance CSV/PDF exports.
- Admin, faculty, and student sign-in with expiring bearer tokens and role-scoped access.
- Server-side validation, duplicate detection, CORS, and JSON errors.
- Responsive desktop and mobile layouts.

## Project structure

```text
api/index.py                 Vercel Python function entry point
backend/app.py               Flask application factory and local entry point
backend/config.py            Database environment configuration
backend/extensions.py        Shared SQLAlchemy extension
backend/models/              Student, course, department, and ERP models
backend/routes/api.py        Dashboard and legacy student/course APIs
backend/routes/erp.py        Faculty, subjects, attendance, marks, exams, reports
backend/routes/auth.py       Bootstrap, sign-in, and user-account APIs
backend/migrations.py        Additive upgrades for existing databases
backend/security.py          Password hashes, bearer tokens, and role guards
frontend/                    Static HTML, CSS, and JavaScript
postman/                      Postman collection
requirements.txt
vercel.json
```

## Run locally

1. Use Python 3.10 or later and create/activate a virtual environment.
2. Install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. Optionally copy `.env.example` to `.env`. The application does not load `.env` automatically; set environment variables in your terminal or VS Code launch configuration. Without `DATABASE_URL`, SQLite is created at `instance/students.db`. Set `SECRET_KEY` and `ERP_BOOTSTRAP_TOKEN` for local use:

   ```powershell
   $env:SECRET_KEY = "a-long-random-secret"
   $env:ERP_BOOTSTRAP_TOKEN = "a-separate-one-time-bootstrap-secret"
   ```
4. Start the server:

   ```powershell
   python -m backend.app
   ```

5. Open <http://127.0.0.1:5000>. The API is available at <http://127.0.0.1:5000/api>.

The database tables are created at startup. Existing SQLite records are preserved: startup adds the new student-number/course-credit columns and assigns `STU-LEGACY-...` IDs to existing students. New student numbers are unique. Existing database snapshots should still be backed up before production schema changes.

### First administrator and user accounts

The application does not ship with default credentials or public sign-up. Set a private bootstrap token, then create the first administrator once:

```powershell
$headers = @{ "X-Bootstrap-Token" = $env:ERP_BOOTSTRAP_TOKEN }
$body = @{ email = "admin@your-college.edu"; password = "Use-A-Unique-Password-12+" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/auth/bootstrap -Headers $headers -ContentType "application/json" -Body $body
```

Sign in at the Campus page. An administrator creates faculty/student accounts with `POST /api/auth/users`; their account email must match the linked faculty/student profile. Passwords must be at least 12 characters. The bootstrap endpoint becomes permanently unavailable once an account exists. After bootstrapping production, remove `ERP_BOOTSTRAP_TOKEN` from Vercel settings.

## REST API

Except for health, login and one-time bootstrap, APIs require `Authorization: Bearer <token>`. Successful JSON responses have a `data` property; errors have an `error` message. Passwords are stored as scrypt hashes. Tokens expire after `TOKEN_MAX_AGE_SECONDS` (default 8 hours). Students can only access their own profile, attendance, marks and reports; faculty access is limited to allocated subjects for academic records.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Health check |
| POST | `/api/auth/bootstrap` | One-time first-admin setup (`X-Bootstrap-Token`) |
| POST | `/api/auth/login` | Sign in; returns a bearer token |
| GET | `/api/auth/me` | Current account |
| GET / POST | `/api/auth/users` | Admin: list/create role accounts |
| DELETE | `/api/auth/users/{id}` | Admin: delete an account |
| GET | `/api/dashboard` | Dashboard totals and recent registrations |
| GET | `/api/students?search=&department_id=` | List/search students (supports unique student number) |
| POST | `/api/students` | Register a student |
| GET | `/api/students/{id}` | Student profile |
| PUT | `/api/students/{id}` | Update a student |
| DELETE | `/api/students/{id}` | Delete a student |
| GET | `/api/students/by-number/{student_number}` | Find by unique student number |
| GET | `/api/students/{id}/marksheet` | Marks, grades, GPA and attendance summary |
| GET / POST | `/api/departments` | List or create departments |
| PUT / DELETE | `/api/departments/{id}` | Update or delete a department |
| GET / POST | `/api/courses?department_id=` | List or create courses (with credits) |
| PUT / DELETE | `/api/courses/{id}` | Update or delete a course |
| GET / POST | `/api/faculty` | List or create faculty |
| GET / PUT / DELETE | `/api/faculty/{id}` | Read, update or delete faculty |
| GET / POST | `/api/subjects` | List or create subjects with credits and faculty allocation |
| GET / PUT / DELETE | `/api/subjects/{id}` | Read, update or delete a subject |
| GET / POST | `/api/attendance` | List or record daily subject attendance |
| POST | `/api/attendance/bulk` | Record a subject/day session (up to 500 students) |
| GET | `/api/attendance/summary` | Per-student, per-subject attendance percentages |
| GET / PUT / DELETE | `/api/attendance/{id}` | Read, update or delete an attendance record |
| GET / POST | `/api/marks` | List or record internal/semester marks |
| GET / PUT / DELETE | `/api/marks/{id}` | Read, update or delete marks |
| GET / POST | `/api/exams` | List or schedule exams |
| GET / PUT / DELETE | `/api/exams/{id}` | Read, update or delete exam schedules |
| GET / POST | `/api/timetable` | List or create weekly class sessions |
| GET / PUT / DELETE | `/api/timetable/{id}` | Read, update or delete a class session |
| GET | `/api/reports/attendance.csv` or `.pdf` | Export attendance records |
| GET | `/api/reports/performance.csv` or `.pdf` | Export marks and grades |

`POST /api/attendance/bulk` example:

```json
{
  "records": [
    { "student_id": 1, "subject_id": 1, "attendance_date": "2026-10-30", "status": "Present" },
    { "student_id": 2, "subject_id": 1, "attendance_date": "2026-10-30", "status": "Absent" }
  ]
}
```

Attendance is unique per student, subject and day. `Excused` records do not count in the attendance-percentage denominator; `Present` and `Late` count as attended. Duplicate attendance and duplicate student emails are rejected.

Example student body:

```json
{
  "name": "Alex Morgan",
  "email": "alex@example.edu",
  "phone": "+1 555 010 2040",
  "department_id": 1,
  "course_id": 1,
  "admission_date": "2026-09-01"
}
```

Student, course and department request bodies and runnable requests are in [postman/students-management.postman_collection.json](postman/students-management.postman_collection.json). Set the collection's `token` variable from the login response; set `bootstrapToken` before initial setup. The Postman collection includes role and ERP module requests.

## Database configuration

- **Local:** leave `DATABASE_URL` unset to use `instance/students.db`.
- **Production:** set `DATABASE_URL` to a PostgreSQL connection string, for example `postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require`. Legacy `postgres://` URLs are normalized automatically.
- Set a unique random `SECRET_KEY` and private `ERP_BOOTSTRAP_TOKEN`; do not commit secrets. `.env.example` is a template and is not loaded automatically.

Tables are created at app startup. Startup schema upgrades are additive for the pre-existing SQLite student and course tables; they do not delete records.

## Deploy to Vercel

1. Push the existing project to GitHub and import that repository into Vercel. `api/index.py` is the Python function entry point; `vercel.json` sends `/api/*` to it and serves the existing `frontend/` files.
2. Provision a persistent PostgreSQL database (Vercel Postgres or another PostgreSQL provider) and copy its SSL-enabled connection URL.
3. In Vercel **Project → Settings → Environment Variables**, add `DATABASE_URL`, `SECRET_KEY` (generate with `python -c "import secrets; print(secrets.token_hex(32))"`), and a separate random `ERP_BOOTSTRAP_TOKEN`. Apply them to Production (and Preview if used).
4. Deploy. The app creates/upgrades database tables at startup. Set the same environment variables for Preview deployments before testing them.
5. Create the first admin once by POSTing to `https://YOUR-DOMAIN/api/auth/bootstrap` with header `X-Bootstrap-Token: YOUR_BOOTSTRAP_TOKEN` and JSON `{ "email": "admin@your-college.edu", "password": "a-unique-password-of-at-least-12-characters" }`.
6. Remove `ERP_BOOTSTRAP_TOKEN` from Vercel after the first admin exists, then redeploy. Admins can create faculty/student accounts from `POST /api/auth/users` (Postman collection).

Serverless instances are ephemeral: deployed startup requires PostgreSQL `DATABASE_URL` and `SECRET_KEY`; do not rely on SQLite for persistent data. The database must accept Vercel function connections; use the provider's serverless/pooling connection URL if needed. Vercel deployments were not performed as part of local API testing.

## API testing with Postman

Import `postman/students-management.postman_collection.json`. Set `baseUrl` to `http://127.0.0.1:5000` or your Vercel URL. Set the one-time `bootstrapToken`, run administrator bootstrap once, then sign in and set the returned token. The collection covers the ERP APIs and role accounts.
