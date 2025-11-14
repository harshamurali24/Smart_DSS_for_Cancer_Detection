from flask import Flask, render_template, request, redirect, url_for, session, send_file
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_TO_A_RANDOM_SECRET_KEY"

DB_PATH = "patients.db"

# ---------------------------
# DATABASE INITIALIZATION
# ---------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            age INTEGER,
            gender TEXT,
            duration INTEGER,
            symptoms TEXT,
            scan_file TEXT,
            lab_file TEXT,
            history_file TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------------------
# ADMIN CREDENTIALS
# ---------------------------
ADMIN_USER = "admin"
ADMIN_PASS = generate_password_hash("cancer123")  # change later

# ---------------------------
# LOGIN REQUIRED DECORATOR
# ---------------------------
def login_required(f):
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/login")
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


# ---------------------------
# ROUTES
# ---------------------------
@app.route("/")
def home():
    return render_template("index.html")


# ---------------------------
# LOGIN / LOGOUT
# ---------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == ADMIN_USER and check_password_hash(ADMIN_PASS, password):
            session["logged_in"] = True
            return redirect("/records")
        else:
            return render_template("login.html", error="Invalid username or password")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------------------
# VIEW ALL RECORDS (PROTECTED)
# ---------------------------
@app.route("/records")
@login_required
def records():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM patients")
    data = cur.fetchall()
    conn.close()
    return render_template("records.html", records=data)


# ---------------------------
# ADD PATIENT (PUBLIC FORM)
# ---------------------------
@app.route("/submit", methods=["POST"])
def submit():
    patient_id = request.form.get("patient_id")
    age = request.form.get("age")
    gender = request.form.get("gender")
    duration = request.form.get("duration")
    symptoms = request.form.get("symptoms")

    scan = request.files.get("scan")
    lab = request.files.get("lab")
    history = request.files.get("history")

    def save_file(file, folder="uploads"):
        if not file or file.filename == "":
            return None
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, file.filename)
        file.save(path)
        return path

    scan_path = save_file(scan)
    lab_path = save_file(lab)
    history_path = save_file(history)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO patients (patient_id, age, gender, duration, symptoms, scan_file, lab_file, history_file) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (patient_id, age, gender, duration, symptoms, scan_path, lab_path, history_path))
    conn.commit()
    conn.close()

    return redirect("/")


# ---------------------------
# EDIT RECORD (PROTECTED)
# ---------------------------
@app.route("/edit/<int:record_id>", methods=["GET", "POST"])
@login_required
def edit(record_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    if request.method == "POST":
        patient_id = request.form.get("patient_id")
        age = request.form.get("age")
        gender = request.form.get("gender")
        duration = request.form.get("duration")
        symptoms = request.form.get("symptoms")

        cur.execute("""
            UPDATE patients 
            SET patient_id=?, age=?, gender=?, duration=?, symptoms=? 
            WHERE id=?
        """, (patient_id, age, gender, duration, symptoms, record_id))
        conn.commit()
        conn.close()
        return redirect("/records")

    cur.execute("SELECT * FROM patients WHERE id=?", (record_id,))
    record = cur.fetchone()
    conn.close()

    return render_template("edit.html", record=record)


# ---------------------------
# DELETE RECORD (PROTECTED)
# ---------------------------
@app.route("/delete/<int:record_id>")
@login_required
def delete(record_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM patients WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
    return redirect("/records")


# ---------------------------
# DOWNLOAD FILE
# ---------------------------
@app.route("/download/<path:filepath>")
@login_required
def download(filepath):
    return send_file(filepath, as_attachment=True)


# ---------------------------
# RUN APP
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
