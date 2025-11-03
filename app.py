from flask import Flask, render_template, request, redirect
import numpy as np
import sqlite3
from PIL import Image
import io

app = Flask(__name__)

# -----------------------------
# 1. Database Setup
# -----------------------------
DB_PATH = "patients.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            age INTEGER,
            gender TEXT,
            duration INTEGER,
            symptoms TEXT,
            cancer_type TEXT,
            severity TEXT,
            urgency TEXT,
            confidence REAL,
            survival_prob REAL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# -----------------------------
# 2. Model Data
# -----------------------------
cancer_symptoms = {
    "Breast Cancer": {
        "Change in breast size or shape": 0.3,
        "Lump in breast or underarm": 0.4,
        "Persistent thickening near breast": 0.35,
        "Skin dimpling or redness on breast": 0.25,
        "Marble-like hardened area under skin": 0.3,
        "Nipple discharge (blood-stained or clear)": 0.35
    },
    "Lung Cancer": {
        "Persistent cough": 0.3,
        "Coughing up blood": 0.4,
        "Shortness of breath": 0.3,
        "Chest pain or discomfort": 0.25,
        "Wheezing": 0.25,
        "Hoarseness": 0.2,
        "Loss of appetite": 0.2,
        "Unexplained weight loss": 0.3,
        "Fatigue or tiredness": 0.2,
        "Shoulder pain": 0.15,
        "Swelling in face or neck": 0.25,
        "Drooping eyelid or uneven pupil": 0.3
    },
    "Prostate Cancer": {
        "Frequent need to pee, especially at night": 0.35,
        "Weak urine flow": 0.25,
        "Pain or burning when peeing": 0.3,
        "Loss of bladder control": 0.2,
        "Loss of bowel control": 0.2,
        "Painful ejaculation or erectile dysfunction": 0.35,
        "Blood in semen or pee": 0.4,
        "Pain in lower back, hip or chest": 0.25
    },
    "Blood Cancer": {
        "Fatigue": 0.3,
        "Shortness of breath": 0.3,
        "Swollen lymph nodes": 0.35,
        "Frequent infections": 0.3,
        "Bone or joint pain": 0.25,
        "Night sweats": 0.25,
        "Enlarged liver or spleen": 0.3,
        "Persistent fever": 0.3,
        "Unexplained weight loss": 0.3,
        "Unusual bruising or bleeding": 0.4
    }
}

# -----------------------------
# 3. Utility Functions
# -----------------------------
def safe_int(value, default):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def analyze_image(image_bytes):
    """Simulated CNN-like image analysis."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('L')
        arr = np.array(img)
        variance = np.var(arr)
        confidence = min(95, max(40, variance / 800))
        return confidence
    except:
        return 0

def survival_prediction(confidence, age):
    base = 0.9 - (confidence / 200) - (age / 300)
    return max(0.1, min(0.99, base))

# -----------------------------
# 4. Routes
# -----------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    if request.method == "POST":
        patient_id = request.form.get("name", "Unknown")
        age = safe_int(request.form.get("age"), 45)
        gender = request.form.get("gender", "Not specified")
        duration = safe_int(request.form.get("duration"), 3)
        selected_symptoms = request.form.getlist("symptoms")

        # Cancer prediction logic
        cancer_scores = {}
        for cancer, symptoms in cancer_symptoms.items():
            score = sum(symptoms.get(s, 0) for s in selected_symptoms)
            cancer_scores[cancer] = score

        likely_cancer = max(cancer_scores, key=cancer_scores.get)
        symptom_score = cancer_scores[likely_cancer]

        symptom_confidence = min(100, 40 + symptom_score * 100)
        if age > 60:
            symptom_confidence += 10
        elif age < 25:
            symptom_confidence -= 5
        if duration > 6:
            symptom_confidence += 10
        elif duration < 1:
            symptom_confidence -= 5
        symptom_confidence = np.clip(symptom_confidence, 0, 100)

        # Image analysis
        image_confidence = 0
        if 'scan' in request.files and request.files['scan'].filename != '':
            image_bytes = request.files['scan'].read()
            image_confidence = analyze_image(image_bytes)

        combined_confidence = (symptom_confidence * 0.6) + (image_confidence * 0.4)

        # Severity and urgency
        if combined_confidence < 50:
            severity, urgency, color = "Low", "Routine Check", "#5cb85c"
        elif combined_confidence < 75:
            severity, urgency, color = "Moderate", "Doctor Visit Recommended", "#f0ad4e"
        else:
            severity, urgency, color = "High", "Immediate Medical Attention", "#d9534f"

        survival_prob = survival_prediction(combined_confidence, age)

        # Save to DB
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO patients (
                patient_id, age, gender, duration, symptoms, cancer_type,
                severity, urgency, confidence, survival_prob
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            patient_id, age, gender, duration, ",".join(selected_symptoms),
            likely_cancer, severity, urgency, combined_confidence, survival_prob
        ))
        conn.commit()
        conn.close()

        # -----------------------------
        # Interpret results into plain medical form
        # -----------------------------
        if combined_confidence >= 60:
            diagnosis = f"Signs suggest possible presence of {likely_cancer}."
        else:
            diagnosis = f"No strong evidence of cancer detected — {likely_cancer} unlikely."

        if survival_prob > 0.75:
            prognosis = "Favorable — good outlook with early detection."
        elif survival_prob > 0.45:
            prognosis = "Monitor closely — treatment likely to improve outcomes."
        else:
            prognosis = "Critical outlook — immediate medical attention advised."

        # Final output (cleaned for UI)
        result = {
            "name": patient_id,
            "age": age,
            "gender": gender,
            "cancer_type": likely_cancer,
            "severity": severity,
            "urgency": urgency,
            "diagnosis": diagnosis,
            "prognosis": prognosis,
            "color": color
        }


    return render_template(
        "index.html",
        symptoms=sorted(set(s for d in cancer_symptoms.values() for s in d)),
        result=result
    )

# -----------------------------
# 5. Record Management
# -----------------------------
@app.route("/records")
def records():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM patients")
    data = c.fetchall()
    conn.close()
    return render_template("records.html", data=data)

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_record(id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if request.method == "POST":
        age = request.form["age"]
        gender = request.form["gender"]
        duration = request.form["duration"]
        cancer_type = request.form["cancer_type"]
        severity = request.form["severity"]
        urgency = request.form["urgency"]

        c.execute("""
            UPDATE patients
            SET age=?, gender=?, duration=?, cancer_type=?, severity=?, urgency=?
            WHERE id=?
        """, (age, gender, duration, cancer_type, severity, urgency, id))
        conn.commit()
        conn.close()
        return redirect("/records")

    c.execute("SELECT * FROM patients WHERE id=?", (id,))
    record = c.fetchone()
    conn.close()
    return render_template("edit.html", record=record)

@app.route("/delete/<int:id>")
def delete_record(id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM patients WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/records")

@app.route("/add", methods=["GET", "POST"])
def add_patient():
    if request.method == "POST":
        patient_id = request.form["patient_id"]
        age = request.form["age"]
        gender = request.form["gender"]
        duration = request.form["duration"]
        symptoms = request.form.get("symptoms", "")
        cancer_type = request.form["cancer_type"]
        severity = request.form["severity"]
        urgency = request.form["urgency"]
        confidence = request.form["confidence"]
        survival = float(request.form["survival"]) / 100

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO patients (patient_id, age, gender, duration, symptoms,
                                  cancer_type, severity, urgency, confidence, survival_prob)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (patient_id, age, gender, duration, symptoms, cancer_type,
              severity, urgency, confidence, survival))
        conn.commit()
        conn.close()
        return redirect("/records")

    return render_template("edit.html", record=None)

# -----------------------------
# 6. Run Server
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
