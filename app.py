"""
app.py — Flask backend that serves the disease prediction API and the frontend.

Endpoints:
  GET  /                     → serves templates/index.html
  GET  /api/symptoms         → returns JSON list of all symptoms
  POST /api/predict          → accepts {"symptoms": [...]} → returns prediction
"""

import os
import numpy as np
import pandas as pd
import joblib
from flask import Flask, jsonify, render_template, request, abort

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")

# ── Load model artefacts ──────────────────────────────────────────────────────
clf = joblib.load(os.path.join(MODEL_DIR, "model.pkl"))
all_symptoms = joblib.load(os.path.join(MODEL_DIR, "symptom_list.pkl"))
severity_map = joblib.load(os.path.join(MODEL_DIR, "severity_map.pkl"))
symptom_index = {s: i for i, s in enumerate(all_symptoms)}

# ── Load reference datasets ───────────────────────────────────────────────────
description_df = pd.read_csv(os.path.join(BASE_DIR, "description.csv"))
description_df.columns = description_df.columns.str.strip()
description_df["Disease"] = description_df["Disease"].str.strip()
desc_map = dict(zip(description_df["Disease"], description_df["Description"]))

precautions_df = pd.read_csv(os.path.join(BASE_DIR, "precautions_df.csv"), index_col=0)
precautions_df.columns = precautions_df.columns.str.strip()
precautions_df["Disease"] = precautions_df["Disease"].str.strip()
prec_map = {}
for _, row in precautions_df.iterrows():
    precs = [str(row[c]).strip() for c in ["Precaution_1", "Precaution_2", "Precaution_3", "Precaution_4"]
             if pd.notna(row[c]) and str(row[c]).strip() not in ("", "nan")]
    prec_map[row["Disease"]] = precs

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates", static_folder="static")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/symptoms", methods=["GET"])
def get_symptoms():
    """Return the full list of symptoms (display-friendly labels)."""
    display = [s.replace("_", " ").title() for s in all_symptoms]
    return jsonify([{"value": s, "label": d} for s, d in zip(all_symptoms, display)])


@app.route("/api/predict", methods=["POST"])
def predict():
    data = request.get_json(force=True, silent=True)
    if not data or "symptoms" not in data:
        abort(400, "Request body must be JSON with a 'symptoms' array.")

    raw_symptoms = data["symptoms"]
    if not isinstance(raw_symptoms, list):
        abort(400, "'symptoms' must be an array.")

    # Sanitise input: keep only known symptoms, strip whitespace, lower-case
    chosen = []
    unknown = []
    for s in raw_symptoms:
        clean = str(s).strip().lower()
        if clean in symptom_index:
            chosen.append(clean)
        else:
            unknown.append(s)

    if not chosen:
        abort(400, "None of the supplied symptoms were recognised.")

    # Build feature vector
    vec = np.zeros((1, len(all_symptoms)), dtype=np.float32)
    for s in chosen:
        vec[0, symptom_index[s]] = severity_map[s]

    disease = clf.predict(vec)[0]
    # Get top-3 predictions with probabilities
    proba = clf.predict_proba(vec)[0]
    top3_idx = np.argsort(proba)[::-1][:3]
    top3 = [
        {"disease": clf.classes_[i], "probability": round(float(proba[i]) * 100, 1)}
        for i in top3_idx
        if proba[i] > 0
    ]

    return jsonify({
        "disease": disease,
        "description": desc_map.get(disease, "No description available."),
        "precautions": prec_map.get(disease, []),
        "top3": top3,
        "unknown_symptoms": unknown,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
