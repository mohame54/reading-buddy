import base64
import io
import json
import re
import unicodedata
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

import numpy as np
import soundfile as sf

from src.config import get_settings
from src.utils.decode import WordSegment


def normalize_word(word: str) -> str:
    word = unicodedata.normalize("NFKC", word)
    # Strip Arabic diacritics (tashkeel), tatweel, superscript alef, and tajweed marks
    word = re.sub(r"[\u064B-\u065F\u0640\u0670\u06D6-\u06ED]", "", word)
    # Keep letters/digits only. Arabic punctuation (، ؟ ؛ ۔) lives in U+0600–U+06FF
    # so a script-range keep-filter would incorrectly retain it.
    word = "".join(
        c
        for c in word
        if unicodedata.category(c).startswith(("L", "N"))
        and unicodedata.category(c) != "Lm"
    )
    return word.strip().lower()


def tokenize_text(text: str) -> List[str]:
    return [w for w in re.split(r"\s+", (text or "").strip()) if w]


def page_has_text(text: str | None) -> bool:
    return bool(tokenize_text(text or ""))


def parse_content_aligned(content_aligned: str | None) -> List[WordSegment]:
    if not content_aligned:
        return []
    data = json.loads(content_aligned)
    return [WordSegment(**item) for item in data]


def serialize_content_aligned(segments: List[WordSegment]) -> str:
    return json.dumps([seg.model_dump() for seg in segments])


def fuzzy_match_segment_index(
    expected_word: str,
    segments: List[WordSegment],
    hint_index: int,
) -> int:
    if not segments:
        return -1
    if 0 <= hint_index < len(segments):
        if normalize_word(segments[hint_index].word) == normalize_word(expected_word):
            return hint_index

    best_idx = -1
    best_score = 0.0
    target = normalize_word(expected_word)
    for idx, seg in enumerate(segments):
        score = SequenceMatcher(None, target, normalize_word(seg.word)).ratio()
        if score > best_score:
            best_score = score
            best_idx = idx
    return best_idx if best_score >= get_settings().stt_fuzzy_match_threshold else -1


def compare_utterance(
    expected_words: List[str],
    heard_words: List[str],
    cursor: int,
) -> Tuple[int, List[Tuple[int, str, Optional[str]]]]:
    """
    Compare heard words against expected words starting at cursor.

    Aligns heard[i] with expected[cursor + i]. Collects every mismatch in the
    utterance. The returned cursor advances only through consecutive correct
    words before the first mismatch (gate stays on the first unresolved word).
  """
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


def decode_audio_base64(audio_b64: str) -> Tuple[np.ndarray, int]:
    raw = base64.b64decode(audio_b64)
    audio, sample_rate = sf.read(io.BytesIO(raw))
    if audio.ndim > 1:
        audio = audio[:, 0]
    return audio.astype(np.float32), int(sample_rate)
