#!/usr/bin/env python3
"""
Evaluate Sherpa ONNX STT against teacher-scored ground truth CSV.

Usage:
  python eval/evaluate_sherpa.py --input "Audio tracks - Teacher Scored - Eval Audio Collection Submissions.csv"
  python eval/evaluate_sherpa.py --limit 10  # smoke test
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

import pandas as pd
import requests
from tqdm import tqdm

from sherpa_core import (
    compare_utterance,
    load_stt_recognizer,
    load_wav,
    recognize_audio,
    tokenize_text,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = EVAL_DIR.parent

DEFAULT_INPUT = REPO_ROOT / (
    "Audio tracks - Teacher Scored - Eval Audio Collection Submissions.csv"
)
DEFAULT_OUTPUT = EVAL_DIR / "sherpa_eval_results.csv"
DEFAULT_MODEL_DIR = REPO_ROOT / "models"
DEFAULT_AUDIO_DIR = EVAL_DIR / "audio_cache"
CHECKPOINT_INTERVAL = 25
PASS_THRESHOLD = 7.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sherpa ONNX eval vs teacher scores")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Teacher-scored CSV path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output evaluation CSV path",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=DEFAULT_MODEL_DIR,
        help="Directory containing stt_ar_ctc.onnx and tokens.txt",
    )
    parser.add_argument(
        "--audio-dir",
        type=Path,
        default=DEFAULT_AUDIO_DIR,
        help="Directory to cache downloaded audio files",
    )
    parser.add_argument(
        "--pass-threshold",
        type=float,
        default=PASS_THRESHOLD,
        help="Pass threshold for teacher_pass and model_ok (0-10 scale)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only N rows (smoke test)",
    )
    parser.add_argument(
        "--num-threads",
        type=int,
        default=int(os.getenv("STT_NUM_THREADS", "2")),
        help="Sherpa ONNX thread count",
    )
    return parser.parse_args()


def download_model(model_dir: Path) -> None:
    model_path = model_dir / "stt_ar_ctc.onnx"
    if model_path.exists():
        logger.info("Model already present at %s", model_dir)
        return

    folder_id = os.getenv("FOLDER_DRIVE_ID")
    if not folder_id:
        raise ValueError(
            "Model not found and FOLDER_DRIVE_ID is not set. "
            "Set FOLDER_DRIVE_ID to download from Google Drive via gdown."
        )

    import gdown

    model_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading model from Drive folder %s ...", folder_id)
    gdown.download_folder(id=folder_id, output=str(model_dir))


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def parse_teacher_score(raw: Any) -> float | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def audio_cache_path(audio_dir: Path, url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return audio_dir / f"{digest}.wav"


def download_audio(url: str, dest: Path, timeout: float = 60.0) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    dest.write_bytes(response.content)


def score_utterance(
    exact_phrase: str,
    heard_words: list[str],
    pass_threshold: float,
) -> dict[str, Any]:
    expected = tokenize_text(exact_phrase)
    words_total = len(expected)
    if words_total == 0:
        return {
            "words_total": 0,
            "words_correct": 0,
            "words_mismatch": 0,
            "model_accuracy": 0.0,
            "model_accuracy_pct": 0.0,
            "model_score_0_10": 0.0,
            "model_pct": 0.0,
            "model_ok": False,
        }

    new_cursor, mismatches = compare_utterance(expected, heard_words, cursor=0)
    words_correct = new_cursor
    words_mismatch = len(mismatches)
    model_accuracy = words_correct / words_total
    model_score = model_accuracy * 10.0
    model_pct = model_accuracy * 100.0

    return {
        "words_total": words_total,
        "words_correct": words_correct,
        "words_mismatch": words_mismatch,
        "model_accuracy": round(model_accuracy, 4),
        "model_accuracy_pct": round(model_pct, 2),
        "model_score_0_10": round(model_score, 4),
        "model_pct": round(model_pct, 2),
        "model_ok": model_score >= pass_threshold,
    }


def process_row(
    row: pd.Series,
    recognizer: Any,
    audio_dir: Path,
    pass_threshold: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {col: row[col] for col in row.index}
    result["status"] = "error"
    result["error"] = ""

    audio_url = str(row.get("Audio Track", "")).strip()
    exact_phrase = str(row.get("Exact Phrase", "")).strip()
    teacher_score = parse_teacher_score(row.get("Teacher score"))

    result["teacher_score"] = teacher_score
    result["teacher_pct"] = (
        round(teacher_score * 10.0, 2) if teacher_score is not None else None
    )
    result["teacher_pass"] = (
        teacher_score is not None and teacher_score >= pass_threshold
    )

    if not audio_url or not exact_phrase:
        result["error"] = "missing Audio Track or Exact Phrase"
        return result

    local_path = audio_cache_path(audio_dir, audio_url)
    result["local_audio_path"] = str(local_path)

    try:
        download_audio(audio_url, local_path)
        audio, sample_rate = load_wav(str(local_path))
        recognition = recognize_audio(recognizer, audio, sample_rate)
        segments = recognition.merge_subwords()
        heard_words = [seg.word for seg in segments]

        result["sherpa_transcript"] = recognition.text
        result["sherpa_heard_words"] = " ".join(heard_words)

        scores = score_utterance(exact_phrase, heard_words, pass_threshold)
        result.update(scores)

        if teacher_score is not None:
            result["error_pct"] = round(
                scores["model_pct"] - teacher_score * 10.0, 2
            )
            result["abs_error_pct"] = abs(result["error_pct"])
            result["abs_error"] = abs(scores["model_score_0_10"] - teacher_score)
        else:
            result["error_pct"] = None
            result["abs_error_pct"] = None
            result["abs_error"] = None

        result["status"] = "ok"
        result["error"] = ""
    except Exception as exc:
        result["error"] = str(exc)
        result["sherpa_transcript"] = ""
        result["sherpa_heard_words"] = ""
        result["words_total"] = None
        result["words_correct"] = None
        result["words_mismatch"] = None
        result["model_accuracy"] = None
        result["model_accuracy_pct"] = None
        result["model_score_0_10"] = None
        result["model_pct"] = None
        result["model_ok"] = None
        result["error_pct"] = None
        result["abs_error_pct"] = None
        result["abs_error"] = None

    return result


def main() -> None:
    args = parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input CSV not found: {args.input}")

    download_model(args.model_dir)
    recognizer = load_stt_recognizer(
        str(args.model_dir),
        num_threads=args.num_threads,
    )

    df = normalize_columns(pd.read_csv(args.input))
    required = {"Audio Track", "Exact Phrase"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {sorted(missing)}")

    df = df[df["Audio Track"].notna() & df["Exact Phrase"].notna()].copy()
    if args.limit is not None:
        df = df.head(args.limit)

    logger.info("Processing %d rows", len(df))

    results: list[dict[str, Any]] = []
    args.output.parent.mkdir(parents=True, exist_ok=True)

    for idx, (_, row) in enumerate(
        tqdm(df.iterrows(), total=len(df), desc="Evaluating"),
        start=1,
    ):
        results.append(process_row(row, recognizer, args.audio_dir, args.pass_threshold))
        if idx % CHECKPOINT_INTERVAL == 0:
            pd.DataFrame(results).to_csv(args.output, index=False)
            logger.info("Checkpoint saved at row %d", idx)

    out_df = pd.DataFrame(results)
    out_df.to_csv(args.output, index=False)

    ok_count = (out_df["status"] == "ok").sum()
    logger.info("Done. %d/%d rows ok. Output: %s", ok_count, len(out_df), args.output)


if __name__ == "__main__":
    main()
