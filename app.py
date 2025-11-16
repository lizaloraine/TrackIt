from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

# ---------- Configuration ----------
APP_SECRET = os.environ.get('TRACKIT_SECRET', 'dev-secret-change-me')
ADMIN_EMAIL = os.environ.get('TRACKIT_ADMIN_EMAIL', 'admin@trackit.com')
ADMIN_PASSWORD = os.environ.get('TRACKIT_ADMIN_PASSWORD', 'admin123')

# ---------- Flask init ----------
app = Flask(__name__)
app.secret_key = APP_SECRET

# ---------- Firebase Admin / Firestore init ----------
cred_path = os.path.join(os.path.dirname(__file__), 'firebase', 'config.json')
if not os.path.exists(cred_path):
    raise RuntimeError('Place your Firebase service account JSON at firebase/config.json')

cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

# ---------- Helpers ----------
def get_user_by_email(email):
    """Return a DocumentSnapshot or None"""
    docs = list(db.collection('users').where('email', '==', email).limit(1).stream())
    return docs[0] if docs else None

def create_user_record(name, email, pw_hash, role, extra_id_field=None):
    """
    Creates a user doc.
    'classes' is an array of maps [{'class_code': 'CSE402', 'section': 'CS-4101'}]
    """
    data = {
        'name': name,
        'email': email,
        'role': role,
        'classes': [],
        'password_hash': pw_hash
    }
    if role == 'student':
        data['student_id'] = extra_id_field or ''
    if role == 'teacher':
        data['teacher_id'] = extra_id_field or ''

    return db.collection('users').add(data)


def create_user_record_student(name, email, pw_hash, role, extra_id_field=None, gender=None):
    """
    Creates a user doc.
    'classes' is an array of maps [{'class_code': 'CSE402', 'section': 'CS-4101'}]
    """
    data = {
        'name': name,
        'email': email,
        'role': role,
        'classes': [],
        'password_hash': pw_hash,
        'gender': gender
    }
    if role == 'student':
        data['student_id'] = extra_id_field or ''
    if role == 'teacher':
        data['teacher_id'] = extra_id_field or ''

    return db.collection('users').add(data)



def get_class_doc(class_code):
    """Return DocumentSnapshot for a class (class_code should be uppercase)"""
    return db.collection('classes').document(class_code).get()

def create_class(class_code, subject_name, sections):
    """
    Create a class document with sections.
    sections: list of section strings
    Structure:
    {
      "classCode": "CSE402",
      "subjectName": "Elective 1",
      "sections": {
          "CS-4101": {"teacher": None, "students": [], "attendance": {}},
          ...
      }
    }
    """
    sections_map = {}
    for s in sections:
        s_key = s.strip()
        if not s_key:
            continue
        sections_map[s_key] = {"teacher": None, "students": [], "attendance": {}}
    new_class = {
        "classCode": class_code,
        "subjectName": subject_name,
        "sections": sections_map
    }
    db.collection('classes').document(class_code).set(new_class)
    return new_class

def add_section_if_missing(class_code, section):
    """Ensure a section exists for a class; create it if missing."""
    class_ref = db.collection('classes').document(class_code)
    doc = class_ref.get()
    if not doc.exists:
        return False
    data = doc.to_dict()
    sections = data.get('sections', {})
    if section not in sections:
        # create section
        field = {f"sections.{section}": {"teacher": None, "students": [], "attendance": {}}}
        class_ref.update(field)
    return True

def add_class_to_user(user_id, class_code, section):
    """Add a class+section map to user's classes array (avoids duplicates)."""
    user_ref = db.collection('users').document(user_id)
    entry = {'class_code': class_code, 'section': section}
    user_ref.update({'classes': firestore.ArrayUnion([entry])})

def assign_teacher_to_section(teacher_id, class_code, section):
    """Set the teacher for a specific section"""
    class_ref = db.collection('classes').document(class_code)
    # set sections.<section>.teacher = teacher_id
    class_ref.update({f"sections.{section}.teacher": teacher_id})

def add_student_to_section(student_id, class_code, section):
    """Add a student id to a section's students array"""
    class_ref = db.collection('classes').document(class_code)
    class_ref.update({f"sections.{section}.students": firestore.ArrayUnion([student_id])})

def get_sections(class_code):
    """Return list of section keys for a class code (uppercase)."""
    doc = get_class_doc(class_code)
    if not doc or not doc.exists:
        return []
    d = doc.to_dict()
    secs = list(d.get('sections', {}).keys())
    return secs

def get_students_in_section(class_code, section):
    """
    Return list of student dicts [{'id': doc_id, 'name': '...'}]
    """
    doc = get_class_doc(class_code)
    if not doc or not doc.exists:
        return []
    d = doc.to_dict()
    sec_map = d.get('sections', {}).get(section, {})
    student_ids = sec_map.get('students', []) if sec_map else []
    students = []
    for sid in student_ids:
        s_doc = db.collection('users').document(sid).get()
        if s_doc.exists:
            s_data = s_doc.to_dict()
            students.append({'id': sid, 'name': s_data.get('name', 'Unknown')})
    return students

def save_attendance_to_section(class_code, section, date_str, attendance_list):
    """
    attendance_list = [{'student_id': ..., 'status': 'present'/'absent'/'excused'}]
    Saves under sections.<section>.attendance.<date_str> = attendance_list
    """
    class_ref = db.collection('classes').document(class_code)
    field_path = f"sections.{section}.attendance.{date_str}"
    class_ref.update({field_path: attendance_list})

def get_attendance_summary_for_student(user_id):
    """
    Walk classes the student is enrolled in (user.classes),
    and compute present/absent/excused counts per class.
    Returns a list of dicts:
    [{'class_code': 'CSE402', 'subjectName': 'Elective', 'section': 'CS-4101',
      'present': 21, 'absent': 1, 'excused': 0 }, ...]
    """
    user_doc = db.collection('users').document(user_id).get()
    if not user_doc.exists:
        return []
    u = user_doc.to_dict()
    classes = u.get('classes', [])
    results = []
    for entry in classes:
        # entry expected to be a map with class_code and section
        if isinstance(entry, dict):
            class_code = entry.get('class_code')
            section = entry.get('section')
        else:
            # backward compat (string), assume no section
            class_code = str(entry)
            section = None

        class_doc = get_class_doc(class_code)
        if not class_doc or not class_doc.exists:
            continue
        cd = class_doc.to_dict()
        subject = cd.get('subjectName', '')
        present = absent = excused = 0
        if section:
            attendance_map = cd.get('sections', {}).get(section, {}).get('attendance', {})
            for date_key, att_list in attendance_map.items():
                for rec in att_list:
                    if rec.get('student_id') != user_id:
                        continue
                    status = rec.get('status')
                    if status == 'present':
                        present += 1
                    elif status == 'absent':
                        absent += 1
                    elif status == 'excused':
                        excused += 1
        results.append({
            'class_code': class_code,
            'subjectName': subject,
            'section': section,
            'present': present,
            'absent': absent,
            'excused': excused
        })
    return results

def count_students_and_teachers(class_code):
    """
    Return aggregate counts:
    {'student_count': X, 'teacher_count': Y}
    teacher_count is number of sections that have a teacher assigned.
    """
    doc = get_class_doc(class_code)
    if not doc or not doc.exists:
        return {'student_count': 0, 'teacher_count': 0}
    d = doc.to_dict()
    secs = d.get('sections', {})
    student_count = 0
    teacher_count = 0
    for sec_name, sec_data in secs.items():
        student_count += len(sec_data.get('students', []))
        if sec_data.get('teacher'):
            teacher_count += 1
    return {'student_count': student_count, 'teacher_count': teacher_count}

# ---------- Routes ----------
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        # Admin login
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session['user'] = {'id': 'admin', 'role': 'admin', 'name': 'Administrator'}
            flash("Logged in as admin", "success")
            return redirect(url_for('dashboard'))

        doc = get_user_by_email(email)
        if not doc:
            flash('Account not found', 'danger')
            return render_template('login.html')

        user = doc.to_dict()
        if not check_password_hash(user.get('password_hash', ''), password):
            flash('Wrong password', 'danger')
            return render_template('login.html')

        session['user'] = {
            'id': doc.id,
            'email': user.get('email'),
            'name': user.get('name'),
            'role': user.get('role')
        }
        flash(f"Welcome, {user.get('name')}", "success")
        return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/signup_role')
def signup_role():
    return render_template('signup_role.html')


@app.route('/signup_student', methods=['GET', 'POST'])
def signup_student():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].lower()
        password = request.form['password']
        student_id = request.form.get('student_id', '')
        gender = request.form.get('gender', '')  \

        if get_user_by_email(email):
            flash("Email already exists!", "warning")
            return redirect(url_for('signup_student'))

        pw_hash = generate_password_hash(password)

        create_user_record_student(name, email, pw_hash, 'student', student_id, gender)

        flash("Account created!", "success")
        return redirect(url_for('login'))

    return render_template('signup_student.html')


@app.route('/signup_teacher', methods=['GET', 'POST'])
def signup_teacher():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].lower()
        password = request.form['password']
        teacher_id = request.form.get('teacher_id', '')

        if get_user_by_email(email):
            flash("Email already exists!", "warning")
            return redirect(url_for('signup_teacher'))

        pw_hash = generate_password_hash(password)
        create_user_record(name, email, pw_hash, 'teacher', teacher_id)

        flash("Account created!", "success")
        return redirect(url_for('login'))

    return render_template('signup_teacher.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    user_id = user['id']
    role = user['role']

    # ---------- Admin ----------
    if role == 'admin':
        if request.method == 'POST':
            # Admin creating a new class with sections
            class_code = request.form.get('class_code', '').strip().upper()
            subject = request.form.get('subjectName', '').strip()
            sections_raw = request.form.get('sections', '')
            sections = [s.strip() for s in sections_raw.split(',') if s.strip()]

            if not class_code or not subject or not sections:
                flash("Please provide class code, subject name and at least one section.", "warning")
                return redirect(url_for('dashboard'))

            # create class doc
            create_class(class_code, subject, sections)
            flash("Class created with sections!", "success")
            return redirect(url_for('dashboard'))

        # GET request: render admin dashboard
        classes = []
        for c in db.collection('classes').stream():
            cdict = c.to_dict()
            counts = count_students_and_teachers(c.id)
            # attach counts for UI convenience
            cdict['student_count'] = counts['student_count']
            cdict['teacher_count'] = counts['teacher_count']
            classes.append(cdict)
        return render_template('dashboard_admin.html', classes=classes, user=user)

    # ---------- Teacher ----------
    if role == 'teacher':
        # fetch teacher user doc and classes list
        user_doc_snap = db.collection('users').document(user_id).get()
        user_doc = user_doc_snap.to_dict() if user_doc_snap.exists else {}
        classes = user_doc.get('classes', [])  # list of maps {'class_code','section'}

        if request.method == 'POST':
            # Distinguish between "add_class" (teacher assigns self to a section)
            # and other potential actions. We expect an action field from the form.
            action = request.form.get('action', '')
            if action == 'add_class':
                class_code = request.form.get('class_code', '').strip().upper()
                section = request.form.get('section', '').strip()
                if not class_code or not section:
                    flash("Provide class code and section.", "warning")
                    return redirect(url_for('dashboard'))

                class_doc = get_class_doc(class_code)
                if not class_doc.exists:
                    flash("Class code not found!", "danger")
                    return redirect(url_for('dashboard'))

                # ensure section exists (create if missing)
                add_section_if_missing(class_code, section)

                # assign teacher and add class to teacher's classes
                assign_teacher_to_section(user_id, class_code, section)
                add_class_to_user(user_id, class_code, section)
                flash("Class added to your list and you are assigned as teacher for the section.", "success")
                return redirect(url_for('dashboard'))

            # fallback: treat as join class (legacy)
            class_code = request.form.get('class_code', '').strip().upper()
            section = request.form.get('section', '').strip()
            if class_code:
                class_doc = get_class_doc(class_code)
                if not class_doc.exists:
                    flash("Invalid class code!", "danger")
                else:
                    # if section provided, assign to that section; else just assign class
                    if section:
                        add_section_if_missing(class_code, section)
                        assign_teacher_to_section(user_id, class_code, section)
                        add_class_to_user(user_id, class_code, section)
                    else:
                        add_class_to_user(user_id, class_code, '')
                    flash("Class joined!", "success")
            return redirect(url_for('dashboard'))

        # GET: prepare classes summary for teacher home
        # Normalize classes for template: list of {'class_code','section','subjectName'}
        teacher_classes = []
        for entry in classes:
            if isinstance(entry, dict):
                cc = entry.get('class_code')
                sec = entry.get('section')
            else:
                cc = str(entry)
                sec = ''
            class_doc = get_class_doc(cc)
            subj = class_doc.to_dict().get('subjectName') if class_doc and class_doc.exists else ''
            teacher_classes.append({'class_code': cc, 'section': sec, 'subjectName': subj})
        return render_template('dashboard_teacher.html', classes=teacher_classes, user=user)

    # ---------- Student ----------
    if role == 'student':
        user_doc_snap = db.collection('users').document(user_id).get()
        user_doc = user_doc_snap.to_dict() if user_doc_snap.exists else {}
        classes = user_doc.get('classes', [])  # list of maps {'class_code','section'}

        if request.method == 'POST':
            # Student joining a class
            action = request.form.get('action', '')
            if action == 'join_class':
                class_code = request.form.get('class_code', '').strip().upper()
                section = request.form.get('section', '').strip()
                if not class_code or not section:
                    flash("Provide class code and select a section.", "warning")
                    return redirect(url_for('dashboard'))

                class_doc = get_class_doc(class_code)
                if not class_doc.exists:
                    flash("Class code not found!", "danger")
                    return redirect(url_for('dashboard'))

                # ensure section exists
                add_section_if_missing(class_code, section)

                # add student to section and add class to user's classes
                add_student_to_section(user_id, class_code, section)
                add_class_to_user(user_id, class_code, section)
                flash("Joined class!", "success")
                return redirect(url_for('dashboard'))

            # fallback (legacy)
            class_code = request.form.get('class_code', '').strip().upper()
            if class_code:
                class_doc = get_class_doc(class_code)
                if not class_doc.exists:
                    flash("Class code not found!", "danger")
                else:
                    add_student_to_section(user_id, class_code, '')
                    add_class_to_user(user_id, class_code, '')
                    flash("Joined class!", "success")
                return redirect(url_for('dashboard'))

        # GET: build attendance summary for display in student's home/classes table
        attendance_summary = get_attendance_summary_for_student(user_id)
        return render_template('dashboard_student.html', classes=attendance_summary, user=user)

    flash("Unknown role", "danger")
    return redirect(url_for('login'))

# ---------- AJAX endpoints ----------

@app.route('/get_sections/<class_code>')
def ajax_get_sections(class_code):
    """Return list of sections for a class code as JSON"""
    class_code = class_code.strip().upper()
    secs = get_sections(class_code)
    return jsonify({'sections': secs})

@app.route('/get_students/<class_code>/<section>')
def ajax_get_students(class_code, section):
    """Return student list for a specific class section as JSON"""
    class_code = class_code.strip().upper()
    section = section.strip()
    students = get_students_in_section(class_code, section)
    return jsonify({'students': students})

# Backwards-compatible endpoint if only class_code provided (returns merged student list across sections)
@app.route('/get_students/<class_code>')
def ajax_get_students_by_class(class_code):
    class_code = class_code.strip().upper()
    doc = get_class_doc(class_code)
    if not doc or not doc.exists:
        return jsonify({'students': []})
    d = doc.to_dict()
    students = []
    sections = d.get('sections', {})
    for sec_name, sec_data in sections.items():
        for sid in sec_data.get('students', []):
            s_doc = db.collection('users').document(sid).get()
            if s_doc.exists:
                s_data = s_doc.to_dict()
                students.append({'id': sid, 'name': s_data.get('name', 'Unknown'), 'section': sec_name})
    return jsonify({'students': students})

@app.route('/save_attendance/<class_code>/<section>', methods=['POST'])
def save_attendance_route(class_code, section):
    """
    Receive attendance list and save under the specified class/section/date.
    Expects JSON:
    {
      "date": "YYYY-MM-DD",    # optional, defaults to today if missing
      "attendance": [{'student_id': '...', 'status': 'present'|'absent'|'excused'}, ...]
    }
    """
    if 'user' not in session or session['user']['role'] != 'teacher':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    class_code = class_code.strip().upper()
    section = section.strip()
    payload = request.get_json(force=True) or {}
    attendance_list = payload.get('attendance', [])
    date_str = payload.get('date')
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # validate class/section
    class_doc = get_class_doc(class_code)
    if not class_doc or not class_doc.exists:
        return jsonify({'status': 'error', 'message': 'Class not found'}), 404

    class_data = class_doc.to_dict()
    if section not in class_data.get('sections', {}):
        return jsonify({'status': 'error', 'message': 'Section not found'}), 404

    # Save attendance
    save_attendance_to_section(class_code, section, date_str, attendance_list)
    return jsonify({'status': 'success', 'message': 'Attendance saved'})

# ---------- Logout ----------
@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("Logged out", "info")
    return redirect(url_for('login'))

# ---------- Run ----------
if __name__ == '__main__':
    app.run(debug=True)
