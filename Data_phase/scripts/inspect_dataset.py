"""Inspect Parquet files in an ASR dataset folder without decoding audio."""

import argparse
from pathlib import Path

import pyarrow.parquet as pq


def inspect_dataset(data_dir: Path, text_column: str) -> None:
    parquet_files = sorted(
        path
        for path in data_dir.rglob("*.parquet")
        if ".cache" not in path.parts
    )

    if not parquet_files:
        raise FileNotFoundError(f"No Parquet files found under: {data_dir}")

    total_rows = 0
    total_missing_text = 0
    total_text_chars = 0

    print(f"Dataset folder: {data_dir}")
    print(f"Parquet files found: {len(parquet_files)}")

    for file_path in parquet_files:
        parquet_file = pq.ParquetFile(file_path)
        schema = parquet_file.schema_arrow
        rows = parquet_file.metadata.num_rows
        total_rows += rows

        print(f"\nFile: {file_path.relative_to(data_dir)}")
        print(f"Rows: {rows}")
        print(f"Columns: {schema.names}")
        print(f"Schema:\n{schema}")

        if text_column not in schema.names:
            print(f"WARNING: text column '{text_column}' is not in this file.")
            continue

        # Read only transcript text. The audio column is left untouched.
        table = pq.read_table(file_path, columns=[text_column])
        texts = table[text_column].to_pylist()

        missing = sum(
            text is None or (isinstance(text, str) and not text.strip())
            for text in texts
        )
        char_count = sum(len(text) for text in texts if isinstance(text, str))

        total_missing_text += missing
        total_text_chars += char_count

        print(f"Missing/empty transcripts: {missing}")
        print(f"Transcript characters: {char_count}")

        examples = [text for text in texts if isinstance(text, str) and text.strip()]
        print("Transcript examples:")
        for index, text in enumerate(examples[:3], start=1):
            print(f"  {index}. {text[:250]}")

    print("\n=== Dataset totals ===")
    print(f"Rows: {total_rows}")
    print(f"Missing/empty transcripts: {total_missing_text}")
    print(f"Transcript characters: {total_text_chars}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect Parquet dataset files without decoding audio."
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        help="Folder containing Parquet files, searched recursively.",
    )
    parser.add_argument(
        "--text-column",
        required=True,
        help="Name of the transcript column, e.g. sentence.",
    )
    args = parser.parse_args()

    inspect_dataset(Path(args.data_dir), args.text_column)


if __name__ == "__main__":
    main()