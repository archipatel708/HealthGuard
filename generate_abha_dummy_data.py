"""Generate ABHA-like dummy historical records for local demos.

This script is useful when ABHA APIs are unavailable. It creates:
1) A visit-level synthetic history dataset
2) A disease trend summary showing how repeated patterns become signal
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


OUTPUT_DIR = Path(__file__).resolve().parent / "data"
HISTORY_FILE = OUTPUT_DIR / "abha_dummy_history.csv"
TRENDS_FILE = OUTPUT_DIR / "abha_disease_trends.csv"


def _random_visit_date(days_back: int, rng: np.random.Generator) -> datetime:
    offset = int(rng.integers(0, days_back + 1))
    return datetime.now() - timedelta(days=offset)


def _build_disease_profiles() -> dict:
    return {
        "Common Cold": {
            "symptoms": ["runny_nose", "cough", "throat_irritation", "mild_fever", "congestion"],
            "temperature_mean": 37.8,
            "heart_rate_mean": 84,
        },
        "Viral Fever": {
            "symptoms": ["high_fever", "headache", "fatigue", "chills", "muscle_pain"],
            "temperature_mean": 38.8,
            "heart_rate_mean": 96,
        },
        "GERD": {
            "symptoms": ["acidity", "indigestion", "chest_tightness", "heartburn", "nausea"],
            "temperature_mean": 36.9,
            "heart_rate_mean": 78,
        },
        "Migraine": {
            "symptoms": ["headache", "nausea", "light_sensitivity", "visual_disturbances", "dizziness"],
            "temperature_mean": 36.8,
            "heart_rate_mean": 80,
        },
        "Asthma": {
            "symptoms": ["shortness_of_breath", "wheezing", "chest_tightness", "dry_cough", "rapid_breathing"],
            "temperature_mean": 37.1,
            "heart_rate_mean": 94,
        },
    }


def generate_dummy_history(total_users: int = 120, min_visits: int = 3, max_visits: int = 14, seed: int = 2026) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    profiles = _build_disease_profiles()
    disease_names = list(profiles.keys())
    disease_weights = np.array([0.34, 0.2, 0.18, 0.15, 0.13])

    rows = []
    for user_id in range(1, total_users + 1):
        gender = rng.choice(["M", "F"], p=[0.52, 0.48])
        age = int(rng.integers(18, 75))
        visits = int(rng.integers(min_visits, max_visits + 1))

        for _ in range(visits):
            disease = rng.choice(disease_names, p=disease_weights)
            profile = profiles[disease]

            symptom_count = int(rng.integers(2, 5))
            symptoms = list(rng.choice(profile["symptoms"], size=symptom_count, replace=False))

            temperature = round(float(rng.normal(profile["temperature_mean"], 0.35)), 1)
            heart_rate = int(max(50, rng.normal(profile["heart_rate_mean"], 9)))
            systolic = int(max(90, rng.normal(122, 16)))
            diastolic = int(max(55, rng.normal(79, 10)))

            if disease == "Asthma":
                oxygen = round(float(max(88, rng.normal(93.5, 2.2))), 1)
            else:
                oxygen = round(float(max(90, rng.normal(97.2, 1.4))), 1)

            visit_date = _random_visit_date(365, rng)
            note_text = (
                f"Patient reports {', '.join(symptoms)} for 1-3 days. "
                "Symptoms were converted from narrative text before model prediction."
            )

            rows.append(
                {
                    "user_id": user_id,
                    "visit_date": visit_date.date().isoformat(),
                    "age": age,
                    "gender": gender,
                    "symptom_text": note_text,
                    "interpreted_symptoms": json.dumps(symptoms),
                    "blood_pressure": f"{systolic}/{diastolic}",
                    "heart_rate": heart_rate,
                    "temperature": temperature,
                    "oxygen_saturation": oxygen,
                    "diagnosed_disease": disease,
                }
            )

    history_df = pd.DataFrame(rows).sort_values(["visit_date", "user_id"], ascending=[False, True])
    return history_df


def build_trend_summary(history_df: pd.DataFrame) -> pd.DataFrame:
    disease_counts = history_df.groupby("diagnosed_disease").size().rename("total_cases")

    recent_df = history_df.copy()
    recent_df["visit_date"] = pd.to_datetime(recent_df["visit_date"])
    window_start = pd.Timestamp(datetime.now().date() - timedelta(days=90))
    last_90_days = recent_df[recent_df["visit_date"] >= window_start]
    recent_counts = last_90_days.groupby("diagnosed_disease").size().rename("cases_last_90_days")

    user_recurrence = (
        history_df.groupby(["user_id", "diagnosed_disease"]).size().reset_index(name="user_disease_count")
    )
    recurrence_score = (
        user_recurrence.groupby("diagnosed_disease")["user_disease_count"].mean().rename("avg_recurrence_per_user")
    )

    summary = pd.concat([disease_counts, recent_counts, recurrence_score], axis=1).fillna(0)
    summary["cases_last_90_days"] = summary["cases_last_90_days"].astype(int)
    summary["total_cases"] = summary["total_cases"].astype(int)
    summary["signal_strength"] = (
        summary["cases_last_90_days"] * 0.6 + summary["avg_recurrence_per_user"] * 25
    ).round(2)

    return summary.sort_values("signal_strength", ascending=False).reset_index()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    history_df = generate_dummy_history()
    trends_df = build_trend_summary(history_df)

    history_df.to_csv(HISTORY_FILE, index=False)
    trends_df.to_csv(TRENDS_FILE, index=False)

    print(f"Saved: {HISTORY_FILE}")
    print(f"Saved: {TRENDS_FILE}")
    print("\nTop disease trend signals:")
    print(trends_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
