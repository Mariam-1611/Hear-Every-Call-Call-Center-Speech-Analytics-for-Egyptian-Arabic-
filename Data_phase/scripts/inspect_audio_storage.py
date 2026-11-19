"""Check how audio is stored in Parquet without decoding the recordings."""

from pathlib import Path

import pyarrow.parquet as pq


DATA_DIR = Path("Data_phase/data/raw/MGB-3")


def main():
    parquet_files = sorted(DATA_DIR.rglob("*.parquet"))

    for file_path in parquet_files:
        table = pq.read_table(file_path, columns=["audio"])
        audio_rows = table["audio"].to_pylist()

        print(f"\nFile: {file_path.name}")
        print(f"Records: {len(audio_rows)}")

        for index, audio in enumerate(audio_rows[:3], start=1):
            if audio is None:
                print(f"  Example {index}: missing audio")
            else:
                audio_bytes = audio.get("bytes")
                audio_path = audio.get("path")
                byte_count = len(audio_bytes) if audio_bytes else 0
                print(
                    f"  Example {index}: "
                    f"bytes={byte_count}, path={audio_path!r}"
                )


if __name__ == "__main__":
    main()