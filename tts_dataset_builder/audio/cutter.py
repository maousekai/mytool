"""PCM slice-bound calculation and canonical mono PCM16 WAV writing."""

import math
import os
import wave
from typing import Optional, Tuple


def calculate_slice_bounds(
    start_sec: float,
    end_sec: float,
    padding_before: float = 0.15,
    padding_after: float = 0.20,
    prev_end_sec: Optional[float] = None,
    next_start_sec: Optional[float] = None,
    total_audio_duration: float = 999999.0,
) -> Tuple[float, float]:
    if start_sec < 0 or end_sec <= start_sec:
        raise ValueError("Invalid segment bounds: require 0 <= start < end")

    actual_start = max(0.0, start_sec - max(0.0, padding_before))
    actual_end = min(total_audio_duration, end_sec + max(0.0, padding_after))

    # Only clamp padding inside a real non-negative gap. If transcript segments
    # themselves overlap, moving the cut point inside speech would clip phonemes.
    if prev_end_sec is not None and 0 <= prev_end_sec <= start_sec:
        if actual_start < prev_end_sec:
            actual_start = (prev_end_sec + start_sec) / 2.0

    if next_start_sec is not None and end_sec <= next_start_sec:
        if actual_end > next_start_sec:
            actual_end = (end_sec + next_start_sec) / 2.0

    actual_start = max(0.0, min(actual_start, total_audio_duration))
    actual_end = max(0.0, min(actual_end, total_audio_duration))
    if actual_start >= actual_end:
        actual_start = max(0.0, min(start_sec, total_audio_duration))
        actual_end = max(actual_start, min(end_sec, total_audio_duration))
    if actual_start >= actual_end:
        raise ValueError("Segment lies outside the available audio")

    return round(actual_start, 3), round(actual_end, 3)


def cut_pcm_slice(
    pcm_file_path: str,
    output_wav_path: str,
    start_sec: float,
    end_sec: float,
    sample_rate: int = 24000,
) -> int:
    if not os.path.isfile(pcm_file_path):
        raise FileNotFoundError(f"PCM source not found: {pcm_file_path}")
    if sample_rate <= 0 or start_sec < 0 or end_sec <= start_sec:
        raise ValueError("Invalid PCM cut parameters")

    bytes_per_sample = 2  # raw s16le mono
    pcm_size = os.path.getsize(pcm_file_path)
    total_samples = pcm_size // bytes_per_sample
    start_sample = max(0, int(math.floor(start_sec * sample_rate)))
    end_sample = min(total_samples, int(math.ceil(end_sec * sample_rate)))
    if start_sample >= end_sample:
        raise ValueError("Requested cut is outside PCM bounds")

    start_byte = start_sample * bytes_per_sample
    length_bytes = (end_sample - start_sample) * bytes_per_sample
    with open(pcm_file_path, "rb") as pcm_f:
        pcm_f.seek(start_byte)
        raw_pcm = pcm_f.read(length_bytes)
    if len(raw_pcm) != length_bytes:
        raise IOError(f"Short PCM read: expected {length_bytes} bytes, got {len(raw_pcm)}")

    os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)
    tmp_path = output_wav_path + ".tmp"
    try:
        with wave.open(tmp_path, "wb") as wav_out:
            wav_out.setnchannels(1)
            wav_out.setsampwidth(2)
            wav_out.setframerate(sample_rate)
            wav_out.writeframes(raw_pcm)
        os.replace(tmp_path, output_wav_path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    return end_sample - start_sample
