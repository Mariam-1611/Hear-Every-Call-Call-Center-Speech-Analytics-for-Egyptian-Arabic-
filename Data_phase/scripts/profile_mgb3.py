"""Profile MGB-3 audio and transcripts without modifying them."""

import csv
import math
import statistics
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf


DATA_DIR = Path("Data_phase/data/interim/MGB-3")
MANIFEST_PATH = DATA_DIR / "manifest.csv"
AUDIO_DIR = DATA_DIR / "audio"
REPORT_DIR = Path("Data_phase/reports")
REPORT_PATH = REPORT_DIR / "mgb3_quality_profile.csv"

# Diagnostic thresholds, not automatic cleaning rules.
FRAME_DURATION_SECONDS = 0.020  # 20 ms
QUIET_THRESHOLD_DBFS = -60.0
NEAR_CLIP_THRESHOLD = 0.999


def count_character_types(text: str) -> tuple[int, int]:
    """Count Arabic-script and Latin-script alphabetic characters."""
    arabic_count = 0
    latin_count = 0

    for char in text:
        if not char.isalpha():
            continue

        name = unicodedata.name(char, "")
        if "ARABIC" in name:
            arabic_count += 1
        elif "LATIN" in name:
            latin_count += 1

    return arabic_count, latin_count


def measure_audio(audio_path: Path) -> dict:
    """Read audio and calculate descriptive measurements."""
    samples, sample_rate = sf.read(
        audio_path,
        dtype="float32",
        always_2d=True,
    )

    frame_count, channel_count = samples.shape
    duration = frame_count / sample_rate

    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0

    rms_dbfs = (
        20.0 * math.log10(rms)
        if rms > 0
        else float("-inf")
    )

    near_clip_fraction = (
        float(np.mean(np.abs(samples) >= NEAR_CLIP_THRESHOLD))
        if samples.size
        else 0.0
    )

    # Measure the proportion of 20 ms frames below the quiet threshold.
    frame_length = max(1, int(sample_rate * FRAME_DURATION_SECONDS))
    quiet_threshold = 10 ** (QUIET_THRESHOLD_DBFS / 20.0)
    quiet_frames = 0
    total_frames = 0

    for start in range(0, frame_count, frame_length):
        frame = samples[start : start + frame_length]
        frame_rms = float(np.sqrt(np.mean(np.square(frame))))
        quiet_frames += frame_rms < quiet_threshold
        total_frames += 1

    quiet_frame_fraction = quiet_frames / total_frames if total_frames else 0.0

    return {
        "duration_seconds": round(duration, 3),
        "sample_rate_hz": sample_rate,
        "channels": channel_count,
        "subtype": sf.info(audio_path).subtype,
        "peak_abs": round(peak, 6),
        "rms_dbfs": round(rms_dbfs, 2) if math.isfinite(rms_dbfs) else "-inf",
        "near_clip_sample_fraction": round(near_clip_fraction, 8),
        "quiet_frame_fraction_below_minus_60_dbfs": round(
            quiet_frame_fraction, 4
        ),
    }


def main() -> None:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    with MANIFEST_PATH.open("r", newline="", encoding="utf-8-sig") as csv_file:
        rows = list(csv.DictReader(csv_file))

    if not rows:
        raise ValueError("The manifest has no records.")

    report_rows = []
    errors = []

    for row_number, row in enumerate(rows, start=2):
        transcript = row.get("transcript", "") or ""
        audio_path = DATA_DIR / row["audio_path"]

        if not audio_path.is_file():
            errors.append(f"Manifest row {row_number}: missing audio {audio_path}")
            continue

        try:
            audio_stats = measure_audio(audio_path)
        except Exception as error:
            errors.append(f"Manifest row {row_number}: {audio_path.name}: {error}")
            continue

        arabic_chars, latin_chars = count_character_types(transcript)

        report_rows.append(
            {
                "record_id": row.get("record_id", ""),
                "audio_path": row["audio_path"],
                "transcript_chars": len(transcript),
                "transcript_words_whitespace_split": len(transcript.split()),
                "arabic_letter_count": arabic_chars,
                "latin_letter_count": latin_chars,
                "contains_ellipsis": "..." in transcript or "…" in transcript,
                "contains_unclear_marker": "غير واضح" in transcript,
                **audio_stats,
            }
        )

    if not report_rows:
        raise RuntimeError("No records could be profiled.")

    fieldnames = list(report_rows[0].keys())
    with REPORT_PATH.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)

    print(f"Records in manifest: {len(rows)}")
    print(f"Records profiled: {len(report_rows)}")
    print(f"Records with errors: {len(errors)}")
    print(f"Detailed report: {REPORT_PATH}")

    durations = [row["duration_seconds"] for row in report_rows]
    transcript_lengths = [row["transcript_chars"] for row in report_rows]
    sample_rates = sorted({row["sample_rate_hz"] for row in report_rows})
    channel_counts = sorted({row["channels"] for row in report_rows})

    print("\nAudio summary")
    print(f"  Sample rates (Hz): {sample_rates}")
    print(f"  Channel counts: {channel_counts}")
    print(
        "  Duration seconds "
        f"(min / median / max): "
        f"{min(durations):.2f} / {statistics.median(durations):.2f} / "
        f"{max(durations):.2f}"
    )

    print("\nTranscript summary")
    print(
        "  Character count "
        f"(min / median / max): "
        f"{min(transcript_lengths)} / {statistics.median(transcript_lengths):.0f} / "
        f"{max(transcript_lengths)}"
    )
    print(
        "  Transcripts containing '...': "
        f"{sum(row['contains_ellipsis'] for row in report_rows)}"
    )
    print(
        "  Transcripts containing 'غير واضح': "
        f"{sum(row['contains_unclear_marker'] for row in report_rows)}"
    )

    if errors:
        print("\nErrors (first 20):")
        for error in errors[:20]:
            print(f"  - {error}")


if __name__ == "__main__":
    main()