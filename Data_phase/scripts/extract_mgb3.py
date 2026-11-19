"""Extract MGB-3 audio bytes and pair each WAV with its original sentence."""

import csv
import re
from pathlib import Path

import pyarrow.parquet as pq


RAW_DIR = Path("Data_phase/data/raw/MGB-3")
OUTPUT_DIR = Path("Data_phase/data/interim/MGB-3")
AUDIO_DIR = OUTPUT_DIR / "audio"
MANIFEST_PATH = OUTPUT_DIR / "manifest.csv"
BATCH_SIZE = 16


def safe_filename(name: str) -> str:
    """Keep only a simple filename, without directories or unsafe characters."""
    name = Path(name).name
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def main() -> None:
    parquet_files = sorted(RAW_DIR.rglob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No Parquet files found under {RAW_DIR}")

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    columns = [
        "record_id",
        "audio_path",
        "transcript",
        "source_shard",
        "source_audio_filename",
    ]

    extracted = 0

    with MANIFEST_PATH.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()

        for parquet_path in parquet_files:
            parquet_file = pq.ParquetFile(parquet_path)

            for batch in parquet_file.iter_batches(
                batch_size=BATCH_SIZE,
                columns=["audio", "sentence"],
            ):
                audio_values = batch.column("audio").to_pylist()
                sentences = batch.column("sentence").to_pylist()

                for audio, sentence in zip(audio_values, sentences):
                    if audio is None or not audio.get("bytes"):
                        raise ValueError(
                            f"Missing audio in {parquet_path.name}, "
                            f"record {extracted}"
                        )
                    if sentence is None or not sentence.strip():
                        raise ValueError(
                            f"Missing transcript in {parquet_path.name}, "
                            f"record {extracted}"
                        )

                    source_name = safe_filename(audio.get("path") or "audio.wav")
                    record_id = f"mgb3_{extracted:06d}"
                    output_name = f"{record_id}_{source_name}"
                    output_path = AUDIO_DIR / output_name

                    # Copy the stored WAV bytes as-is; no audio preprocessing here.
                    output_path.write_bytes(audio["bytes"])

                    writer.writerow(
                        {
                            "record_id": record_id,
                            "audio_path": f"audio/{output_name}",
                            "transcript": sentence,
                            "source_shard": parquet_path.name,
                            "source_audio_filename": source_name,
                        }
                    )
                    extracted += 1

            print(f"Finished: {parquet_path.name}")

    print(f"\nExtracted records: {extracted}")
    print(f"Audio folder: {AUDIO_DIR}")
    print(f"Manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()