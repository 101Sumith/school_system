const API_BASE = "/api";
const state = {
  students: [], departments: [], courses: [], faculty: [], subjects: [],
  records: [], view: "dashboard", user: null,
};
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

async function api(path, options = {}) {
  const token = sessionStorage.getItem("campus-token");
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401 && token) {
    sessionStorage.removeItem("campus-token");
    sessionStorage.removeItem("campus-user");
    state.user = null;
    $("#auth-screen").classList.remove("hidden");
  }
  if (!response.ok) throw new Error(payload.error || "Something went wrong. Please try again.");
  return payload.data;
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function initials(name = "") {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0] || "").join("").toUpperCase();
}

function formattedDate(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(`${value}T00:00:00`));
}

function showToast(message, isError = false) {
  const toast = document.createElement("div");
  toast.className = `toast${isError ? " error" : ""}`;
  toast.textContent = message;
  $("#toast-region").append(toast);
  window.setTimeout(() => toast.remove(), 3500);
}

async function loadDashboard() {
  const data = await api("/dashboard");
  $("#stat-students").textContent = data.total_students;
  $("#stat-active").textContent = data.active_students;
  $("#stat-faculty").textContent = data.total_faculty;
  $("#stat-courses").textContent = data.total_courses;
  $("#stat-attendance").textContent = `${data.attendance_percentage}%`;
  $("#stat-average-marks").textContent = `${data.average_marks}%`;
  $("#stat-departments").textContent = data.total_departments;
  $("#student-nav-count").textContent = data.total_students;
  renderRecent(data.recent_students);
}

function renderRecent(students) {
  const body = $("#recent-students");
  body.innerHTML = students.map((student, index) => `
    <tr>
      <td><div class="student-cell"><span class="avatar avatar-student tone-${index % 4}">${escapeHtml(initials(student.name))}</span><span><strong>${escapeHtml(student.name)}</strong><small>${escapeHtml(student.email)}</small></span></div></td>
      <td>${escapeHtml(student.course_name)}</td><td>${formattedDate(student.admission_date)}</td>
      <td><span class="status-pill">${escapeHtml(student.status)}</span></td>
    </tr>`).join("");
  $("#recent-empty").classList.toggle("hidden", students.length > 0);
  $(".recent-panel .table-wrap").classList.toggle("hidden", students.length === 0);
}

async function loadReferenceData() {
  const [departments, courses, students, faculty, subjects] = await Promise.all([
    api("/departments"), api("/courses"), api("/students"), api("/faculty"), api("/subjects"),
  ]);
  state.departments = departments;
  state.courses = courses;
  state.students = students;
  state.faculty = faculty;
  state.subjects = subjects;
  renderDepartments();
  renderCourses();
  const filter = $("#student-department-filter");
  const selected = filter.value;
  filter.innerHTML = `<option value="">All departments</option>${departments.map((department) =>
    `<option value="${department.id}">${escapeHtml(department.name)}</option>`).join("")}`;
  filter.value = selected;
}

async function loadStudents() {
  const params = new URLSearchParams();
  const search = $("#student-search").value.trim();
  const departmentId = $("#student-department-filter").value;
  if (search) params.set("search", search);
  if (departmentId) params.set("department_id", departmentId);
  state.students = await api(`/students${params.size ? `?${params}` : ""}`);
  renderStudents();
}

function renderStudents() {
  const body = $("#students-table");
  const canEdit = state.user?.role === "admin";
  body.innerHTML = state.students.map((student, index) => `
    <tr>
      <td><div class="student-cell"><span class="avatar avatar-student tone-${index % 4}">${escapeHtml(initials(student.name))}</span><span><strong>${escapeHtml(student.name)}</strong><small>${escapeHtml(student.student_number)} · ${escapeHtml(student.email)}</small></span></div></td>
      <td>${escapeHtml(student.phone)}</td><td>${escapeHtml(student.department_name)}</td><td>${escapeHtml(student.course_name)}</td><td>${formattedDate(student.admission_date)}</td>
      <td><span class="status-pill">${escapeHtml(student.status)}</span></td>
      <td><div class="row-actions"><button class="icon-button" data-action="profile-student" data-id="${student.id}" aria-label="View ${escapeHtml(student.name)}">↗</button>${canEdit ? `<button class="icon-button" data-action="edit-student" data-id="${student.id}" aria-label="Edit ${escapeHtml(student.name)}">✎</button><button class="icon-button" data-action="delete-student" data-id="${student.id}" aria-label="Delete ${escapeHtml(student.name)}">×</button>` : ""}</div></td>
    </tr>`).join("");
  $("#student-count").textContent = state.students.length;
  $("#students-empty").classList.toggle("hidden", state.students.length > 0);
  $(".directory-panel .table-wrap").classList.toggle("hidden", state.students.length === 0);
}

function renderCourses() {
  $("#course-count").textContent = state.courses.length;
  const adminActions = state.user?.role === "admin";
  $("#courses-grid").innerHTML = state.courses.map((course) => `
    <article class="collection-card">
      <div class="collection-card-top"><span class="collection-icon">▤</span><div class="collection-actions">${adminActions ? `<button class="icon-button" data-action="edit-course" data-id="${course.id}" aria-label="Edit ${escapeHtml(course.name)}">✎</button><button class="icon-button" data-action="delete-course" data-id="${course.id}" aria-label="Delete ${escapeHtml(course.name)}">×</button>` : ""}</div></div>
      <h3>${escapeHtml(course.name)}</h3><span class="collection-code">${escapeHtml(course.code)}</span>
      <p>${escapeHtml(course.description || "A course in the " + course.department_name + " department.")}</p>
      <div class="collection-meta"><span>${escapeHtml(course.department_name)}</span><span>${course.credits} credits · ${course.student_count} ${course.student_count === 1 ? "student" : "students"}</span></div>
    </article>`).join("");
  $("#courses-empty").classList.toggle("hidden", state.courses.length > 0);
  $("#courses-grid").classList.toggle("hidden", state.courses.length === 0);
}

function renderDepartments() {
  $("#department-count").textContent = state.departments.length;
  const adminActions = state.user?.role === "admin";
  $("#departments-grid").innerHTML = state.departments.map((department) => `
    <article class="collection-card">
      <div class="collection-card-top"><span class="collection-icon">▦</span><div class="collection-actions">${adminActions ? `<button class="icon-button" data-action="edit-department" data-id="${department.id}" aria-label="Edit ${escapeHtml(department.name)}">✎</button><button class="icon-button" data-action="delete-department" data-id="${department.id}" aria-label="Delete ${escapeHtml(department.name)}">×</button>` : ""}</div></div>
      <h3>${escapeHtml(department.name)}</h3><span class="collection-code">${escapeHtml(department.code)}</span>
      <p>${escapeHtml(department.description || "An academic department at your campus.")}</p>
      <div class="collection-meta"><span>${department.course_count} ${department.course_count === 1 ? "course" : "courses"}</span><span></span></div>
    </article>`).join("");
  $("#departments-empty").classList.toggle("hidden", state.departments.length > 0);
  $("#departments-grid").classList.toggle("hidden", state.departments.length === 0);
}

const MODULES = {
  faculty: {
    title: "Faculty", eyebrow: "YOUR TEACHING TEAM", plural: "Faculty members",
    description: "Manage faculty profiles and allocated subjects.", resource: "faculty",
    columns: [["employee_number", "FACULTY ID"], ["name", "NAME"], ["email", "EMAIL"], ["phone", "PHONE"], ["department_name", "DEPARTMENT"], ["title", "TITLE"], ["faculty_names", "SUBJECTS"]],
    fields: [
      ["employee_number", "Faculty ID", "text", [], false], ["name", "Full name", "text"],
      ["email", "Email address", "email"], ["phone", "Phone", "tel", [], false],
      ["title", "Title", "text", [], false], ["department_id", "Department", "select", "departments"],
    ],
  },
  subjects: {
    title: "Subjects", eyebrow: "COURSE CURRICULUM", plural: "Subjects",
    description: "Manage subject credits, semesters and faculty allocation.", resource: "subjects",
    columns: [["code", "CODE"], ["name", "SUBJECT"], ["course_name", "COURSE"], ["credits", "CREDITS"], ["semester", "SEMESTER"], ["faculty_names", "FACULTY"]],
    fields: [
      ["code", "Subject code", "text"], ["name", "Subject name", "text"],
      ["course_id", "Course", "select", "courses"], ["credits", "Credits", "number"],
      ["semester", "Semester", "number"], ["faculty_ids", "Allocated faculty", "multiselect", "faculty", false],
    ],
  },
  attendance: {
    title: "Attendance", eyebrow: "DAILY CLASS RECORDS", plural: "Attendance records",
    description: "Record and review daily, subject-wise attendance.", resource: "attendance",
    columns: [["student_number", "STUDENT ID"], ["student_name", "STUDENT"], ["subject_name", "SUBJECT"], ["attendance_date", "DATE"], ["status", "STATUS"]],
    fields: [
      ["student_id", "Student", "select", "students"], ["subject_id", "Subject", "select", "subjects"],
      ["attendance_date", "Attendance date", "date"], ["status", "Status", "select", "attendance-status"],
    ],
  },
  marks: {
    title: "Marks & results", eyebrow: "ACADEMIC PERFORMANCE", plural: "Assessment results",
    description: "Record internal and semester marks, grades and GPA.", resource: "marks",
    columns: [["student_number", "STUDENT ID"], ["student_name", "STUDENT"], ["subject_name", "SUBJECT"], ["semester", "SEMESTER"], ["assessment_type", "TYPE"], ["marks_obtained", "MARKS"], ["percentage", "SCORE"], ["grade", "GRADE"], ["grade_points", "GPA"]],
    fields: [
      ["student_id", "Student", "select", "students"], ["subject_id", "Subject", "select", "subjects"],
      ["semester", "Semester", "number"], ["assessment_type", "Assessment type", "select", "assessment-types"],
      ["marks_obtained", "Marks obtained", "number"], ["max_marks", "Maximum marks", "number", [], false],
    ],
  },
  exams: {
    title: "Examinations", eyebrow: "EXAM SCHEDULE", plural: "Scheduled exams",
    description: "Schedule internal, practical and semester examinations.", resource: "exams",
    columns: [["title", "EXAM"], ["subject_name", "SUBJECT"], ["exam_date", "DATE"], ["start_time", "START"], ["end_time", "END"], ["room", "ROOM"], ["exam_type", "TYPE"]],
    fields: [
      ["title", "Exam title", "text"], ["subject_id", "Subject", "select", "subjects"],
      ["exam_date", "Exam date", "date"], ["start_time", "Start time", "time"],
      ["end_time", "End time", "time"], ["room", "Room", "text", [], false],
      ["exam_type", "Exam type", "select", "exam-types"],
    ],
  },
  timetable: {
    title: "Timetable", eyebrow: "WEEKLY CLASS SCHEDULE", plural: "Class sessions",
    description: "Create a weekly schedule for subjects, faculty and rooms.", resource: "timetable",
    columns: [["day", "DAY"], ["start_time", "START"], ["end_time", "END"], ["subject_name", "SUBJECT"], ["course_name", "COURSE"], ["faculty_name", "FACULTY"], ["room", "ROOM"]],
    fields: [
      ["subject_id", "Subject", "select", "subjects"], ["faculty_id", "Faculty", "select", "faculty", false],
      ["day_of_week", "Day", "select", "days"], ["start_time", "Start time", "time"],
      ["end_time", "End time", "time"], ["room", "Room", "text", [], false],
    ],
  },
};

function moduleChoices(source) {
  const choices = {
    departments: state.departments,
    courses: state.courses,
    faculty: state.faculty,
    subjects: state.subjects,
    students: state.students.map((student) => ({
      id: student.id, name: `${student.student_number} — ${student.name}`,
    })),
    "attendance-status": ["Present", "Absent", "Late", "Excused"].map((name) => ({ id: name, name })),
    "assessment-types": ["Internal", "Semester"].map((name) => ({ id: name, name })),
    "exam-types": ["Internal", "Semester", "Practical"].map((name) => ({ id: name, name })),
    days: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"].map((name, id) => ({ id, name })),
  };
  return choices[source] || [];
}

async function loadModule(view) {
  const config = MODULES[view];
  if (!config) return;
  $("#records-title").innerHTML = `${escapeHtml(config.title)}<span class="heading-period">.</span>`;
  $("#records-eyebrow").textContent = config.eyebrow;
  $("#records-description").textContent = config.description;
  $("#records-list-title").innerHTML = `All ${escapeHtml(config.plural.toLowerCase())} <span class="subtle-count" id="records-count">${state.records.length}</span>`;
  $("#records-list-description").textContent = config.description;
  $("#records-add-button").classList.toggle("hidden", !canWriteModule(view));
  $("#records-add-button").textContent = `＋ Add ${view === "faculty" ? "faculty" : view === "subjects" ? "subject" : view === "attendance" ? "attendance" : view === "marks" ? "marks" : view === "exams" ? "exam" : "class"}`;
  $("#records-date-filter").classList.toggle("hidden", !["attendance", "exams"].includes(view));
  const query = new URLSearchParams();
  if (view === "attendance" && $("#records-date-filter").value) query.set("date", $("#records-date-filter").value);
  const records = await api(`/${config.resource}${query.size ? `?${query}` : ""}`);
  if (view === "faculty") records.forEach((item) => { item.faculty_names = item.subjects.map((subject) => subject.name).join(", "); });
  if (view === "subjects") records.forEach((item) => { item.faculty_names = item.faculty.map((person) => person.name).join(", ") || "—"; });
  state.records = records;
  $("#records-head").innerHTML = `<tr>${config.columns.map(([, title]) => `<th>${escapeHtml(title)}</th>`).join("")}<th></th></tr>`;
  renderModuleRows(view);
}

function canWriteModule(view) {
  return state.user?.role === "admin" || (state.user?.role === "faculty" && ["attendance", "marks"].includes(view));
}

function renderModuleRows(view) {
  const config = MODULES[view];
  const term = $("#records-search").value.trim().toLowerCase();
  const rows = state.records.filter((row) => !term || JSON.stringify(row).toLowerCase().includes(term));
  $("#records-count").textContent = rows.length;
  $("#records-body").innerHTML = rows.map((row) => `<tr>${config.columns.map(([key]) =>
    `<td>${escapeHtml(row[key] === null || row[key] === undefined || row[key] === "" ? "—" : row[key])}</td>`).join("")}
    <td><div class="row-actions">${canWriteModule(view) ? `<button class="icon-button" data-action="edit-record" data-module="${view}" data-id="${row.id}" aria-label="Edit record">✎</button><button class="icon-button" data-action="delete-record" data-module="${view}" data-id="${row.id}" aria-label="Delete record">×</button>` : ""}${view === "marks" ? `<button class="icon-button" data-action="open-marksheet" data-id="${row.student_id}" aria-label="Open student marksheet">↗</button>` : ""}</div></td>
  </tr>`).join("");
  $("#records-empty").classList.toggle("hidden", rows.length > 0);
  $(".directory-panel #records-head").closest(".table-wrap").classList.toggle("hidden", rows.length === 0);
}

function navigate(view) {
  const isModule = Boolean(MODULES[view]);
  if (!$("#" + view + "-view") && !isModule && view !== "reports") return;
  state.view = view;
  const panelId = isModule ? "records-view" : `${view}-view`;
  $$(".view-panel").forEach((panel) => panel.classList.toggle("active", panel.id === panelId));
  $$(".nav-link").forEach((link) => link.classList.toggle("active", link.dataset.view === view));
  const title = isModule ? MODULES[view].title : view[0].toUpperCase() + view.slice(1);
  $("#breadcrumb-current").textContent = view === "dashboard" ? "Overview" : title;
  $("#sidebar").classList.remove("open");
  if (view === "students") loadStudents().catch((error) => showToast(error.message, true));
  if (isModule) loadModule(view).catch((error) => showToast(error.message, true));
}

function formField(label, name, options = {}) {
  const { type = "text", value = "", placeholder = "", required = true, full = false, choices = [], help = "", min, max, step = "1" } = options;
  const valueAttr = `value="${escapeHtml(value)}"`;
  let input;
  if (type === "select") {
    input = `<select id="field-${name}" name="${name}" ${required ? "required" : ""}><option value="">Select ${label.toLowerCase()}</option>${choices.map((choice) =>
      `<option value="${choice.id}" ${String(choice.id) === String(value) ? "selected" : ""}>${escapeHtml(choice.name)}</option>`).join("")}</select>`;
  } else if (type === "multiselect") {
    const selected = (value || []).map(String);
    input = `<select id="field-${name}" name="${name}" multiple size="4">${choices.map((choice) =>
      `<option value="${choice.id}" ${selected.includes(String(choice.id)) ? "selected" : ""}>${escapeHtml(choice.name)}</option>`).join("")}</select>`;
  } else if (type === "textarea") {
    input = `<textarea id="field-${name}" name="${name}" placeholder="${escapeHtml(placeholder)}" ${required ? "required" : ""}>${escapeHtml(value)}</textarea>`;
  } else {
    const numeric = type === "number" ? `min="${min ?? 1}" ${max === undefined ? "" : `max="${max}"`} step="${step}"` : "";
    input = `<input id="field-${name}" name="${name}" type="${type}" ${type === "date" && !value ? "" : valueAttr} placeholder="${escapeHtml(placeholder)}" ${numeric} ${required ? "required" : ""} ${type === "email" ? "autocomplete=\"email\"" : ""}>`;
  }
  return `<div class="form-field${full ? " full" : ""}"><label for="field-${name}">${label}${required ? " *" : ""}</label>${input}${help ? `<small>${escapeHtml(help)}</small>` : ""}</div>`;
}

function openModal(title, body, onSubmit, eyebrow = "CAMPUS DIRECTORY") {
  $("#modal-title").textContent = title;
  $("#modal-eyebrow").textContent = eyebrow;
  $("#modal-content").innerHTML = body;
  $("#modal-backdrop").classList.remove("hidden");
  const form = $("#modal-content form");
  $("#modal-close").focus();
  if (form) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submit = form.querySelector('[type="submit"]');
      submit.disabled = true;
      const values = Object.fromEntries(new FormData(form).entries());
      try {
        await onSubmit(values);
      } catch (error) {
        const message = $("#modal-error");
        if (message) {
          message.textContent = error.message;
          message.classList.remove("hidden");
        } else showToast(error.message, true);
        submit.disabled = false;
      }
    });
  }
}

function closeModal() {
  $("#modal-backdrop").classList.add("hidden");
  $("#modal-content").innerHTML = "";
}

function studentForm(student = {}) {
  const departmentId = student.department_id || "";
  const matchingCourses = state.courses.filter((course) => String(course.department_id) === String(departmentId));
  const today = new Date().toISOString().slice(0, 10);
  return `<form><div class="form-grid">
    ${student.student_number ? `<div class="form-field full"><label>Student ID</label><div>${escapeHtml(student.student_number)}</div></div>` : ""}
    ${formField("Full name", "name", { value: student.name || "", placeholder: "e.g. Alex Morgan" })}
    ${formField("Email address", "email", { type: "email", value: student.email || "", placeholder: "alex@campus.edu" })}
    ${formField("Phone number", "phone", { type: "tel", value: student.phone || "", placeholder: "+1 (555) 000-0000" })}
    ${formField("Admission date", "admission_date", { type: "date", value: student.admission_date || today })}
    ${formField("Department", "department_id", { type: "select", value: departmentId, choices: state.departments })}
    ${formField("Course", "course_id", { type: "select", value: student.course_id || "", choices: matchingCourses })}
    <div class="form-error hidden full" id="modal-error" role="alert"></div>
  </div><div class="form-actions"><button type="button" class="button button-secondary" data-action="close-modal">Cancel</button><button class="button button-primary" type="submit">${student.id ? "Save changes" : "Register student"}</button></div></form>`;
}

function openStudentForm(student = {}) {
  if (state.user?.role !== "admin") {
    showToast("Administrator access is required.", true);
    return;
  }
  if (!state.departments.length || !state.courses.length) {
    showToast("Add a department and course before registering a student.", true);
    return;
  }
  openModal(student.id ? "Edit student" : "Register a student", studentForm(student), async (values) => {
    await api(student.id ? `/students/${student.id}` : "/students", {
      method: student.id ? "PUT" : "POST", body: JSON.stringify(values),
    });
    closeModal();
    await refreshData();
    if (state.view === "students") await loadStudents();
    showToast(student.id ? "Student record updated." : "Student registered successfully.");
  });
  const department = $("#field-department_id");
  department.addEventListener("change", () => {
    const course = $("#field-course_id");
    const currentCourse = course.value;
    const available = state.courses.filter((item) => String(item.department_id) === department.value);
    course.innerHTML = `<option value="">Select course</option>${available.map((item) =>
      `<option value="${item.id}" ${String(item.id) === currentCourse ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("")}`;
  });
}

function collectionForm(kind, item = {}) {
  if (kind === "department") return `<form><div class="form-grid">
    ${formField("Department name", "name", { value: item.name || "", placeholder: "e.g. School of Design" })}
    ${formField("Department code", "code", { value: item.code || "", placeholder: "e.g. DESIGN" })}
    ${formField("Description", "description", { type: "textarea", value: item.description || "", placeholder: "A short description of this department", full: true, required: false })}
    <div class="form-error hidden full" id="modal-error" role="alert"></div>
  </div><div class="form-actions"><button type="button" class="button button-secondary" data-action="close-modal">Cancel</button><button class="button button-primary" type="submit">${item.id ? "Save changes" : "Add department"}</button></div></form>`;
  return `<form><div class="form-grid">
    ${formField("Course name", "name", { value: item.name || "", placeholder: "e.g. Product Design" })}
    ${formField("Course code", "code", { value: item.code || "", placeholder: "e.g. DES-101" })}
    ${formField("Department", "department_id", { type: "select", value: item.department_id || "", choices: state.departments })}
    ${formField("Course credits", "credits", { type: "number", value: item.credits || 3, min: 1, max: 30 })}
    ${formField("Duration", "duration", { value: item.duration || "", placeholder: "e.g. 4 years", required: false })}
    ${formField("Description", "description", { type: "textarea", value: item.description || "", placeholder: "What students will learn", full: true, required: false })}
    <div class="form-error hidden full" id="modal-error" role="alert"></div>
  </div><div class="form-actions"><button type="button" class="button button-secondary" data-action="close-modal">Cancel</button><button class="button button-primary" type="submit">${item.id ? "Save changes" : "Add course"}</button></div></form>`;
}

function openCollectionForm(kind, item = {}) {
  if (state.user?.role !== "admin") {
    showToast("Administrator access is required.", true);
    return;
  }
  if (kind === "course" && !state.departments.length) {
    showToast("Add a department before creating a course.", true);
    return;
  }
  const isDepartment = kind === "department";
  const resource = isDepartment ? "departments" : "courses";
  const title = `${item.id ? "Edit" : "Add"} ${kind}`;
  openModal(title, collectionForm(kind, item), async (values) => {
    await api(item.id ? `/${resource}/${item.id}` : `/${resource}`, {
      method: item.id ? "PUT" : "POST", body: JSON.stringify(values),
    });
    closeModal();
    await refreshData();
    showToast(`${kind[0].toUpperCase() + kind.slice(1)} ${item.id ? "updated" : "added"}.`);
  }, isDepartment ? "YOUR ACADEMIC TEAMS" : "ACADEMIC PROGRAMS");
}

async function showStudentProfile(id) {
  const [student, academic] = await Promise.all([
    api(`/students/${id}`), api(`/students/${id}/marksheet`),
  ]);
  const body = `<div class="profile-card"><div class="student-cell"><span class="avatar avatar-student">${escapeHtml(initials(student.name))}</span><span><strong>${escapeHtml(student.name)}</strong><small>${escapeHtml(student.email)}</small></span></div></div>
    <div class="form-grid profile-details">
      <div class="form-field"><label>Student ID</label><div>${escapeHtml(student.student_number)}</div></div>
      <div class="form-field"><label>Phone</label><div>${escapeHtml(student.phone)}</div></div>
      <div class="form-field"><label>Status</label><div>${escapeHtml(student.status)}</div></div>
      <div class="form-field"><label>Department</label><div>${escapeHtml(student.department_name)}</div></div>
      <div class="form-field"><label>Course</label><div>${escapeHtml(student.course_name)}</div></div>
      <div class="form-field"><label>Admission date</label><div>${formattedDate(student.admission_date)}</div></div>
      <div class="form-field"><label>Attendance</label><div>${academic.attendance_percentage}%</div></div>
      <div class="form-field"><label>GPA</label><div>${academic.gpa}</div></div>
    </div><div class="form-actions"><button class="button button-secondary" data-action="close-modal">Close</button><button class="button button-primary" data-action="edit-from-profile" data-id="${student.id}">Edit record</button></div>`;
  openModal("Student profile", body, null, "STUDENT DETAILS");
}

function openModuleRecordForm(view, record = {}) {
  const config = MODULES[view];
  if (!canWriteModule(view)) return;
  const fields = config.fields.map(([name, label, type = "text", source, required = true]) => {
    const choices = typeof source === "string" ? moduleChoices(source) : [];
    let value = record[name] ?? "";
    if (type === "multiselect") value = record.faculty_ids || [];
    if (!record.id && name === "attendance_date") value = new Date().toISOString().slice(0, 10);
    if (!record.id && name === "semester") value = 1;
    if (!record.id && name === "credits") value = 3;
    if (!record.id && name === "max_marks") value = 100;
    if (type === "select" && source === "days" && value === "") value = 0;
    return formField(label, name, {
      type, value, choices, required, full: type === "multiselect",
      min: type === "number" ? (name === "credits" ? 1 : 0) : undefined,
      max: type === "number" && name === "credits" ? 30 : undefined,
    });
  }).join("");
  const body = `<form><div class="form-grid">${fields}<div class="form-error hidden full" id="modal-error" role="alert"></div></div>
    <div class="form-actions"><button type="button" class="button button-secondary" data-action="close-modal">Cancel</button><button type="submit" class="button button-primary">${record.id ? "Save changes" : `Add ${config.title.toLowerCase()}`}</button></div></form>`;
  openModal(`${record.id ? "Edit" : "Add"} ${config.title.toLowerCase()}`, body, async (values) => {
    for (const [name, , type] of config.fields) {
      if (type === "multiselect") {
        values[name] = [...$("#field-" + name).selectedOptions].map((option) => Number(option.value));
      } else if (type === "number") {
        values[name] = Number(values[name]);
      }
    }
    await api(record.id ? `/${config.resource}/${record.id}` : `/${config.resource}`, {
      method: record.id ? "PUT" : "POST", body: JSON.stringify(values),
    });
    closeModal();
    await refreshData();
    await loadModule(view);
    showToast(`${config.title} ${record.id ? "updated" : "added"}.`);
  });
}

async function deleteRecord(resource, id, label) {
  if (!window.confirm(`Delete this ${label}? This action cannot be undone.`)) return;
  await api(`/${resource}/${id}`, { method: "DELETE" });
  await refreshData();
  if (state.view === "students") await loadStudents();
  showToast(`${label[0].toUpperCase() + label.slice(1)} deleted.`);
}

async function showMarksheet(studentId) {
  const report = await api(`/students/${studentId}/marksheet`);
  const body = `<div class="profile-card"><div class="student-cell"><span class="avatar avatar-student">${escapeHtml(initials(report.student.name))}</span><span><strong>${escapeHtml(report.student.name)}</strong><small>${escapeHtml(report.student.student_number)} · ${escapeHtml(report.student.email)}</small></span></div></div>
    <div class="collection-meta"><span>${escapeHtml(report.student.course_name)}</span><strong>GPA ${report.gpa}</strong></div>
    <div class="table-wrap"><table><thead><tr><th>SUBJECT</th><th>SEMESTER</th><th>TYPE</th><th>MARKS</th><th>GRADE</th></tr></thead><tbody>${report.marks.map((mark) =>
      `<tr><td>${escapeHtml(mark.subject_name)}</td><td>${mark.semester}</td><td>${escapeHtml(mark.assessment_type)}</td><td>${mark.marks_obtained} / ${mark.max_marks}</td><td>${escapeHtml(mark.grade)}</td></tr>`).join("")}</tbody></table></div>`;
  openModal("Student marksheet", body, null, "ACADEMIC RESULTS");
}

async function exportReport(report, format) {
  const token = sessionStorage.getItem("campus-token");
  const response = await fetch(`${API_BASE}/reports/${report}.${format}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || "Report export failed.");
  }
  const blob = await response.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${report}-report.${format}`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  showToast(`${report[0].toUpperCase() + report.slice(1)} report exported.`);
}

async function refreshData() {
  await Promise.all([loadDashboard(), loadReferenceData()]);
}

document.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-view], [data-action]");
  if (!target) return;
  if (target.dataset.view) {
    navigate(target.dataset.view);
    return;
  }
  const { action, id } = target.dataset;
  try {
    switch (action) {
      case "add-student": openStudentForm(); break;
      case "edit-student": openStudentForm(await api(`/students/${id}`)); break;
      case "profile-student": await showStudentProfile(id); break;
      case "edit-from-profile": closeModal(); openStudentForm(await api(`/students/${id}`)); break;
      case "delete-student": await deleteRecord("students", id, "student"); break;
      case "add-course": openCollectionForm("course"); break;
      case "edit-course": openCollectionForm("course", state.courses.find((item) => item.id === Number(id))); break;
      case "delete-course": await deleteRecord("courses", id, "course"); break;
      case "add-department": openCollectionForm("department"); break;
      case "edit-department": openCollectionForm("department", state.departments.find((item) => item.id === Number(id))); break;
      case "delete-department": await deleteRecord("departments", id, "department"); break;
      case "add-record": openModuleRecordForm(state.view); break;
      case "edit-record": {
        const record = state.records.find((item) => item.id === Number(id));
        if (record) openModuleRecordForm(target.dataset.module, record);
        break;
      }
      case "delete-record": await deleteRecord(target.dataset.module, id, target.dataset.module.slice(0, -1)); await loadModule(target.dataset.module); break;
      case "open-marksheet": await showMarksheet(id); break;
      case "export-report": await exportReport(target.dataset.report, target.dataset.format); break;
      case "logout":
        sessionStorage.removeItem("campus-token");
        sessionStorage.removeItem("campus-user");
        state.user = null;
        $("#auth-screen").classList.remove("hidden");
        closeModal();
        break;
      case "close-modal": closeModal(); break;
      default: break;
    }
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#modal-close").addEventListener("click", closeModal);
$("#modal-backdrop").addEventListener("click", (event) => {
  if (event.target === $("#modal-backdrop")) closeModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeModal();
});
$("#menu-button").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
$("#student-search").addEventListener("input", () => {
  if (state.view === "students") loadStudents().catch((error) => showToast(error.message, true));
});
$("#student-department-filter").addEventListener("change", () => {
  if (state.view === "students") loadStudents().catch((error) => showToast(error.message, true));
});
$("#records-search").addEventListener("input", () => {
  if (MODULES[state.view]) renderModuleRows(state.view);
});
$("#records-date-filter").addEventListener("change", () => {
  if (MODULES[state.view]) loadModule(state.view).catch((error) => showToast(error.message, true));
});
$("#today-label").textContent = new Intl.DateTimeFormat("en", { weekday: "short", month: "short", day: "numeric" }).format(new Date());

function applyAccess() {
  const roles = {
    admin: ["dashboard", "students", "courses", "departments", "faculty", "subjects", "attendance", "marks", "exams", "timetable", "reports"],
    faculty: ["dashboard", "students", "courses", "departments", "faculty", "subjects", "attendance", "marks", "exams", "timetable", "reports"],
    student: ["dashboard", "students", "courses", "departments", "subjects", "attendance", "marks", "exams", "timetable", "reports"],
  };
  $$(".nav-link").forEach((link) => {
    link.classList.toggle("hidden", !roles[state.user.role].includes(link.dataset.view));
  });
  $$(".button[data-action='add-student'], .button[data-action='add-course'], .button[data-action='add-department']").forEach((button) => {
    button.classList.toggle("hidden", state.user.role !== "admin");
  });
  $$(".quick-action[data-action='add-student']").forEach((button) => {
    button.classList.toggle("hidden", state.user.role !== "admin");
  });
  $(".user-card strong").textContent = state.user.name || state.user.email;
  $(".user-card span:not(.user-menu)").textContent = state.user.role[0].toUpperCase() + state.user.role.slice(1);
}

async function enterWorkspace(user) {
  state.user = user;
  applyAccess();
  $("#auth-screen").classList.add("hidden");
  await refreshData();
}

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const errorBox = $("#login-error");
  const button = $(".auth-submit");
  button.disabled = true;
  errorBox.classList.add("hidden");
  try {
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    const result = await api("/auth/login", { method: "POST", body: JSON.stringify(values) });
    sessionStorage.setItem("campus-token", result.token);
    sessionStorage.setItem("campus-user", JSON.stringify(result.user));
    await enterWorkspace(result.user);
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.classList.remove("hidden");
  } finally {
    button.disabled = false;
  }
});

async function initialize() {
  const token = sessionStorage.getItem("campus-token");
  if (!token) {
    $("#auth-screen").classList.remove("hidden");
    return;
  }
  try {
    const user = await api("/auth/me");
    sessionStorage.setItem("campus-user", JSON.stringify(user));
    await enterWorkspace(user);
  } catch (error) {
    sessionStorage.removeItem("campus-token");
    $("#auth-screen").classList.remove("hidden");
    if (error.message !== "The access token is invalid or expired.") showToast(error.message, true);
  }
}

initialize().catch((error) => showToast(error.message, true));
