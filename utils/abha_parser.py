import csv
import random
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
CSV_PATH = BASE_DIR / "dummy_health_data.csv"


def parse_dummy_health_data() -> list[dict]:
    records = []
    with open(CSV_PATH, "r", encoding="utf-8") as file_obj:
        reader = csv.DictReader(file_obj)
        for row in reader:
            records.append(
                {
                    "record_id": row.get("record_id", ""),
                    "condition": row.get("condition", ""),
                    "medication": row.get("medication", ""),
                    "last_visit": row.get("last_visit", ""),
                    "notes": row.get("notes", ""),
                }
            )
    return records


def pick_random_records(records: list[dict]) -> list[dict]:
    if not records:
        return []
    count = random.randint(2, min(5, len(records)))
    return random.sample(records, count)
