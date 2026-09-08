"""
Audio cutter for Vietnamese TTS Dataset Builder.
Directly extracts audio slices from the pre-decoded PCM file and writes
standard canonical mono 16-bit PCM WAV files.
"""

import os
import wave
from typing import Optional, Tuple
import numpy as np
from .vad import refine_boundary_with_silence


def calculate_slice_bounds(
    start_sec: float,
    end_sec: float,
    padding_before: float = 0.15,
    padding_after: float = 0.20,
    prev_end_sec: Optional[float] = None,
    next_start_sec: Optional[float] = None,
    total_audio_duration: float = 999999.0,
) -> Tuple[float, float]:
    """
    Computes padded cut boundaries with overlap prevention against adjacent sentences:
    - Pads before by padding_before seconds, clamped by prev_end_sec midpoint.
    - Pads after by padding_after seconds, clamped by next_start_sec midpoint.
    """
    # Raw padded start and end
    actual_start = max(0.0, start_sec - padding_before)
    actual_end = min(total_audio_duration, end_sec + padding_after)

    # Overlap prevention with previous segment:
    # If padding would cross previous segment's end, clamp to midway between them or prev_end
    if prev_end_sec is not None and prev_end_sec > 0:
        if actual_start < prev_end_sec:
            # Halfway between prev_end and start
            midpoint = (prev_end_sec + start_sec) / 2.0
            actual_start = max(actual_start, midpoint)

    # Overlap prevention with next segment:
    if next_start_sec is not None and next_start_sec > end_sec:
        if actual_end > next_start_sec:
            midpoint = (end_sec + next_start_sec) / 2.0
            actual_end = min(actual_end, midpoint)

    # Safety: ensure start < end
    if actual_start >= actual_end:
        actual_start = start_sec
        actual_end = max(start_sec + 0.1, end_sec)

    return round(actual_start, 3), round(actual_end, 3)


def cut_pcm_slice(
    pcm_file_path: str,
    output_wav_path: str,
    start_sec: float,
    end_sec: float,
    sample_rate: int = 24000,
) -> int:
    """
    Reads byte slice from PCM file and writes mono 16-bit PCM WAV.
    Returns number of samples written.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)

    bytes_per_sample = 2  # s16le mono
    start_byte = max(0, int(start_sec * sample_rate) * bytes_per_sample)
    end_byte = max(start_byte, int(end_sec * sample_rate) * bytes_per_sample)
    length_bytes = end_byte - start_byte

    with open(pcm_file_path, "rb") as pcm_f:
        pcm_f.seek(start_byte)
        raw_pcm = pcm_f.read(length_bytes)

    # Write WAV file using Python standard library wave module
    with wave.open(output_wav_path, "wb") as wav_out:
        wav_out.setnchannels(1)  # Mono
        wav_out.setsampwidth(2)  # 16-bit
        wav_out.setframerate(sample_rate)
        wav_out.writeframes(raw_pcm)

    return len(raw_pcm) // bytes_per_sample
