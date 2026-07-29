import soundfile as sf
import numpy as np
import soxr
from typing import Tuple, List
import sherpa_onnx
import os
from pydantic import BaseModel
from src.utils.decode import merge_sherpa_subwords, WordSegment


class RecognitionResult(BaseModel):
    text: str
    timestamps: List[float]
    tokens: List[str]

    def merge_subwords(self, frame_dur=0.8) -> List[WordSegment]:
        return merge_sherpa_subwords(self.tokens, self.timestamps, frame_dur)

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

def load_wav(file_path, tr_rate=16_000) -> Tuple[np.ndarray, int]:
    """
    Loads a WAV file and performs resampling if necessary.

    Args:
    - file_path: Path to the WAV file.
    - tr_rate: Target sampling rate, default is 16,000.

    Returns:
    - audio_array: Loaded and resampled audio as a numpy array.
    - tr_rate: Target sampling rate.
    """
    audio_array, orig_rate = sf.read(file_path)
    audio_array = audio_array.astype(np.float32)
    audio_array = resample_audio(audio_array, orig_rate, tr_rate)
    return audio_array, tr_rate


def load_stt_recognizer(model_dir: str, num_threads: int = 2, provider: str = "cpu", debug: bool = False):
    model_path = os.path.join(model_dir, "stt_ar_ctc.onnx")
    tokens_path = os.path.join(model_dir, "tokens.txt")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    if not os.path.exists(tokens_path):
        raise FileNotFoundError(f"Tokens file not found: {tokens_path}")
    
    recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
        model=model_path,   # Path to your exported NeMo CTC ONNX model
        tokens=tokens_path,       # Path to your generated tokens.txt
        num_threads=num_threads,             # CPU threads
        provider=provider,           # Use "cuda" for GPU, or "cpu"
        debug=debug
    )

    return recognizer


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
        tokens=result.tokens
    )

def recognize_audios(
    recognizer: sherpa_onnx.OfflineRecognizer,
    audio: List[np.ndarray],
    sample_rate: int = 16_000,
) -> List[RecognitionResult]:
    streams = []
    for audio_chunk in audio:
        if audio_chunk.ndim > 1:
            audio_chunk = audio_chunk[:, 0]
        stream = recognizer.create_stream()
        stream.accept_waveform(sample_rate, audio_chunk)
        streams.append(stream)
    recognizer.decode_streams(streams)
    results = []
    for stream in streams:
        result = stream.result
        results.append(RecognitionResult(
            text=result.text,
            timestamps=result.timestamps,
            tokens=result.tokens
        ))
    return results