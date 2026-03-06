"""
train.py — Train a Random Forest Classifier for disease prediction.
Run this once to generate model/model.pkl and model/symptom_list.pkl.
"""

import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")
os.makedirs(MODEL_DIR, exist_ok=True)

# ── Load datasets ──────────────────────────────────────────────────────────────
symptoms_df = pd.read_csv(os.path.join(BASE_DIR, "symtoms_df.csv"), index_col=0)
severity_df = pd.read_csv(os.path.join(BASE_DIR, "Symptom-severity.csv"))

# ── Build canonical symptom list from severity file ───────────────────────────
# Strip whitespace and lower-case for consistent matching
severity_df["Symptom"] = severity_df["Symptom"].str.strip().str.lower()
severity_df = severity_df[severity_df["Symptom"] != "prognosis"]   # drop sentinel row

severity_map = dict(zip(severity_df["Symptom"], severity_df["weight"]))
all_symptoms = sorted(severity_map.keys())
symptom_index = {s: i for i, s in enumerate(all_symptoms)}

print(f"Total unique symptoms: {len(all_symptoms)}")

# ── Clean symptoms_df ─────────────────────────────────────────────────────────
symptom_cols = [c for c in symptoms_df.columns if c.startswith("Symptom_")]

for col in symptom_cols:
    symptoms_df[col] = symptoms_df[col].astype(str).str.strip().str.lower()

# ── Build feature matrix (weighted one-hot) ───────────────────────────────────
n = len(symptoms_df)
X = np.zeros((n, len(all_symptoms)), dtype=np.float32)

for i, (row_idx, row) in enumerate(symptoms_df.iterrows()):
    for col in symptom_cols:
        val = row[col]
        if pd.isna(val):
            continue
        sym = str(val).strip().lower()
        if sym in symptom_index:
            X[i, symptom_index[sym]] = severity_map[sym]

y = symptoms_df["Disease"].str.strip().values
disease_classes = sorted(set(y))
print(f"Total diseases: {len(disease_classes)}")

# ── Train / test split ────────────────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# ── Train Random Forest ───────────────────────────────────────────────────────
clf = RandomForestClassifier(
    n_estimators=200,
    max_depth=None,
    min_samples_split=2,
    random_state=42,
    n_jobs=-1,
)
clf.fit(X_train, y_train)

# ── Evaluate ──────────────────────────────────────────────────────────────────
y_pred = clf.predict(X_test)
acc = accuracy_score(y_test, y_pred)
print(f"Test accuracy: {acc * 100:.2f}%")

# ── Persist artefacts ─────────────────────────────────────────────────────────
joblib.dump(clf, os.path.join(MODEL_DIR, "model.pkl"))
joblib.dump(all_symptoms, os.path.join(MODEL_DIR, "symptom_list.pkl"))
joblib.dump(severity_map, os.path.join(MODEL_DIR, "severity_map.pkl"))

print("Saved → model/model.pkl, model/symptom_list.pkl, model/severity_map.pkl")
