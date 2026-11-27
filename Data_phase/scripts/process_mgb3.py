"""Process MGB-3 using explicit, manually reviewed record decisions.

The original interim manifest is preserved. Corrections are applied by record ID
and saved in a separate reviewed transcript column. Excluded records are logged.
"""

import csv
import random
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.common.text_normalizer import normalize_text

INTERIM_MANIFEST = PROJECT_ROOT / "data" / "interim" / "MGB-3" / "manifest.csv"
DECISIONS_FILE = PROJECT_ROOT / "configs" / "mgb3_manual_decisions.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "MGB-3"
PROCESSED_MANIFEST = PROCESSED_DIR / "manifest.csv"
DROPPED_REPORT = PROJECT_ROOT / "reports" / "mgb3_dropped_records.csv"
ELLIPSIS_REVIEW = PROJECT_ROOT / "reports" / "mgb3_ellipsis_review.csv"
ELLIPSIS_INVENTORY = PROJECT_ROOT / "reports" / "mgb3_ellipsis_inventory.csv"
ELLIPSIS_SAMPLE_SIZE = 30
ELLIPSIS_SAMPLE_PER_GROUP = 6
ELLIPSIS_SAMPLE_SEED = 42

# Includes the underscore used to mark the annotation in mgb3_000022.
ANNOTATION_PATTERN = re.compile(r"_?غير\s+واضح")
ALLOWED_DECISIONS = {"replace", "exclude"}


def load_manual_decisions() -> dict[str, dict[str, str]]:
    if not DECISIONS_FILE.is_file():
        raise FileNotFoundError(f"Manual decisions file not found: {DECISIONS_FILE}")

    with DECISIONS_FILE.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    decisions = {}
    for row in rows:
        record_id = (row.get("record_id") or "").strip()
        decision = (row.get("decision") or "").strip().lower()
        replacement = row.get("replacement") or ""
        reason = (row.get("reason") or "").strip()

        if not record_id:
            raise ValueError("Manual decision row has no record_id")
        if record_id in decisions:
            raise ValueError(f"Duplicate manual decision for {record_id}")
        if decision not in ALLOWED_DECISIONS:
            raise ValueError(f"Unsupported decision '{decision}' for {record_id}")
        if decision == "replace" and not replacement.strip():
            raise ValueError(f"Replacement text is empty for {record_id}")
        if decision == "exclude" and replacement.strip():
            raise ValueError(f"Excluded record {record_id} must not have replacement text")

        decisions[record_id] = {
            "decision": decision,
            "replacement": replacement,
            "reason": reason,
        }

    return decisions


def ellipsis_pattern_group(text: str, ellipsis_pattern: re.Pattern) -> str:
    """Assign one reproducible review stratum based on visible marker form."""
    if "…" in text:
        return "unicode_ellipsis"
    if re.search(r"^\s*\.{2,}", text):
        return "leading_dots"
    if re.search(r"\.{2,}\s*$", text):
        return "trailing_dots"
    if len(ellipsis_pattern.findall(text)) >= 3:
        return "many_internal_dots"
    return "internal_dots"


def select_ellipsis_review_sample(rows: list[dict]) -> list[dict]:
    """Select a deterministic, roughly balanced sample across marker forms."""
    rng = random.Random(ELLIPSIS_SAMPLE_SEED)
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["ellipsis_pattern_group"], []).append(row)

    selected: dict[str, dict] = {}
    for group_name in sorted(groups):
        group_rows = groups[group_name]
        count = min(ELLIPSIS_SAMPLE_PER_GROUP, len(group_rows))
        for row in rng.sample(group_rows, count):
            selected[row["record_id"]] = row

    # Fill unused quota from the remaining rows if a stratum has fewer than
    # six examples. The fixed seed makes the same sample reproducible.
    remaining = [row for row in rows if row["record_id"] not in selected]
    needed = min(ELLIPSIS_SAMPLE_SIZE, len(rows)) - len(selected)
    if needed > 0:
        for row in rng.sample(remaining, min(needed, len(remaining))):
            selected[row["record_id"]] = row

    return sorted(selected.values(), key=lambda row: row["record_id"])


def main() -> None:
    if not INTERIM_MANIFEST.is_file():
        raise FileNotFoundError(f"Interim manifest not found: {INTERIM_MANIFEST}")

    decisions = load_manual_decisions()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    DROPPED_REPORT.parent.mkdir(parents=True, exist_ok=True)

    with INTERIM_MANIFEST.open("r", newline="", encoding="utf-8-sig") as file:
        interim_rows = list(csv.DictReader(file))

    record_ids = {row["record_id"] for row in interim_rows}
    missing_decision_records = set(decisions) - record_ids
    if missing_decision_records:
        raise ValueError(
            "Decision file contains IDs absent from the interim manifest: "
            + ", ".join(sorted(missing_decision_records))
        )

    # Every current candidate must have a human decision. New markers cannot be
    # silently filtered or passed through without review.
    candidate_ids = {
        row["record_id"]
        for row in interim_rows
        if ANNOTATION_PATTERN.search(row.get("transcript", ""))
    }
    undecided_ids = candidate_ids - set(decisions)
    decisions_without_marker = set(decisions) - candidate_ids
    if undecided_ids or decisions_without_marker:
        raise ValueError(
            "Manual decisions do not match marker candidates. "
            f"Undecided candidates: {sorted(undecided_ids)}; "
            f"decision IDs without marker: {sorted(decisions_without_marker)}"
        )

    clean_records = []
    dropped_records = []
    ellipsis_inventory_rows = []
    ellipsis_pattern = re.compile(r"(?:\.{2,}|…)")

    for row in interim_rows:
        record_id = row["record_id"]
        raw_text = row.get("transcript", "") or ""
        manual = decisions.get(record_id)
        reviewed_text = raw_text

        if manual and manual["decision"] == "exclude":
            dropped_records.append(
                {
                    "record_id": record_id,
                    "audio_path": row.get("audio_path", ""),
                    "source_audio_filename": row.get("source_audio_filename", ""),
                    "decision": "exclude",
                    "reason": manual["reason"],
                    "raw_transcript": raw_text,
                }
            )
            continue

        if manual and manual["decision"] == "replace":
            reviewed_text, replacements = ANNOTATION_PATTERN.subn(
                lambda _match: manual["replacement"],
                raw_text,
                count=1,
            )
            if replacements != 1:
                raise ValueError(
                    f"Expected one annotation to replace in {record_id}; "
                    f"found {replacements}"
                )

        # Keep distinct derived views so the effect of removing ellipses can be
        # compared without also normalizing taa marbuta or alef maqsura.
        normalized_conservative = normalize_text(reviewed_text)
        normalized_no_ellipses = normalize_text(
            reviewed_text,
            remove_ellipses=True,
        )
        # Retain this combined variant for the existing broad comparison only;
        # it is not a controlled test of ellipsis removal by itself.
        normalized_aggressive = normalize_text(
            reviewed_text,
            remove_ellipses=True,
            normalize_taa_marbuta=True,
            normalize_alef_maqsura=True,
        )
        if not normalized_conservative:
            dropped_records.append(
                {
                    "record_id": record_id,
                    "audio_path": row.get("audio_path", ""),
                    "source_audio_filename": row.get("source_audio_filename", ""),
                    "decision": "exclude",
                    "reason": "Empty transcript after normalization",
                    "raw_transcript": raw_text,
                }
            )
            continue

        clean_records.append(
            {
                "record_id": record_id,
                "audio_path": row.get("audio_path", ""),
                "raw_transcript": raw_text,
                "reviewed_transcript": reviewed_text,
                "normalized_conservative": normalized_conservative,
                "normalized_no_ellipses": normalized_no_ellipses,
                "normalized_aggressive": normalized_aggressive,
                "source_shard": row.get("source_shard", ""),
                "source_audio_filename": row.get("source_audio_filename", ""),
            }
        )

        ellipses = ellipsis_pattern.findall(reviewed_text)
        if ellipses:
            ellipsis_inventory_rows.append(
                {
                    "record_id": record_id,
                    "audio_path": row.get("audio_path", ""),
                    "ellipsis_count": len(ellipses),
                    "ellipsis_pattern_group": ellipsis_pattern_group(
                        reviewed_text, ellipsis_pattern
                    ),
                    "reviewed_transcript": reviewed_text,
                    "audio_review_category": "",
                    "review_notes": "",
                }
            )

    processed_fields = [
        "record_id",
        "audio_path",
        "raw_transcript",
        "reviewed_transcript",
        "normalized_conservative",
        "normalized_no_ellipses",
        "normalized_aggressive",
        "source_shard",
        "source_audio_filename",
    ]
    with PROCESSED_MANIFEST.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=processed_fields)
        writer.writeheader()
        writer.writerows(clean_records)

    dropped_fields = [
        "record_id",
        "audio_path",
        "source_audio_filename",
        "decision",
        "reason",
        "raw_transcript",
    ]
    with DROPPED_REPORT.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=dropped_fields)
        writer.writeheader()
        writer.writerows(dropped_records)

    ellipsis_fields = [
        "record_id",
        "audio_path",
        "ellipsis_count",
        "ellipsis_pattern_group",
        "reviewed_transcript",
        "audio_review_category",
        "review_notes",
    ]

    def write_ellipsis_report(path: Path, rows: list[dict]) -> None:
        with path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=ellipsis_fields)
            writer.writeheader()
            writer.writerows(rows)

    ellipsis_review_sample = select_ellipsis_review_sample(ellipsis_inventory_rows)
    write_ellipsis_report(ELLIPSIS_INVENTORY, ellipsis_inventory_rows)
    write_ellipsis_report(ELLIPSIS_REVIEW, ellipsis_review_sample)

    print("=== Manual MGB-3 Processing Summary ===")
    print(f"Interim records       : {len(interim_rows)}")
    print(f"Manually corrected    : {sum(d['decision'] == 'replace' for d in decisions.values())}")
    print(f"Manually excluded     : {sum(d['decision'] == 'exclude' for d in decisions.values())}")
    print(f"Processed records     : {len(clean_records)}")
    print(f"Dropped records       : {len(dropped_records)}")
    print(f"Processed manifest    : {PROCESSED_MANIFEST}")
    print(f"Dropped records report: {DROPPED_REPORT}")
    print(f"Ellipsis inventory    : {ELLIPSIS_INVENTORY} ({len(ellipsis_inventory_rows)} records)")
    print(
        f"Ellipsis review sample: {ELLIPSIS_REVIEW} "
        f"({len(ellipsis_review_sample)} records, seed={ELLIPSIS_SAMPLE_SEED})"
    )


if __name__ == "__main__":
    main()
