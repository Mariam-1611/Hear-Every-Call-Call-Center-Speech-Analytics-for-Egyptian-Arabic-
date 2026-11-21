"""
Create speaker-disjoint dataset splits (Train / Val / Test) using GroupShuffleSplit.

Design:
- Prevents acoustic and speaker data leakage by grouping clips by their source program.
- Generates 80% Train, 10% Validation, and 10% Test partitions.
- Asserts zero overlap between subsets to guarantee academic evaluation integrity.
"""

import csv
import re
import sys
from pathlib import Path
from sklearn.model_selection import GroupShuffleSplit

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_MANIFEST = PROJECT_ROOT / "data" / "processed" / "MGB-3" / "manifest.csv"
MANIFESTS_DIR = PROJECT_ROOT / "data" / "manifests"

TRAIN_SPLIT = MANIFESTS_DIR / "train_manifest.csv"
VAL_SPLIT = MANIFESTS_DIR / "val_manifest.csv"
TEST_SPLIT = MANIFESTS_DIR / "test_manifest.csv"

# Extracts the parent show/speaker ID (e.g., 'comedy_78' from 'comedy_78_first_12min_part_0.wav')
SOURCE_PATTERN = re.compile(r"^(?P<source>.+?)_first_12min_part_\d+\.wav$", re.IGNORECASE)
RANDOM_SEED = 42


def get_source_group(filename: str) -> str:
    """Extract source show/speaker ID for group-based splitting."""
    match = SOURCE_PATTERN.match(Path(filename).name)
    return match.group("source") if match else "unknown_group"


def save_manifest(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    """Save a split manifest to disk."""
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    if not PROCESSED_MANIFEST.is_file():
        raise FileNotFoundError(f"Processed manifest not found: {PROCESSED_MANIFEST}")

    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    with PROCESSED_MANIFEST.open("r", encoding="utf-8-sig") as f:
        records = list(csv.DictReader(f))

    fieldnames = list(records[0].keys())

    # Extract source groups for all records
    groups = [get_source_group(r["source_audio_filename"]) for r in records]

    # Partition 1: Split into 80% Train and 20% Temporary (Val + Test)
    gss_train = GroupShuffleSplit(n_splits=1, train_size=0.80, random_state=RANDOM_SEED)
    train_idx, temp_idx = next(gss_train.split(records, groups=groups))

    train_records = [records[i] for i in train_idx]
    temp_records = [records[i] for i in temp_idx]
    temp_groups = [groups[i] for i in temp_idx]

    # Partition 2: Split the 20% remaining equally into 10% Val and 10% Test (50/50 split)
    gss_val = GroupShuffleSplit(n_splits=1, train_size=0.50, random_state=RANDOM_SEED)
    val_idx, test_idx = next(gss_val.split(temp_records, groups=temp_groups))

    val_records = [temp_records[i] for i in val_idx]
    test_records = [temp_records[i] for i in test_idx]

    # Write split manifest files
    save_manifest(TRAIN_SPLIT, train_records, fieldnames)
    save_manifest(VAL_SPLIT, val_records, fieldnames)
    save_manifest(TEST_SPLIT, test_records, fieldnames)

    # Academic sanity verification: Ensure zero group overlap across partitions
    train_sources = {get_source_group(r["source_audio_filename"]) for r in train_records}
    val_sources = {get_source_group(r["source_audio_filename"]) for r in val_records}
    test_sources = {get_source_group(r["source_audio_filename"]) for r in test_records}

    assert train_sources.isdisjoint(val_sources), "Data leakage detected between Train and Val!"
    assert train_sources.isdisjoint(test_sources), "Data leakage detected between Train and Test!"
    assert val_sources.isdisjoint(test_sources), "Data leakage detected between Val and Test!"

    print("=== Data Splits Summary (Speaker-Disjoint) ===")
    print(f"Total processed records : {len(records)}")
    print(f"Train records           : {len(train_records)} ({len(train_records)/len(records)*100:.1f}%) | Groups: {len(train_sources)}")
    print(f"Val records             : {len(val_records)} ({len(val_records)/len(records)*100:.1f}%) | Groups: {len(val_sources)}")
    print(f"Test records            : {len(test_records)} ({len(test_records)/len(records)*100:.1f}%) | Groups: {len(test_sources)}")
    print("\nFiles generated:")
    print(f"  - {TRAIN_SPLIT}")
    print(f"  - {VAL_SPLIT}")
    print(f"  - {TEST_SPLIT}")
    print("\nVerification: Zero speaker/program leakage across all splits confirmed.")


if __name__ == "__main__":
    main()