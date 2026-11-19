"""Prepare manual-review reports for MGB-3. Does not modify dataset files."""

import csv
import hashlib
import random
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import soundfile as sf


DATA_DIR = Path("Data_phase/data/interim/MGB-3")
MANIFEST_PATH = DATA_DIR / "manifest.csv"
REPORT_DIR = Path("Data_phase/reports")

# Reproducible sample sizes and seed.
ELLIPSIS_SAMPLE_SIZE = 20
RANDOM_SAMPLE_SIZE = 50
CPS_OUTLIERS_PER_SIDE = 10
RANDOM_SEED = 42

SOURCE_PATTERN = re.compile(
    r"^(?P<source>.+?)_first_12min_part_(?P<part>\d+)\.wav$",
    re.IGNORECASE,
)


def is_arabic_letter(char: str) -> bool:
    return char.isalpha() and "ARABIC" in unicodedata.name(char, "")


def is_latin_letter(char: str) -> bool:
    return char.isalpha() and "LATIN" in unicodedata.name(char, "")


def get_source_info(filename: str) -> tuple[str, str]:
    match = SOURCE_PATTERN.match(Path(filename).name)
    if not match:
        return "UNPARSED", ""
    return match.group("source"), match.group("part")


def sha256_file(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    with MANIFEST_PATH.open("r", newline="", encoding="utf-8-sig") as file:
        manifest = list(csv.DictReader(file))

    if not manifest:
        raise ValueError("Manifest contains no records.")

    # Add derived measurements; the source audio and text remain unchanged.
    records = []
    for row in manifest:
        transcript = row.get("transcript", "") or ""
        audio_path = DATA_DIR / row["audio_path"]

        if not audio_path.is_file():
            raise FileNotFoundError(f"Missing WAV: {audio_path}")

        duration = sf.info(audio_path).duration
        non_whitespace_chars = len(re.sub(r"\s+", "", transcript))
        chars_per_second = (
            non_whitespace_chars / duration if duration > 0 else 0.0
        )
        source_id, part_number = get_source_info(
            row.get("source_audio_filename", "")
        )

        records.append(
            {
                **row,
                "duration_seconds": round(duration, 3),
                "transcript_characters_no_whitespace": non_whitespace_chars,
                "characters_per_second": round(chars_per_second, 3),
                "source_id_from_filename": source_id,
                "part_number_from_filename": part_number,
            }
        )

    # Select examples for manual review. Reasons are combined if a record
    # matches more than one selection.
    review_reasons = defaultdict(set)

    unclear_records = [
        record for record in records
        if "غير واضح" in record["transcript"]
    ]
    for record in unclear_records:
        review_reasons[record["record_id"]].add("contains غير واضح: review all")

    ellipsis_records = [
        record for record in records
        if "..." in record["transcript"] or "…" in record["transcript"]
    ]
    rng = random.Random(RANDOM_SEED)
    ellipsis_sample = rng.sample(
        ellipsis_records,
        min(ELLIPSIS_SAMPLE_SIZE, len(ellipsis_records)),
    )
    for record in ellipsis_sample:
        review_reasons[record["record_id"]].add(
            f"ellipsis sample (seed={RANDOM_SEED})"
        )

    random_sample = rng.sample(records, min(RANDOM_SAMPLE_SIZE, len(records)))
    for record in random_sample:
        review_reasons[record["record_id"]].add(
            f"random listening sample (seed={RANDOM_SEED})"
        )

    sorted_by_cps = sorted(records, key=lambda item: item["characters_per_second"])
    outlier_count = min(CPS_OUTLIERS_PER_SIDE, len(sorted_by_cps))
    for record in sorted_by_cps[:outlier_count]:
        review_reasons[record["record_id"]].add("lowest transcript characters/sec")
    for record in sorted_by_cps[-outlier_count:]:
        review_reasons[record["record_id"]].add("highest transcript characters/sec")

    record_by_id = {record["record_id"]: record for record in records}
    review_rows = []
    for record_id, reasons in sorted(review_reasons.items()):
        record = record_by_id[record_id]
        review_rows.append(
            {
                "record_id": record_id,
                "review_reasons": "; ".join(sorted(reasons)),
                "source_id_from_filename": record["source_id_from_filename"],
                "part_number_from_filename": record["part_number_from_filename"],
                "audio_path": record["audio_path"],
                "duration_seconds": record["duration_seconds"],
                "characters_per_second": record["characters_per_second"],
                "transcript": record["transcript"],
            }
        )

    review_path = REPORT_DIR / "mgb3_manual_review.csv"
    write_csv(
        review_path,
        review_rows,
        [
            "record_id",
            "review_reasons",
            "source_id_from_filename",
            "part_number_from_filename",
            "audio_path",
            "duration_seconds",
            "characters_per_second",
            "transcript",
        ],
    )

    # Count characters that need a human decision. Arabic and Latin letters,
    # digits, and whitespace are omitted; punctuation and combining marks
    # (including Arabic diacritics) remain visible in the report.
    character_counts = Counter(
        char
        for record in records
        for char in record["transcript"]
        if not char.isspace()
        and not is_arabic_letter(char)
        and not is_latin_letter(char)
        and not char.isnumeric()
    )

    character_rows = []
    for char, count in character_counts.most_common():
        category = unicodedata.category(char)
        character_rows.append(
            {
                "character": char,
                "codepoint": f"U+{ord(char):04X}",
                "unicode_name": unicodedata.name(char, "UNKNOWN"),
                "unicode_category": category,
                "count": count,
            }
        )

    character_path = REPORT_DIR / "mgb3_character_inventory.csv"
    write_csv(
        character_path,
        character_rows,
        ["character", "codepoint", "unicode_name", "unicode_category", "count"],
    )

    # Detect exact duplicate transcripts and exact duplicate WAV contents.
    transcript_groups = defaultdict(list)
    audio_hash_groups = defaultdict(list)
    source_groups = defaultdict(list)

    for record in records:
        transcript_groups[record["transcript"]].append(record)
        source_groups[record["source_id_from_filename"]].append(record)

        wav_path = DATA_DIR / record["audio_path"]
        audio_hash_groups[sha256_file(wav_path)].append(record)

    duplicate_rows = []
    for transcript, group in transcript_groups.items():
        if transcript and len(group) > 1:
            for record in group:
                duplicate_rows.append(
                    {
                        "duplicate_type": "exact_transcript",
                        "duplicate_group": hashlib.sha256(
                            transcript.encode("utf-8")
                        ).hexdigest()[:12],
                        "record_id": record["record_id"],
                        "audio_path": record["audio_path"],
                        "source_id_from_filename": record[
                            "source_id_from_filename"
                        ],
                    }
                )

    for audio_hash, group in audio_hash_groups.items():
        if len(group) > 1:
            for record in group:
                duplicate_rows.append(
                    {
                        "duplicate_type": "identical_audio_sha256",
                        "duplicate_group": audio_hash[:12],
                        "record_id": record["record_id"],
                        "audio_path": record["audio_path"],
                        "source_id_from_filename": record[
                            "source_id_from_filename"
                        ],
                    }
                )

    duplicate_path = REPORT_DIR / "mgb3_duplicates.csv"
    write_csv(
        duplicate_path,
        duplicate_rows,
        [
            "duplicate_type",
            "duplicate_group",
            "record_id",
            "audio_path",
            "source_id_from_filename",
        ],
    )

    # A source ID is only a filename-based hypothesis until we confirm its
    # meaning from dataset documentation or manual inspection.
    source_rows = []
    for source_id, group in sorted(source_groups.items()):
        parts = sorted(
            {
                record["part_number_from_filename"]
                for record in group
                if record["part_number_from_filename"]
            },
            key=int,
        )
        source_rows.append(
            {
                "source_id_from_filename": source_id,
                "record_count": len(group),
                "part_numbers": ", ".join(parts),
            }
        )

    source_path = REPORT_DIR / "mgb3_source_groups.csv"
    write_csv(
        source_path,
        source_rows,
        ["source_id_from_filename", "record_count", "part_numbers"],
    )

    print(f"Manifest records: {len(records)}")
    print(f"Records containing غير واضح: {len(unclear_records)}")
    print(f"Records containing ellipses: {len(ellipsis_records)}")
    print(f"Manual review-list records: {len(review_rows)}")
    print(f"Filename source groups: {len(source_groups)}")
    print(f"Unparsed source filenames: {len(source_groups.get('UNPARSED', []))}")
    print(f"Duplicate report rows: {len(duplicate_rows)}")
    print("\nReports created:")
    print(f"  {review_path}")
    print(f"  {character_path}")
    print(f"  {duplicate_path}")
    print(f"  {source_path}")
    print(
        "\nNote: duplicate and characters-per-second results are review "
        "signals, not automatic exclusion decisions."
    )


if __name__ == "__main__":
    main()