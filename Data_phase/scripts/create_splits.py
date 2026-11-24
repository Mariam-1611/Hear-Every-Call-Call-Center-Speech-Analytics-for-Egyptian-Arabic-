"""
Create source-disjoint dataset splits (Train / Val / Test) using GroupShuffleSplit.

Design:
- Keeps clips with the same filename-derived source ID in one partition.
- Generates approximately 80% Train, 10% Validation, and 10% Test partitions.
- Asserts zero source-ID overlap between partitions.

The filename-derived ID identifies a source program/recording group; it is not
verified speaker metadata, so this script does not claim speaker-independent splits.
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

# Extracts source ID (e.g., 'comedy_78') from a source audio filename.
SOURCE_PATTERN = re.compile(r"^(?P<source>.+?)_first_12min_part_\d+\.wav$", re.IGNORECASE)
RANDOM_SEED = 42


def get_source_group(filename: str) -> str:
    """Extract the filename-derived recording source ID."""
    match = SOURCE_PATTERN.match(Path(filename).name)
    if not match:
        raise ValueError(f"Cannot derive a source group from filename: {filename!r}")
    return match.group("source")


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

    if not records:
        raise ValueError(f"Processed manifest contains no records: {PROCESSED_MANIFEST}")

    # Extract and retain source groups so each split is auditable.
    groups = [get_source_group(r["source_audio_filename"]) for r in records]
    for record, group in zip(records, groups):
        record["source_group"] = group
    fieldnames = list(records[0].keys())

    # Partition 1: Split into approximately 80% Train and 20% Temporary.
    gss_train = GroupShuffleSplit(n_splits=1, train_size=0.80, random_state=RANDOM_SEED)
    train_idx, temp_idx = next(gss_train.split(records, groups=groups))

    train_records = [records[i] for i in train_idx]
    temp_records = [records[i] for i in temp_idx]
    temp_groups = [groups[i] for i in temp_idx]

    # Partition 2: Split remaining source groups equally between Val and Test.
    gss_val = GroupShuffleSplit(n_splits=1, train_size=0.50, random_state=RANDOM_SEED)
    val_idx, test_idx = next(gss_val.split(temp_records, groups=temp_groups))

    val_records = [temp_records[i] for i in val_idx]
    test_records = [temp_records[i] for i in test_idx]

    # Write split manifest files
    save_manifest(TRAIN_SPLIT, train_records, fieldnames)
    save_manifest(VAL_SPLIT, val_records, fieldnames)
    save_manifest(TEST_SPLIT, test_records, fieldnames)

    # Verify zero source-group overlap across partitions.
    train_sources = {r["source_group"] for r in train_records}
    val_sources = {r["source_group"] for r in val_records}
    test_sources = {r["source_group"] for r in test_records}

    assert train_sources.isdisjoint(val_sources), "Data leakage detected between Train and Val!"
    assert train_sources.isdisjoint(test_sources), "Data leakage detected between Train and Test!"
    assert val_sources.isdisjoint(test_sources), "Data leakage detected between Val and Test!"

    print("=== Data Splits Summary (Source-Disjoint) ===")
    print(f"Total processed records : {len(records)}")
    print(f"Train records           : {len(train_records)} ({len(train_records)/len(records)*100:.1f}%) | Groups: {len(train_sources)}")
    print(f"Val records             : {len(val_records)} ({len(val_records)/len(records)*100:.1f}%) | Groups: {len(val_sources)}")
    print(f"Test records            : {len(test_records)} ({len(test_records)/len(records)*100:.1f}%) | Groups: {len(test_sources)}")
    print("\nFiles generated:")
    print(f"  - {TRAIN_SPLIT}")
    print(f"  - {VAL_SPLIT}")
    print(f"  - {TEST_SPLIT}")
    print("\nVerification: Zero filename-derived source-group overlap confirmed.")
    print("Note: source groups are not verified speaker identities.")


if __name__ == "__main__":
    main()
