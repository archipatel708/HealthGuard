"""
train.py — Train a Random Forest Classifier for disease prediction.
Run this once to generate model/model.pkl and model/symptom_list.pkl.
"""

import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")


def train_and_save_model(base_dir=BASE_DIR, model_dir=MODEL_DIR):
    """Train model artifacts from source CSVs and persist them to disk."""
    os.makedirs(model_dir, exist_ok=True)

    symptoms_df = pd.read_csv(os.path.join(base_dir, "symtoms_df.csv"), index_col=0)
    severity_df = pd.read_csv(os.path.join(base_dir, "Symptom-severity.csv"))

    severity_df["Symptom"] = severity_df["Symptom"].str.strip().str.lower()
    severity_df = severity_df[severity_df["Symptom"] != "prognosis"]

    severity_map = dict(zip(severity_df["Symptom"], severity_df["weight"]))
    all_symptoms = sorted(severity_map.keys())
    symptom_index = {symptom: idx for idx, symptom in enumerate(all_symptoms)}

    print(f"Total unique symptoms: {len(all_symptoms)}")

    symptom_cols = [column for column in symptoms_df.columns if column.startswith("Symptom_")]
    for column in symptom_cols:
        symptoms_df[column] = symptoms_df[column].astype(str).str.strip().str.lower()

    sample_count = len(symptoms_df)
    X = np.zeros((sample_count, len(all_symptoms)), dtype=np.float32)

    for row_number, (_, row) in enumerate(symptoms_df.iterrows()):
        for column in symptom_cols:
            value = row[column]
            if pd.isna(value):
                continue
            symptom = str(value).strip().lower()
            if symptom in symptom_index:
                X[row_number, symptom_index[symptom]] = severity_map[symptom]

    y = symptoms_df["Disease"].str.strip().values
    disease_classes = sorted(set(y))
    print(f"Total diseases: {len(disease_classes)}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=None,
        min_samples_split=2,
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Test accuracy: {accuracy * 100:.2f}%")

    joblib.dump(clf, os.path.join(model_dir, "model.pkl"))
    joblib.dump(all_symptoms, os.path.join(model_dir, "symptom_list.pkl"))
    joblib.dump(severity_map, os.path.join(model_dir, "severity_map.pkl"))

    print("Saved → model/model.pkl, model/symptom_list.pkl, model/severity_map.pkl")
    return clf, all_symptoms, severity_map


if __name__ == "__main__":
    train_and_save_model()
