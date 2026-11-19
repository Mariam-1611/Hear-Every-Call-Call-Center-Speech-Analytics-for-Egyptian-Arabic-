"""Validate extracted MGB-3 WAV files and transcript manifest."""

import csv
from collections import Counter
from pathlib import Path

import soundfile as sf


OUTPUT_DIR = Path("Data_phase/data/interim/MGB-3")
AUDIO_DIR = OUTPUT_DIR / "audio"
MANIFEST_PATH = OUTPUT_DIR / "manifest.csv"


def main() -> None:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")

    with MANIFEST_PATH.open("r", newline="", encoding="utf-8-sig") as csv_file:
        rows = list(csv.DictReader(csv_file))

    required_columns = {
        "record_id",
        "audio_path",
        "transcript",
        "source_shard",
        "source_audio_filename",
    }
    if not rows:
        raise ValueError("The manifest has no data rows.")

    missing_columns = required_columns - set(rows[0].keys())
    if missing_columns:
        raise ValueError(f"Manifest is missing columns: {sorted(missing_columns)}")

    sample_rates = Counter()
    problems = []
    seen_paths = set()
    valid_wavs = 0

    for row_number, row in enumerate(rows, start=2):
        record_id = row["record_id"]
        relative_path = row["audio_path"]
        transcript = row["transcript"]

        if not transcript or not transcript.strip():
            problems.append(f"Row {row_number} ({record_id}): empty transcript")

        if relative_path in seen_paths:
            problems.append(f"Row {row_number} ({record_id}): duplicate audio path")
        seen_paths.add(relative_path)

        wav_path = OUTPUT_DIR / relative_path
        if not wav_path.is_file():
            problems.append(f"Row {row_number} ({record_id}): WAV missing: {wav_path}")
            continue

        try:
            info = sf.info(wav_path)
            if info.frames <= 0 or info.samplerate <= 0:
                problems.append(f"Row {row_number} ({record_id}): empty/invalid WAV")
                continue

            sample_rates[info.samplerate] += 1
            valid_wavs += 1
        except Exception as error:
            problems.append(
                f"Row {row_number} ({record_id}): cannot read WAV: {error}"
            )

    wav_files = list(AUDIO_DIR.glob("*.wav"))
    unlisted_wavs = [
        path for path in wav_files
        if f"audio/{path.name}" not in seen_paths
    ]

    print(f"Manifest rows: {len(rows)}")
    print(f"WAV files in audio folder: {len(wav_files)}")
    print(f"Valid WAV files matched to manifest: {valid_wavs}")
    print(f"Sample-rate counts: {dict(sorted(sample_rates.items()))}")
    print(f"Unlisted WAV files: {len(unlisted_wavs)}")
    print(f"Issues found: {len(problems)}")

    for problem in problems[:30]:
        print(f"  - {problem}")

    if len(problems) > 30:
        print(f"  ... plus {len(problems) - 30} more issues")

    if not problems and not unlisted_wavs and len(rows) == len(wav_files):
        print("\nPASS: every manifest record has a readable WAV and transcript.")
    else:
        print("\nCHECK: review the issues above before continuing.")


if __name__ == "__main__":
    main()