# Sherpa ONNX evaluation (Colab / local)

Offline evaluation of Sherpa STT + word-level scoring against teacher-scored ground truth.

**Self-contained:** only the `eval/` folder is required (no `src/` dependency). Copy `eval/` to Colab and run.

## Prerequisites

- Python 3.10+
- Google Drive folder ID for the Sherpa model (`FOLDER_DRIVE_ID`)
- Teacher CSV with columns: `Audio Track`, `Exact Phrase`, `Teacher score`

## Colab setup (eval folder only)

Upload the `eval/` folder to `/content/eval` and your CSV to `/content/`.

```python
%cd /content/eval

%pip install -q sherpa-onnx soundfile soxr gdown pandas requests tqdm matplotlib scipy

import os
os.environ["FOLDER_DRIVE_ID"] = "10i_Ul9Fb6ZyMYRseu4LQbksiChMiYiqE"

# Smoke test (10 rows)
!python evaluate_sherpa.py \
  --input "/content/Audio tracks - Teacher Scored - Eval Audio Collection Submissions.csv" \
  --model-dir /content/models \
  --output sherpa_eval_results.csv \
  --limit 10

# Full run
!python evaluate_sherpa.py \
  --input "/content/Audio tracks - Teacher Scored - Eval Audio Collection Submissions.csv" \
  --model-dir /content/models \
  --output sherpa_eval_results.csv

# Visualize
!python visualize_eval.py --input sherpa_eval_results.csv --output-dir plots
```

## Colab setup (full repo)

```python
%cd /content/reading-buddy
%pip install -q sherpa-onnx soundfile soxr gdown pandas requests tqdm matplotlib scipy

import os
os.environ["FOLDER_DRIVE_ID"] = "your-drive-folder-id"

!python eval/evaluate_sherpa.py \
  --input "/content/Audio tracks - Teacher Scored - Eval Audio Collection Submissions.csv"
!python eval/visualize_eval.py
```

Plots are written to `eval/plots/`. Results CSV: `eval/sherpa_eval_results.csv`.

## Local usage

```bash
export FOLDER_DRIVE_ID="your-drive-folder-id"

python eval/evaluate_sherpa.py \
  --input "Audio tracks - Teacher Scored - Eval Audio Collection Submissions.csv" \
  --output eval/sherpa_eval_results.csv

python eval/visualize_eval.py \
  --input eval/sherpa_eval_results.csv \
  --output-dir eval/plots
```

### CLI options (`evaluate_sherpa.py`)

| Flag | Default | Description |
|------|---------|-------------|
| `--input` | repo-root teacher CSV | Ground-truth CSV |
| `--output` | `eval/sherpa_eval_results.csv` | Output CSV |
| `--model-dir` | `models/` | Sherpa ONNX model directory |
| `--audio-dir` | `eval/audio_cache/` | Cached WAV downloads |
| `--pass-threshold` | `7` | Pass threshold (0–10) for `teacher_pass` / `model_ok` |
| `--limit` | none | Process only N rows |
| `--num-threads` | `2` | Sherpa ONNX threads |

## Scoring metric (per row)

Each CSV row is one utterance evaluated at `cursor=0` (single pass, no retry/skip loop):

```text
expected       = tokenize_text(Exact Phrase)
heard          = Sherpa merge_subwords()
new_cursor, mismatches = compare_utterance(expected, heard, 0)

words_total    = len(expected)
words_correct  = new_cursor
model_accuracy = words_correct / words_total
model_score_0_10 = model_accuracy * 10
```

Teacher comparison (common **0–100%** scale):

- `teacher_pct = teacher_score × 10` (e.g. teacher 7 → 70%)
- `model_pct = model_accuracy × 100` (e.g. 0.9 → 90%)
- `error_pct = model_pct − teacher_pct` (percentage points)
- `abs_error_pct = |error_pct|`
- Binary pass: `teacher_pct ≥ 70` and `model_pct ≥ 70` (threshold 7 on 0–10 scale)

Legacy 0–10 columns (`model_score_0_10`, `abs_error`) are kept for reference.

This mirrors production grading logic (copied into `eval/sherpa_core.py`) but does not simulate multi-retry sessions.

## Output columns (evaluation CSV)

Original CSV columns plus:

| Column | Meaning |
|--------|---------|
| `local_audio_path` | Cached WAV path |
| `sherpa_transcript` | Full STT text |
| `sherpa_heard_words` | Space-joined heard words |
| `words_total` / `words_correct` / `words_mismatch` | Word counts |
| `model_accuracy` | `words_correct / words_total` (0–1) |
| `model_accuracy_pct` / `model_pct` | Model accuracy on 0–100% scale |
| `teacher_pct` | Teacher score on 0–100% scale |
| `error_pct` / `abs_error_pct` | Difference in percentage points |
| `model_score_0_10` | Model on 0–10 scale (legacy) |
| `teacher_score` | Parsed teacher score 0–10 |
| `teacher_pass` / `model_ok` | Binary pass at threshold |
| `abs_error` | Absolute diff on 0–10 scale |
| `status` / `error` | `ok` or failure reason |

## Visualization outputs (`eval/plots/`)

| File | Description |
|------|-------------|
| `scatter_teacher_vs_model.png` | Teacher vs model score with identity line |
| `bland_altman.png` | Bias and limits of agreement |
| `error_histogram.png` | Distribution of model − teacher |
| `accuracy_by_teacher_bin.png` | Model accuracy by teacher score bin |
| `confusion_matrix.png` | Pass/fail at threshold ≥ 7 |
| `baseline_mae_comparison.png` | MAE vs Whisper tiny (if column present) |

Printed summary includes N, MAE, RMSE, Pearson/Spearman, binary accuracy, FPR, FNR, F1.

## Artifacts (not committed)

- `eval/audio_cache/` — downloaded WAVs
- `eval/plots/` — generated plots
- `eval/sherpa_eval_results.csv` — evaluation output
