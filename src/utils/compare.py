import base64
import io
import json
import re
import unicodedata
from difflib import SequenceMatcher
from typing import List, Optional, Tuple

import numpy as np
import soundfile as sf

from src.utils.decode import WordSegment


def normalize_word(word: str) -> str:
    word = unicodedata.normalize("NFKC", word)
    word = re.sub(r"[^\w\u0600-\u06FF]", "", word, flags=re.UNICODE)
    return word.strip().lower()


def tokenize_text(text: str) -> List[str]:
    return [w for w in re.split(r"\s+", text.strip()) if w]


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
    return best_idx if best_score >= 0.6 else -1


def compare_utterance(
    expected_words: List[str],
    heard_words: List[str],
    cursor: int,
) -> Tuple[int, List[Tuple[int, str, Optional[str]]]]:
    """
    Compare heard words against expected words starting at cursor.
    Returns updated cursor and list of (index, expected, heard) mismatches.
    Stops at first mismatch.
    """
    mismatches: List[Tuple[int, str, Optional[str]]] = []
    heard_idx = 0
    pos = cursor

    while heard_idx < len(heard_words) and pos < len(expected_words):
        expected = expected_words[pos]
        heard = heard_words[heard_idx]
        if normalize_word(expected) == normalize_word(heard):
            pos += 1
            heard_idx += 1
            continue
        mismatches.append((pos, expected, heard))
        break

    return pos, mismatches


def decode_audio_base64(audio_b64: str) -> Tuple[np.ndarray, int]:
    raw = base64.b64decode(audio_b64)
    audio, sample_rate = sf.read(io.BytesIO(raw))
    if audio.ndim > 1:
        audio = audio[:, 0]
    return audio.astype(np.float32), int(sample_rate)
