"""
VAD / Silence Boundary Refinement for Vietnamese TTS Dataset Builder.
Searches within ±300ms of transcript start/end timestamps to find the optimal
silence/speech onset and offset boundaries without altering the transcript text.
"""

import math
import struct
from typing import Tuple, Optional
import numpy as np


def compute_frame_energies_db(
    pcm_bytes: bytes,
    sample_rate: int = 24000,
    frame_ms: float = 15.0,
    hop_ms: float = 5.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Computes RMS energy (in dBFS) for sliding short frames.
    Returns (times_array, energies_db_array).
    """
    num_samples = len(pcm_bytes) // 2
    if num_samples == 0:
        return np.array([]), np.array([])

    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    frame_len = int(sample_rate * (frame_ms / 1000.0))
    hop_len = int(sample_rate * (hop_ms / 1000.0))
    if frame_len <= 0 or hop_len <= 0 or len(samples) < frame_len:
        return np.array([0.0]), np.array([-60.0])

    num_frames = 1 + (len(samples) - frame_len) // hop_len
    energies_db = np.zeros(num_frames, dtype=np.float32)
    times = np.zeros(num_frames, dtype=np.float32)

    for i in range(num_frames):
        start_idx = i * hop_len
        frame = samples[start_idx : start_idx + frame_len]
        rms = np.sqrt(np.mean(frame**2) + 1e-12)
        energies_db[i] = 20.0 * np.log10(max(rms, 1e-5))
        times[i] = (start_idx + frame_len / 2) / sample_rate

    return times, energies_db


def refine_boundary_with_silence(
    pcm_file_handle,
    timestamp: float,
    sample_rate: int = 24000,
    search_window_sec: float = 0.30,
    is_start: bool = True,
    silence_threshold_db: float = -42.0,
    total_duration: float = 999999.0,
) -> float:
    """
    Searches ±search_window_sec (±300ms) around timestamp to find optimal cut point:
    - If is_start: finds the silence right before speech onset.
    - If not is_start: finds the silence right after speech ends.
    """
    window_start = max(0.0, timestamp - search_window_sec)
    window_end = min(total_duration, timestamp + search_window_sec)
    window_len = window_end - window_start
    if window_len <= 0.05:
        return timestamp

    start_byte = int(window_start * sample_rate) * 2
    byte_count = int(window_len * sample_rate) * 2

    pcm_file_handle.seek(start_byte)
    chunk = pcm_file_handle.read(byte_count)
    if len(chunk) < 100:
        return timestamp

    times, energies = compute_frame_energies_db(
        chunk, sample_rate=sample_rate, frame_ms=15.0, hop_ms=5.0
    )
    if len(times) == 0:
        return timestamp

    # Adjust relative times to absolute time in audio
    abs_times = times + window_start

    # Determine speech vs silence boolean mask
    is_speech = energies > silence_threshold_db

    target_time = timestamp
    if is_start:
        # For start: look near timestamp for transition from silence -> speech
        # Ideal cut point is right at onset or lowest energy dip before speech onset
        best_time = timestamp
        min_distance = search_window_sec + 0.1

        # Find points where energy rises above threshold
        for i in range(1, len(energies)):
            if not is_speech[i - 1] and is_speech[i]:
                dist = abs(abs_times[i] - timestamp)
                if dist < min_distance:
                    min_distance = dist
                    best_time = abs_times[i]

        # If no strict transition found, snap to minimum energy point in [-0.2s, 0.0s]
        if min_distance > search_window_sec:
            mask = (abs_times >= timestamp - 0.2) & (abs_times <= timestamp + 0.1)
            if np.any(mask):
                min_idx = np.argmin(energies[mask])
                best_time = abs_times[mask][min_idx]

        return round(float(best_time), 3)

    else:
        # For end: look near timestamp for transition from speech -> silence
        best_time = timestamp
        min_distance = search_window_sec + 0.1

        for i in range(len(energies) - 1):
            if is_speech[i] and not is_speech[i + 1]:
                dist = abs(abs_times[i] - timestamp)
                if dist < min_distance:
                    min_distance = dist
                    best_time = abs_times[i + 1]

        if min_distance > search_window_sec:
            mask = (abs_times >= timestamp - 0.1) & (abs_times <= timestamp + 0.2)
            if np.any(mask):
                min_idx = np.argmin(energies[mask])
                best_time = abs_times[mask][min_idx]

        return round(float(best_time), 3)
