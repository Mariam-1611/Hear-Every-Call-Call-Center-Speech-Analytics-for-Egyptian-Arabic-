# Data Phase: MGB-3 Setup

This phase contains reusable data-preparation scripts, documentation, and the Conda environment file. The folder skeleton is tracked in Git using `.gitkeep` placeholders. Dataset files and generated CSV reports remain local and are ignored by Git.

## Project structure

```text
Data_phase/
├── configs/                 # Dataset and pipeline configuration
├── data/
│   ├── manifests/           # Dataset manifests and indexes
│   ├── raw/                 # Original downloaded datasets (local only)
│   ├── interim/             # Extracted/validated working data (local only)
│   └── processed/           # Final model-ready data (local only)
├── docs/                    # Data notes and decisions
├── notebooks/               # Exploration notebooks
├── reports/                 # Generated reports (local CSVs ignored)
├── scripts/                 # Command-line preparation scripts
└── src/
    ├── adapters/            # Dataset-specific loading/adaptation code
    └── common/              # Shared utilities
```

The `.gitkeep` files preserve empty folders when teammates clone the repository. Running the data scripts does **not** create this entire skeleton; it creates or fills only the data/output folders it needs.

## 1. Get the project

For a first-time setup, you must have access to the private GitHub repository, then run these commands in PowerShell:

```powershell
git clone https://github.com/Mariam-1611/Hear-Every-Call-Call-Center-Speech-Analytics-for-Egyptian-Arabic-.git
Set-Location "Hear-Every-Call-Call-Center-Speech-Analytics-for-Egyptian-Arabic-"
```

If you already cloned the repository, update your copy from its root:

```powershell
git pull origin main
```

## 2. Create and activate the Conda environment

Run these commands from the project root, the folder containing `Data_phase`:

```powershell
conda env create --file Data_phase\environment.yml
conda activate egyptian_asr_data
```

The environment file uses the portable Conda environment name `egyptian_asr_data`; it does not depend on a specific drive or computer. If the environment already exists and the YAML file has changed, update it with:

```powershell
conda env update --file Data_phase\environment.yml
```

Check that the main libraries import correctly:

```powershell
python -c "import datasets, huggingface_hub, pyarrow, numpy, pandas, scipy, matplotlib, librosa, soundfile, sklearn, jiwer; print('Data phase environment ready')"
```

In VS Code, select the `egyptian_asr_data` Python interpreter using **Python: Select Interpreter**.

### Windows Device Guard fallback

If Conda blocks an executable while creating the complete environment, create the Python environment first and install the packages in two batches:

```powershell
conda create --name egyptian_asr_data python=3.11 --yes
conda install --name egyptian_asr_data --override-channels --channel conda-forge datasets huggingface_hub pyarrow numpy pandas scipy matplotlib jupyterlab ipykernel jiwer --yes
conda install --name egyptian_asr_data --override-channels --channel conda-forge librosa pysoundfile scikit-learn --yes
conda activate egyptian_asr_data
```

## 3. Download MGB-3 data locally

The dataset is not included in Git. Download it from Hugging Face into the ignored raw-data folder. Run this from the project root:

```powershell
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='MightyStudent/Egyptian-ASR-MGB-3', repo_type='dataset', local_dir='Data_phase/data/raw/MGB-3')"
```

The download is about 921 MB. You only need to download it once per computer. Do not add the raw data, extracted WAVs, manifest, or generated CSV reports to Git.

## 4. Run the preparation scripts

Run all commands from the project root (the parent folder of `Data_phase`). Run them in this order:

```powershell
python Data_phase\scripts\inspect_dataset.py --data-dir "Data_phase\data\raw\MGB-3" --text-column sentence
python Data_phase\scripts\inspect_audio_storage.py
python Data_phase\scripts\extract_mgb3.py
python Data_phase\scripts\validate_mgb3.py
python Data_phase\scripts\profile_mgb3.py
python Data_phase\scripts\review_mgb3.py
```

The scripts extract embedded WAV audio and pair it with the original sentence in a local manifest. Validation and profiling only inspect the extracted files; they do not alter the audio or transcript. The review script creates reports for manual review; it does not decide which records to remove or how to normalize transcripts.

## Local data and generated files

- Raw downloads: `Data_phase/data/raw/`
- Extracted/interim audio and manifest: `Data_phase/data/interim/`
- Processed outputs: `Data_phase/data/processed/`
- Generated CSV reports: `Data_phase/reports/`

The `.gitkeep` placeholders in data folders are tracked, but their dataset contents are ignored. Keep the original data and transcripts unchanged; document any later preprocessing decisions before creating a normalized dataset.

## 5. Normalize transcripts and generate model-ready splits

After reviewing the reports, run the normalization and dataset splitting pipeline:

```powershell
# 1. Verify normalization rules against test samples
python Data_phase\scripts\test_normalizer.py

# 2. Apply record-specific review decisions and create transcript variants
python Data_phase\scripts\process_mgb3.py

# 3. Generate source-disjoint splits (Train / Val / Test)
python Data_phase\scripts\create_splits.py
```

### Preprocessing decisions:
- **Manual marker decisions**: `configs/mgb3_manual_decisions.csv` records the reviewed outcome for each of the 10 marker candidates. Five transcripts are corrected by replacing the annotation with the words heard; five records (including the uncertain one) are excluded from the clean ASR manifest. Original transcripts remain unchanged, and exclusions are logged to `reports/mgb3_dropped_records.csv`. The processing script validates that each current marker candidate has an explicit decision; it does not drop records by substring alone.
- **Transcript variants**: The processed manifest preserves `raw_transcript` and `reviewed_transcript`. `normalized_conservative` retains ellipses; `normalized_no_ellipses` removes only `...` and `…` from the derived text while keeping `ة` and `ى`; `normalized_aggressive` combines ellipsis removal with `ة -> ه` and `ى -> ي`, so it is not a controlled comparison of ellipsis removal alone.
- **Ellipsis review**: `reports/mgb3_ellipsis_inventory.csv` contains all records with `...` or `…`. `reports/mgb3_ellipsis_review.csv` contains a deterministic, 30-record sample balanced across visible marker patterns (seed 42); review the audio and fill `audio_review_category` (`punctuation_pause`, `hesitation`, `truncated_word`, or `uncertain`) and `review_notes`. This sample is an initial audit, not a label for all 677 records. Removing ellipses from `normalized_no_ellipses` is a text-only derived view; raw text and audio are unchanged while the sample is reviewed.
- **Arabic-English code-switching**: All Latin characters (`a-z`) were preserved in lowercase to support Egyptian call center vocabulary.
- **Arabic orthographic normalization**: All variants unify Alef forms and remove diacritics/Tatweel. The conservative and no-ellipsis variants retain `ة` and `ى`; the aggressive comparison variant maps `ة -> ه` and `ى -> ي`. Do not select the aggressive forms as final until their effect is measured.
- **Source-group split**: `GroupShuffleSplit` keeps records sharing a filename-derived source ID (such as `comedy_78`) in one partition. The proportions are approximate because groups have different sizes. These IDs identify source recordings/programs; they are not verified speaker IDs, so the split must not be described as speaker-independent. Each split manifest includes a `source_group` column and is saved to `data/manifests/`.
