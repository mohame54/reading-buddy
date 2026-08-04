"""
Standalone Sherpa STT + word-level grading for eval scripts.

No dependency on the repo `src/` package — upload only the `eval/` folder to Colab.
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import sherpa_onnx
import soundfile as sf
import soxr

STT_FRAME_DURATION = float(os.getenv("STT_FRAME_DURATION", "0.08"))


@dataclass
class WordSegment:
    word: str
    start: float
    end: float


@dataclass
class RecognitionResult:
    text: str
    timestamps: List[float]
    tokens: List[str]

    def merge_subwords(self, frame_dur: Optional[float] = None) -> List[WordSegment]:
        return merge_sherpa_subwords(
            self.tokens,
            self.timestamps,
            frame_dur or STT_FRAME_DURATION,
        )


def merge_sherpa_subwords(
    tokens: List[str],
    timestamps: List[float],
    frame_duration: float = STT_FRAME_DURATION,
) -> List[WordSegment]:
    words: List[WordSegment] = []
    current_tokens: List[str] = []
    start_time: float | None = None
    last_ts = 0.0

    for token, ts in zip(tokens, timestamps):
        token_clean = token.strip(".")
        if not token_clean:
            continue

        if token_clean.startswith(" "):
            if current_tokens:
                full_word = "".join(current_tokens)
                words.append(
                    WordSegment(
                        word=full_word,
                        start=start_time or 0.0,
                        end=last_ts + frame_duration,
                    )
                )
                current_tokens = []

            start_time = ts
            current_tokens.append(token_clean.replace(" ", ""))
        else:
            current_tokens.append(token_clean)

        last_ts = ts

    if current_tokens:
        full_word = "".join(current_tokens)
        words.append(
            WordSegment(
                word=full_word,
                start=start_time or 0.0,
                end=last_ts + frame_duration,
            )
        )

    return words


def normalize_word(word: str) -> str:
    word = unicodedata.normalize("NFKC", word)
    word = re.sub(r"[\u064B-\u065F\u0640\u0670\u06D6-\u06ED]", "", word)
    word = "".join(
        c
        for c in word
        if unicodedata.category(c).startswith(("L", "N"))
        and unicodedata.category(c) != "Lm"
    )
    return word.strip().lower()


def tokenize_text(text: str) -> List[str]:
    return [w for w in re.split(r"\s+", (text or "").strip()) if w]


def compare_utterance(
    expected_words: List[str],
    heard_words: List[str],
    cursor: int,
) -> Tuple[int, List[Tuple[int, str, Optional[str]]]]:
    mismatches: List[Tuple[int, str, Optional[str]]] = []
    leading_correct = 0

    for i, heard in enumerate(heard_words):
        pos = cursor + i
        if pos >= len(expected_words):
            break
        expected = expected_words[pos]
        if normalize_word(expected) == normalize_word(heard):
            if not mismatches:
                leading_correct += 1
        else:
            mismatches.append((pos, expected, heard))

    new_cursor = cursor + leading_correct
    return new_cursor, mismatches


def resample_audio(audio: np.ndarray, orig_rate: int, tr_rate: int) -> np.ndarray:
    if orig_rate != tr_rate:
        audio = np.apply_along_axis(
            soxr.resample,
            axis=-1,
            arr=audio,
            in_rate=orig_rate,
            out_rate=tr_rate,
            quality="soxr_hq",
        )
    return audio


def load_wav(file_path: str, tr_rate: int = 16_000) -> Tuple[np.ndarray, int]:
    audio_array, orig_rate = sf.read(file_path)
    audio_array = audio_array.astype(np.float32)
    audio_array = resample_audio(audio_array, orig_rate, tr_rate)
    return audio_array, tr_rate


def load_stt_recognizer(
    model_dir: str,
    num_threads: int = 2,
    provider: str = "cpu",
    debug: bool = False,
):
    model_path = os.path.join(model_dir, "stt_ar_ctc.onnx")
    tokens_path = os.path.join(model_dir, "tokens.txt")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
    if not os.path.exists(tokens_path):
        raise FileNotFoundError(f"Tokens file not found: {tokens_path}")

    return sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
        model=model_path,
        tokens=tokens_path,
        num_threads=num_threads,
        provider=provider,
        debug=debug,
    )


def recognize_audio(
    recognizer: sherpa_onnx.OfflineRecognizer,
    audio: np.ndarray,
    sample_rate: int = 16_000,
) -> RecognitionResult:
    if audio.ndim > 1:
        audio = audio[:, 0]

    stream = recognizer.create_stream()
    stream.accept_waveform(sample_rate, audio)
    recognizer.decode_stream(stream)
    result = stream.result
    return RecognitionResult(
        text=result.text,
        timestamps=result.timestamps,
        tokens=result.tokens,
    )
