"""
Process the extracted MGB-3 dataset:
1. Ingests data from Data_phase/data/interim/MGB-3/manifest.csv.
2. Filters out records containing inaudible annotations ('غير واضح').
3. Applies bilingual Arabic/English text normalization.
4. Writes the model-ready dataset to Data_phase/data/processed/MGB-3/manifest.csv.
5. Saves an audit trail of excluded records to Data_phase/reports/mgb3_dropped_records.csv.
"""

import csv
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.common.text_normalizer import contains_inaudible_tag, normalize_text

INTERIM_MANIFEST = PROJECT_ROOT / "data" / "interim" / "MGB-3" / "manifest.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "MGB-3"
PROCESSED_MANIFEST = PROCESSED_DIR / "manifest.csv"
DROPPED_REPORT = PROJECT_ROOT / "reports" / "mgb3_dropped_records.csv"


def main():
    if not INTERIM_MANIFEST.is_file():
        raise FileNotFoundError(f"Interim manifest not found at: {INTERIM_MANIFEST}")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    DROPPED_REPORT.parent.mkdir(parents=True, exist_ok=True)

    with INTERIM_MANIFEST.open("r", encoding="utf-8-sig") as f:
        interim_rows = list(csv.DictReader(f))

    print(f"Total interim records to process: {len(interim_rows)}")

    clean_records = []
    dropped_records = []

    for row in interim_rows:
        record_id = row["record_id"]
        raw_text = row["transcript"]

        # Rule 1: Exclude records containing inaudible / unintelligible tags
        if contains_inaudible_tag(raw_text):
            dropped_records.append({
                "record_id": record_id,
                "audio_path": row["audio_path"],
                "source_audio_filename": row["source_audio_filename"],
                "reason": "Contains inaudible marker (غير واضح)",
                "raw_transcript": raw_text
            })
            continue

        # Rule 2: Apply general text normalization (ellipses removal + lowercase English)
        normalized_text = normalize_text(raw_text)

        # Sanity check: Ensure transcript is not empty after stripping noise
        if not normalized_text:
            dropped_records.append({
                "record_id": record_id,
                "audio_path": row["audio_path"],
                "source_audio_filename": row["source_audio_filename"],
                "reason": "Empty transcript after normalization",
                "raw_transcript": raw_text
            })
            continue

        clean_records.append({
            "record_id": record_id,
            "audio_path": row["audio_path"],
            "raw_transcript": raw_text,
            "normalized_transcript": normalized_text,
            "source_shard": row["source_shard"],
            "source_audio_filename": row["source_audio_filename"]
        })

    # Save the processed manifest containing both raw and clean text
    fieldnames = [
        "record_id",
        "audio_path",
        "raw_transcript",
        "normalized_transcript",
        "source_shard",
        "source_audio_filename"
    ]
    with PROCESSED_MANIFEST.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(clean_records)

    # Save dropped records for audit trail and paper documentation
    if dropped_records:
        dropped_fields = ["record_id", "audio_path", "source_audio_filename", "reason", "raw_transcript"]
        with DROPPED_REPORT.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=dropped_fields)
            writer.writeheader()
            writer.writerows(dropped_records)

    print("\n=== Processing Complete ===")
    print(f"Total interim records : {len(interim_rows)}")
    print(f"Retained clean records: {len(clean_records)} ({len(clean_records)/len(interim_rows)*100:.1f}%)")
    print(f"Dropped records       : {len(dropped_records)}")
    print(f"Processed manifest    : {PROCESSED_MANIFEST}")
    print(f"Dropped records report: {DROPPED_REPORT}")


if __name__ == "__main__":
    main()