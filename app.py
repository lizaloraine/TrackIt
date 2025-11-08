from flask import Flask, render_template, request, redirect, url_for, session, flash
import firebase_admin
from firebase_admin import credentials, firestore
from werkzeug.security import generate_password_hash, check_password_hash
import os

# ---------- Configuration ----------
APP_SECRET = os.environ.get('TRACKIT_SECRET', 'dev-secret-change-me')
ADMIN_EMAIL = 'admin@trackit.com'
ADMIN_PASSWORD = 'admin123'  # hardcoded admin for now (change in production)

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
    users_ref = db.collection('users')
    docs = users_ref.where('email', '==', email).limit(1).stream()
    docs = list(docs)
    if not docs:
        return None
    return docs[0]  # DocumentSnapshot

def create_user_record(name, email, pw_hash, role, extra_id_field=None):
    data = {
        'name': name,
        'email': email,
        'role': role,
        'classes': [],  # class codes array
    }
    if role == 'student':
        data['student_id'] = extra_id_field or ''
    if role == 'teacher':
        data['teacher_id'] = extra_id_field or ''
    data['password_hash'] = pw_hash
    users_ref = db.collection('users')
    new_doc = users_ref.add(data)
    return new_doc

def append_class_for_user(doc_id, class_code):
    user_ref = db.collection('users').document(doc_id)
    user_ref.update({
        'classes': firestore.ArrayUnion([class_code])
    })

# ---------- Routes ----------
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# Single login page for all roles
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        # Hardcoded admin check (Option A: automatic admin login)
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session['user'] = {
                'id': 'admin-hardcoded',
                'email': ADMIN_EMAIL,
                'name': 'Administrator',
                'role': 'admin'
            }
            flash('Logged in as admin', 'success')
            return redirect(url_for('dashboard'))

        # Otherwise check Firestore
        doc = get_user_by_email(email)
        if not doc:
            flash('No user found with that email', 'danger')
            return render_template('login.html')
        user = doc.to_dict()
        if not check_password_hash(user.get('password_hash', ''), password):
            flash('Incorrect password', 'danger')
            return render_template('login.html')

        # login OK
        session['user'] = {
            'id': doc.id,
            'email': user.get('email'),
            'name': user.get('name'),
            'role': user.get('role', 'student')
        }
        flash(f"Welcome, {user.get('name')}", 'success')
        return redirect(url_for('dashboard'))

    return render_template('login.html')

# Student signup
@app.route('/signup_student', methods=['GET', 'POST'])
def signup_student():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        student_id = request.form.get('student_id', '').strip()

        if not (name and email and password and student_id):
            flash('All fields are required', 'danger')
            return render_template('signup_student.html')

        if get_user_by_email(email):
            flash('Email already registered', 'warning')
            return render_template('signup_student.html')

        pw_hash = generate_password_hash(password)
        create_user_record(name, email, pw_hash, 'student', extra_id_field=student_id)
        flash('Student account created. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup_student.html')

# Teacher signup
@app.route('/signup_teacher', methods=['GET', 'POST'])
def signup_teacher():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        teacher_id = request.form.get('teacher_id', '').strip()

        if not (name and email and password and teacher_id):
            flash('All fields are required', 'danger')
            return render_template('signup_teacher.html')

        if get_user_by_email(email):
            flash('Email already registered', 'warning')
            return render_template('signup_teacher.html')

        pw_hash = generate_password_hash(password)
        create_user_record(name, email, pw_hash, 'teacher', extra_id_field=teacher_id)
        flash('Teacher account created. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup_teacher.html')

# Single dashboard router
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    user = session['user']
    role = user.get('role')

    # Admin Dashboard
    if role == 'admin':
        return render_template('dashboard_admin.html', user=user)

    # Teacher Dashboard: show classes & allow adding class codes
    if role == 'teacher':
        # optionally handle add-class form
        if request.method == 'POST':
            class_code = request.form.get('class_code', '').strip()
            if class_code:
                append_class_for_user(user['id'], class_code)
                flash(f'Class {class_code} added to your profile', 'success')
            return redirect(url_for('dashboard'))

        # fetch updated user doc
        doc = db.collection('users').document(user['id']).get()
        user_doc = doc.to_dict() if doc.exists else {}
        classes = user_doc.get('classes', [])
        return render_template('dashboard_teacher.html', user=user, classes=classes)

    # Student Dashboard
    if role == 'student':
        if request.method == 'POST':
            class_code = request.form.get('class_code', '').strip()
            if class_code:
                append_class_for_user(user['id'], class_code)
                flash(f'Joined class {class_code}', 'success')
            return redirect(url_for('dashboard'))

        doc = db.collection('users').document(user['id']).get()
        user_doc = doc.to_dict() if doc.exists else {}
        classes = user_doc.get('classes', [])
        return render_template('dashboard_student.html', user=user, classes=classes)

    # Fallback
    flash('Unknown role', 'danger')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out', 'info')
    return redirect(url_for('login'))

# ---------- Run ----------
if __name__ == '__main__':
    app.run(debug=True)
