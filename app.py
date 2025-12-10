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

# ============================================================================================
#                                      HELPER FUNCTIONS
# ============================================================================================
def get_user_by_email(email):
    docs = list(db.collection('users').where('email', '==', email).limit(1).stream())
    return docs[0] if docs else None

def create_user_record(name, email, pw_hash, role, extra_id_field=None):
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
    return db.collection('classes').document(class_code).get()

def create_class(class_code, subject_name, sections):
    sections_map = {}
    for s in sections:
        if s.strip():
            sections_map[s.strip()] = {"teacher": None, "students": [], "attendance": {}}

    new_class = {
        "classCode": class_code,
        "subjectName": subject_name,
        "sections": sections_map
    }
    db.collection('classes').document(class_code).set(new_class)
    return new_class

def add_section_if_missing(class_code, section):
    class_ref = db.collection('classes').document(class_code)
    doc = class_ref.get()
    if not doc.exists:
        return False

    sections = doc.to_dict().get('sections', {})
    if section not in sections:
        class_ref.update({
            f"sections.{section}": {"teacher": None, "students": [], "attendance": {}}
        })
    return True

def add_class_to_user(user_id, class_code, section):
    db.collection('users').document(user_id).update({
        'classes': firestore.ArrayUnion([{'class_code': class_code, 'section': section}])
    })

def assign_teacher_to_section(teacher_id, class_code, section):
    db.collection('classes').document(class_code).update({
        f"sections.{section}.teacher": teacher_id
    })

def add_student_to_section(student_id, class_code, section):
    db.collection('classes').document(class_code).update({
        f"sections.{section}.students": firestore.ArrayUnion([student_id])
    })

def get_sections(class_code):
    doc = get_class_doc(class_code)
    if not doc.exists:
        return []
    return list(doc.to_dict().get('sections', {}).keys())

def get_students_in_section(class_code, section):
    doc = get_class_doc(class_code)
    if not doc.exists:
        return []

    sec_data = doc.to_dict().get('sections', {}).get(section, {})
    students = []

    for sid in sec_data.get('students', []):
        s_doc = db.collection('users').document(sid).get()
        if s_doc.exists:
            s_data = s_doc.to_dict()
            students.append({
                'id': sid,
                'name': s_data.get('name', 'Unknown')
            })

    return students

def save_attendance_to_section(class_code, section, date_str, attendance_list):
    db.collection('classes').document(class_code).update({
        f"sections.{section}.attendance.{date_str}": attendance_list
    })

def get_attendance_summary_for_student(user_id):
    user_doc = db.collection('users').document(user_id).get()
    if not user_doc.exists:
        return []

    classes = user_doc.to_dict().get('classes', [])
    results = []

    for entry in classes:
        class_code = entry.get('class_code')
        section = entry.get('section')

        class_doc = get_class_doc(class_code)
        if not class_doc.exists:
            continue

        cd = class_doc.to_dict()
        subject = cd.get('subjectName', '')

        attendance_map = cd.get('sections', {}).get(section, {}).get('attendance', {})

        present = absent = excused = 0

        for date_key, records in attendance_map.items():
            for rec in records:
                if rec.get('student_id') != user_id:
                    continue
                if rec.get('status') == 'present':
                    present += 1
                elif rec.get('status') == 'absent':
                    absent += 1
                elif rec.get('status') == 'excused':
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
    doc = get_class_doc(class_code)
    if not doc.exists:
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

# ============================================================================================
#                                          ROUTES
# ============================================================================================

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# ---------- LOGIN / SIGNUP ----------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','')

        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session['user'] = {'id':'admin','role':'admin','name':'Administrator'}
            return redirect(url_for('dashboard'))

        doc = get_user_by_email(email)
        if not doc:
            flash("Account not found", "danger")
            return render_template('login.html')

        user = doc.to_dict()
        if not check_password_hash(user.get('password_hash',''), password):
            flash("Incorrect password", "danger")
            return render_template('login.html')

        session['user'] = {
            'id': doc.id,
            'email': user.get('email'),
            'name': user.get('name'),
            'role': user.get('role')
        }
        return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/signup_role')
def signup_role():
    return render_template('signup_role.html')

@app.route('/signup_student', methods=['GET','POST'])
def signup_student():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].lower()
        password = request.form['password']
        student_id = request.form.get('student_id','')
        gender = request.form.get('gender','')

        if get_user_by_email(email):
            flash("Email already exists!", "warning")
            return redirect(url_for('signup_student'))

        pw_hash = generate_password_hash(password)
        create_user_record_student(name, email, pw_hash, 'student', student_id, gender)

        flash("Student account created!", "success")
        return redirect(url_for('login'))

    return render_template('signup_student.html')

@app.route('/signup_teacher', methods=['GET','POST'])
def signup_teacher():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].lower()
        password = request.form['password']
        teacher_id = request.form.get('teacher_id','')

        if get_user_by_email(email):
            flash("Email already exists!", "warning")
            return redirect(url_for('signup_teacher'))

        pw_hash = generate_password_hash(password)
        create_user_record(name, email, pw_hash, 'teacher', teacher_id)

        flash("Teacher account created!", "success")
        return redirect(url_for('login'))

    return render_template('signup_teacher.html')

@app.route('/profile')
def profile():
    if 'user' not in session:
        return redirect(url_for('login'))
    user_id = session['user']['id']
    doc = db.collection('users').document(user_id).get()
    if not doc.exists:
        flash("User profile not found.", "danger")
        return redirect(url_for('dashboard'))
    user_data = doc.to_dict()
    return render_template('profile.html', user=user_data)

# ============================================================================================
# TEACHER CLASS VIEW (RENAMED TO SINGULAR PATH)
# ============================================================================================
@app.route('/dashboard/teacher/class')
def dashboard_teacher_class():
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('login'))
    user_id = session['user']['id']
    user_doc = db.collection('users').document(user_id).get()
    classes_list = []
    if user_doc.exists:
        raw_classes = user_doc.to_dict().get('classes', [])
        for entry in raw_classes:
            class_code = entry.get('class_code')
            section = entry.get('section')
            class_doc = db.collection('classes').document(class_code).get()
            if class_doc.exists:
                cd = class_doc.to_dict()
                subject = cd.get('subjectName', '')
                counts = count_students_and_teachers(class_code)
                classes_list.append({
                    'class_code': class_code,
                    'section': section,
                    'subjectName': subject,
                    'student_count': counts['student_count']
                })
            else:
                classes_list.append({
                    'class_code': class_code,
                    'section': section,
                    'subjectName': '',
                    'student_count': 0
                })
    return render_template('dashboard_teacher_class.html', classes=classes_list, user=session['user'])


@app.route('/dashboard/teacher/view_class/<class_code>/<section>')
def dashboard_teacher_view_class(class_code, section):
    if 'user' not in session or session['user']['role'] != 'teacher':
        return redirect(url_for('login'))

    class_code = class_code.strip().upper()
    section = section.strip()

    class_doc = get_class_doc(class_code)
    if not class_doc.exists:
        flash("Class not found.", "danger")
        return redirect(url_for('dashboard_teacher_class'))

    class_data = class_doc.to_dict()
    subject = class_data.get('subjectName', '')

    raw_students = get_students_in_section(class_code, section)
    students = []
    for s in raw_students:
        students.append({
            'student_id': s.get('id',''),
            'name': s.get('name','Unknown'),
            'status': ''
        })

    return render_template('dashboard_teacher_view_class.html',
                           class_code=class_code,
                           section=section,
                           subjectName=subject,
                           students=students,
                           user=session['user'])

# ============================================================================================
# New route: Add Class (from modal)
# ============================================================================================
@app.route('/teacher/add_class', methods=['POST'])
def add_class_teacher():
    # Only teachers can add/assign classes via this modal
    if 'user' not in session or session['user']['role'] != 'teacher':
        flash("Unauthorized", "danger")
        return redirect(url_for('login'))

    user_id = session['user']['id']
    class_code = (request.form.get('class_code') or '').strip().upper()
    section = (request.form.get('section') or '').strip()
    subject = (request.form.get('subject') or '').strip()

    if not class_code or not section:
        flash("Please provide class code and section.", "warning")
        return redirect(url_for('dashboard_teacher_class'))

    # If class doc exists: just add section if missing and assign teacher
    class_doc_ref = db.collection('classes').document(class_code)
    class_doc = class_doc_ref.get()

    try:
        if class_doc.exists:
            # add section if missing
            add_section_if_missing(class_code, section)
            # assign teacher to the section and add to teacher's user record
            assign_teacher_to_section(user_id, class_code, section)
            add_class_to_user(user_id, class_code, section)
            flash("Class assigned to you.", "success")
        else:
            # create new class with the given subject and section
            # if subject missing, use class_code as fallback name
            subj = subject if subject else class_code
            create_class(class_code, subj, [section])
            # assign teacher and add class to teacher user doc
            assign_teacher_to_section(user_id, class_code, section)
            add_class_to_user(user_id, class_code, section)
            flash("Class created and assigned to you.", "success")
    except Exception as e:
        app.logger.exception("Error adding/assigning class")
        flash("An error occurred while adding class.", "danger")

    return redirect(url_for('dashboard_teacher_class'))

# ============================================================================================
# DASHBOARD
# ============================================================================================
@app.route('/dashboard', methods=['GET','POST'])
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    user_id = user['id']
    role = user['role']

    # -------- ADMIN --------
    if role == 'admin':
        if request.method == 'POST':
            class_code = request.form.get('class_code','').strip().upper()
            subject = request.form.get('subjectName','').strip()
            sections_raw = request.form.get('sections','')
            sections = [s.strip() for s in sections_raw.split(',') if s.strip()]
            if not class_code or not subject or not sections:
                flash("Fill all required fields", "warning")
                return redirect(url_for('dashboard'))

            create_class(class_code, subject, sections)
            flash("Class created!", "success")
            return redirect(url_for('dashboard'))

        classes_list = []
        for c in db.collection('classes').stream():
            cdict = c.to_dict()
            counts = count_students_and_teachers(c.id)
            cdict['student_count'] = counts['student_count']
            cdict['teacher_count'] = counts['teacher_count']
            classes_list.append(cdict)

        return render_template('dashboard_admin.html', classes=classes_list, user=user)

    # -------- TEACHER --------
    if role == 'teacher':
        user_doc = db.collection('users').document(user_id).get().to_dict()
        classes_list = user_doc.get('classes', [])

        if request.method == 'POST':
            action = request.form.get('action','')
            if action == 'add_class':
                class_code = request.form.get('class_code','').strip().upper()
                section = request.form.get('section','').strip()
                if not class_code or not section:
                    flash("Fill all fields", "warning")
                    return redirect(url_for('dashboard'))

                class_doc = get_class_doc(class_code)
                if not class_doc.exists:
                    flash("Class not found!", "danger")
                    return redirect(url_for('dashboard'))

                add_section_if_missing(class_code, section)
                assign_teacher_to_section(user_id, class_code, section)
                add_class_to_user(user_id, class_code, section)
                flash("Class assigned!", "success")
                return redirect(url_for('dashboard'))

        teacher_classes = []
        for entry in classes_list:
            class_code = entry.get('class_code')
            section = entry.get('section')
            class_doc = get_class_doc(class_code)
            if class_doc.exists:
                subj = class_doc.to_dict().get('subjectName','')
                counts = count_students_and_teachers(class_code)
            else:
                subj = ''
                counts = {'student_count':0}
            teacher_classes.append({
                'class_code': class_code,
                'section': section,
                'subjectName': subj,
                'student_count': counts['student_count']
            })
        return render_template('dashboard_teacher.html', classes=teacher_classes, user=user)

    # -------- STUDENT --------
    if role == 'student':
        user_doc = db.collection('users').document(user_id).get().to_dict()
        classes_list = user_doc.get('classes', [])
        if request.method == 'POST':
            action = request.form.get('action','')
            if action == 'join_class':
                class_code = request.form.get('class_code','').strip().upper()
                section = request.form.get('section','').strip()
                class_doc = get_class_doc(class_code)
                if not class_doc.exists:
                    flash("Class not found!", "danger")
                    return redirect(url_for('dashboard'))
                if section not in class_doc.to_dict().get('sections', {}):
                    flash("Section not found!", "danger")
                    return redirect(url_for('dashboard'))
                add_student_to_section(user_id, class_code, section)
                add_class_to_user(user_id, class_code, section)
                flash("Joined class!", "success")
                return redirect(url_for('dashboard'))

        attendance_summary = get_attendance_summary_for_student(user_id)
        return render_template('dashboard_student.html', classes=attendance_summary, user=user)

    return redirect(url_for('login'))

# ============================================================================================
# SUPPORT / AJAX ROUTES
# ============================================================================================
@app.route('/api/class/<class_code>/sections')
def api_get_sections(class_code):
    return jsonify({'sections': get_sections(class_code.strip().upper())})

@app.route('/get_students/<class_code>/<section>')
def ajax_get_students(class_code, section):
    return jsonify({'students': get_students_in_section(class_code.strip().upper(), section.strip())})

@app.route('/save_attendance/<class_code>/<section>', methods=['POST'])
def save_attendance_route(class_code, section):
    if 'user' not in session or session['user']['role'] != 'teacher':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.get_json()
    date_str = data.get('date') or datetime.now().strftime("%Y-%m-%d")
    attendance = data.get('attendance', [])
    save_attendance_to_section(class_code.strip().upper(), section.strip(), date_str, attendance)
    return jsonify({'status': 'success'})

@app.route('/api/student/attendance-summary')
def api_student_attendance_summary():
    if 'user' not in session or session['user']['role'] != 'student':
        return jsonify({'error': 'Unauthorized'}), 403

    user_id = session['user']['id']
    summary = get_attendance_summary_for_student(user_id)
    return jsonify({
        'present': sum(item['present'] for item in summary),
        'absent': sum(item['absent'] for item in summary),
        'excused': sum(item['excused'] for item in summary)
    })

@app.route('/api/student/joined-classes-summary')
def api_student_joined_classes():
    if 'user' not in session or session['user']['role'] != 'student':
        return jsonify([])
    user_id = session['user']['id']
    return jsonify(get_attendance_summary_for_student(user_id))

@app.route('/api/student/class-details/<class_code>/<section>')
def api_student_class_details(class_code, section):
    if 'user' not in session or session['user']['role'] != 'student':
        return jsonify({'error': 'Unauthorized'}), 403

    class_doc = get_class_doc(class_code.upper())
    if not class_doc.exists:
        return jsonify({'error': 'Class not found'}), 404

    data = class_doc.to_dict()
    sec_data = data.get('sections', {}).get(section.strip(), {})
    attendance_list = [{'date': k, 'records': v} for k,v in sec_data.get('attendance', {}).items()]
    return jsonify({
        'subjectName': data.get('subjectName'),
        'classCode': class_code.upper(),
        'section': section.strip(),
        'attendance': attendance_list
    })

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("Logged out", "info")
    return redirect(url_for('login'))

# ============================================================================================
# RUN SERVER
# ============================================================================================
if __name__ == '__main__':
    app.run(debug=True)
