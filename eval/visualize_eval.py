#!/usr/bin/env python3
"""
Visualize Sherpa eval results against teacher ground truth.

All continuous comparisons use a common 0–100% scale:
  teacher_pct = teacher_score * 10   (teacher 0–10 → 0–100%)
  model_pct   = model_accuracy * 100 (0–1 fraction → 0–100%)

Usage:
  python eval/visualize_eval.py
  python eval/visualize_eval.py --input eval/sherpa_eval_results.csv --output-dir eval/plots
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
DEFAULT_INPUT = EVAL_DIR / "sherpa_eval_results.csv"
DEFAULT_OUTPUT_DIR = EVAL_DIR / "plots"
WHISPER_TINY_COL = "do-whisper-tiny - Score (0-100)"
PCT_SCALE = 100.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize Sherpa eval vs teacher scores")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Evaluation results CSV",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for plot files",
    )
    parser.add_argument(
        "--pass-threshold",
        type=float,
        default=6.0,
        help="Pass threshold on teacher 0–10 scale (7 → 70%%)",
    )
    return parser.parse_args()


def add_percentage_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize teacher (0–10) and model accuracy (0–1) to a common 0–100% scale."""
    out = df.copy()
    out["teacher_score"] = pd.to_numeric(out["teacher_score"], errors="coerce")
    out["model_accuracy"] = pd.to_numeric(out.get("model_accuracy"), errors="coerce")
    out["model_score_0_10"] = pd.to_numeric(out.get("model_score_0_10"), errors="coerce")

    if "teacher_pct" in out.columns:
        out["teacher_pct"] = pd.to_numeric(out["teacher_pct"], errors="coerce")
    else:
        out["teacher_pct"] = None

    out["teacher_pct"] = out["teacher_pct"].fillna(out["teacher_score"] * 10.0)

    if "model_pct" in out.columns:
        out["model_pct"] = pd.to_numeric(out["model_pct"], errors="coerce")
    else:
        out["model_pct"] = None

    out["model_pct"] = out["model_pct"].fillna(out["model_accuracy"] * PCT_SCALE)
    out["model_pct"] = out["model_pct"].fillna(out["model_score_0_10"] * 10.0)

    out["error_pct"] = out["model_pct"] - out["teacher_pct"]
    out["abs_error_pct"] = out["error_pct"].abs()
    return out


def load_ok_rows(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    ok = df[df["status"] == "ok"].copy()
    ok = add_percentage_columns(ok)
    ok = ok.dropna(subset=["teacher_pct", "model_pct"])
    return ok


def compute_metrics(df: pd.DataFrame, pass_threshold_pct: float) -> dict[str, float]:
    teacher = df["teacher_pct"].values
    model = df["model_pct"].values
    diff = model - teacher

    pearson, _ = pearsonr(teacher, model)
    spearman, _ = spearmanr(teacher, model)
    mae_pct = float(np.mean(np.abs(diff)))
    rmse_pct = float(np.sqrt(np.mean(diff ** 2)))

    teacher_pass = teacher >= pass_threshold_pct
    model_ok = model >= pass_threshold_pct
    tp = int(np.sum(teacher_pass & model_ok))
    fp = int(np.sum(~teacher_pass & model_ok))
    fn = int(np.sum(teacher_pass & ~model_ok))
    tn = int(np.sum(~teacher_pass & ~model_ok))

    binary_acc = (tp + tn) / len(df) if len(df) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return {
        "n": len(df),
        "mae_pct": mae_pct,
        "rmse_pct": rmse_pct,
        "pearson": float(pearson),
        "spearman": float(spearman),
        "binary_accuracy": binary_acc,
        "fpr": fpr,
        "fnr": fnr,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def plot_scatter(df: pd.DataFrame, metrics: dict[str, float], out_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(df["teacher_pct"], df["model_pct"], alpha=0.45, s=28, edgecolors="none")
    lims = [0, PCT_SCALE]
    ax.plot(lims, lims, "k--", linewidth=1, label="y = x")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("Teacher score (%)")
    ax.set_ylabel("Sherpa model accuracy (%)")
    ax.set_title("Teacher vs Sherpa (0–100% scale)")
    ax.legend(loc="upper left")
    ax.text(
        0.05,
        0.95,
        f"N={metrics['n']}\nPearson={metrics['pearson']:.3f}\nSpearman={metrics['spearman']:.3f}",
        transform=ax.transAxes,
        va="top",
        fontsize=10,
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8},
    )
    fig.tight_layout()
    fig.savefig(out_dir / "scatter_teacher_vs_model.png", dpi=150)
    plt.close(fig)


def plot_bland_altman(df: pd.DataFrame, metrics: dict[str, float], out_dir: Path) -> None:
    teacher = df["teacher_pct"].values
    model = df["model_pct"].values
    mean_scores = (teacher + model) / 2
    diff = model - teacher
    mean_diff = float(np.mean(diff))
    std_diff = float(np.std(diff))
    loa_upper = mean_diff + 1.96 * std_diff
    loa_lower = mean_diff - 1.96 * std_diff

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(mean_scores, diff, alpha=0.45, s=28, edgecolors="none")
    ax.axhline(mean_diff, color="C1", linestyle="-", label=f"Mean diff = {mean_diff:.1f} pp")
    ax.axhline(loa_upper, color="C3", linestyle="--", label=f"+1.96 SD = {loa_upper:.1f} pp")
    ax.axhline(loa_lower, color="C3", linestyle="--", label=f"-1.96 SD = {loa_lower:.1f} pp")
    ax.set_xlabel("Mean of teacher and model (%)")
    ax.set_ylabel("Model − teacher (percentage points)")
    ax.set_title("Bland–Altman plot (0–100% scale)")
    ax.legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_dir / "bland_altman.png", dpi=150)
    plt.close(fig)


def plot_error_histogram(df: pd.DataFrame, metrics: dict[str, float], out_dir: Path) -> None:
    diff = df["error_pct"]
    # Wider bins on percentage-point scale so differences are visible
    bin_width = 5.0
    bins = np.arange(-PCT_SCALE, PCT_SCALE + bin_width, bin_width)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.hist(diff, bins=bins, edgecolor="white", alpha=0.85)
    ax.axvline(0, color="k", linestyle="--", linewidth=1)
    ax.set_xlabel("Model − teacher (percentage points)")
    ax.set_ylabel("Count")
    ax.set_title(
        f"Score error distribution "
        f"(MAE={metrics['mae_pct']:.1f} pp, RMSE={metrics['rmse_pct']:.1f} pp)"
    )
    fig.tight_layout()
    fig.savefig(out_dir / "error_histogram.png", dpi=150)
    plt.close(fig)


def teacher_score_bin(score_pct: float) -> str:
    """Bin teacher percentage into readable groups."""
    score_0_10 = score_pct / 10.0
    if score_0_10 <= 2:
        return "0–20%"
    if score_0_10 <= 5:
        return "30–50%"
    if score_0_10 <= 7:
        return "60–70%"
    return "80–100%"


def plot_accuracy_by_teacher_bin(df: pd.DataFrame, out_dir: Path) -> None:
    plot_df = df.copy()
    plot_df["teacher_bin"] = plot_df["teacher_pct"].apply(teacher_score_bin)
    bins = ["0–20%", "30–50%", "60–70%", "80–100%"]
    data = [plot_df.loc[plot_df["teacher_bin"] == b, "model_pct"].values for b in bins]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.boxplot(data, tick_labels=bins)
    ax.set_ylim(0, PCT_SCALE)
    ax.set_xlabel("Teacher score bin (%)")
    ax.set_ylabel("Sherpa model accuracy (%)")
    ax.set_title("Model accuracy by teacher score bin")
    fig.tight_layout()
    fig.savefig(out_dir / "accuracy_by_teacher_bin.png", dpi=150)
    plt.close(fig)


def plot_confusion_matrix(
    metrics: dict[str, float],
    pass_threshold_pct: float,
    out_dir: Path,
) -> None:
    cm = np.array([[metrics["tn"], metrics["fp"]], [metrics["fn"], metrics["tp"]]])
    fig, ax = plt.subplots(figsize=(5, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Model fail", "Model pass"])
    ax.set_yticklabels(["Teacher fail", "Teacher pass"])
    ax.set_xlabel(f"Model (≥ {pass_threshold_pct:.0f}%)")
    ax.set_ylabel(f"Teacher (≥ {pass_threshold_pct:.0f}%)")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", color="black", fontsize=14)
    ax.set_title(
        f"Pass/fail confusion\nAcc={metrics['binary_accuracy']:.3f} "
        f"FPR={metrics['fpr']:.3f} FNR={metrics['fnr']:.3f} F1={metrics['f1']:.3f}"
    )
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(out_dir / "confusion_matrix.png", dpi=150)
    plt.close(fig)


def plot_baseline_comparison(df: pd.DataFrame, metrics: dict[str, float], out_dir: Path) -> None:
    if WHISPER_TINY_COL not in df.columns:
        return

    whisper_pct = pd.to_numeric(df[WHISPER_TINY_COL], errors="coerce")
    valid = whisper_pct.notna()
    if valid.sum() < 5:
        return

    whisper_mae = float(
        np.mean(np.abs(whisper_pct[valid] - df.loc[valid, "teacher_pct"]))
    )
    sherpa_mae = metrics["mae_pct"]

    fig, ax = plt.subplots(figsize=(6, 4))
    labels = ["Sherpa", "Whisper tiny"]
    maes = [sherpa_mae, whisper_mae]
    bars = ax.bar(labels, maes, color=["#2a6f97", "#e76f51"])
    ax.set_ylabel("MAE vs teacher (percentage points)")
    ax.set_title("MAE comparison (0–100% scale)")
    for bar, val in zip(bars, maes):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{val:.1f} pp",
            ha="center",
            va="bottom",
        )
    fig.tight_layout()
    fig.savefig(out_dir / "baseline_mae_comparison.png", dpi=150)
    plt.close(fig)


def print_summary(metrics: dict[str, float], pass_threshold_pct: float) -> None:
    print("\n=== Sherpa eval summary (0–100% scale) ===")
    print(f"Rows (ok):        {metrics['n']}")
    print(f"MAE:              {metrics['mae_pct']:.1f} percentage points")
    print(f"RMSE:             {metrics['rmse_pct']:.1f} percentage points")
    print(f"Pearson r:        {metrics['pearson']:.3f}")
    print(f"Spearman rho:     {metrics['spearman']:.3f}")
    print(
        f"Binary accuracy:  {metrics['binary_accuracy']:.3f} "
        f"(pass threshold ≥ {pass_threshold_pct:.0f}%)"
    )
    print(f"FPR:              {metrics['fpr']:.3f}")
    print(f"FNR:              {metrics['fnr']:.3f}")
    print(f"F1:               {metrics['f1']:.3f}")
    print(f"Confusion matrix: TP={metrics['tp']} FP={metrics['fp']} FN={metrics['fn']} TN={metrics['tn']}")


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise FileNotFoundError(f"Results CSV not found: {args.input}")

    df = load_ok_rows(args.input)
    if df.empty:
        raise ValueError("No successful rows with valid teacher and model scores.")

    pass_threshold_pct = args.pass_threshold * 10.0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics = compute_metrics(df, pass_threshold_pct)

    plot_scatter(df, metrics, args.output_dir)
    plot_bland_altman(df, metrics, args.output_dir)
    plot_error_histogram(df, metrics, args.output_dir)
    plot_accuracy_by_teacher_bin(df, args.output_dir)
    plot_confusion_matrix(metrics, pass_threshold_pct, args.output_dir)
    plot_baseline_comparison(df, metrics, args.output_dir)

    print_summary(metrics, pass_threshold_pct)
    print(f"\nPlots saved to {args.output_dir}")


if __name__ == "__main__":
    main()
