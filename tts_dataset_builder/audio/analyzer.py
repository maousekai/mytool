"""
Audio quality analyzer and normalizer for Vietnamese TTS Dataset Builder.
Computes RMS, Peak, Silence Ratio, Clipping, and Quality Score (0-100).
Provides optional Peak and EBU R128 Loudness Normalization.
"""

import os
import math
import wave
from typing import Dict, Any, Tuple, Optional
import numpy as np
from ..utils.ffmpeg import run_ffmpeg, probe_audio


def analyze_wav_file(
    wav_path: str,
    silence_threshold_db: float = -45.0,
) -> Dict[str, Any]:
    """
    Analyzes a 16-bit PCM WAV file:
    - duration (sec)
    - sample_rate (Hz)
    - channels
    - rms (dBFS)
    - peak (dBFS)
    - silence_ratio (0.0 to 1.0)
    - clipping_count (count of samples >= 32760 or <= -32760)
    - quality_score (0 - 100)
    """
    if not os.path.exists(wav_path):
        return {
            "valid": False,
            "error": "File does not exist",
            "quality_score": 0,
        }

    try:
        with wave.open(wav_path, "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            sample_rate = wf.getframerate()
            num_frames = wf.getnframes()
            raw_data = wf.readframes(num_frames)

        if num_frames == 0 or len(raw_data) == 0:
            return {
                "valid": False,
                "error": "Empty audio data (0 frames)",
                "quality_score": 0,
            }

        # Handle 16-bit
        if sampwidth == 2:
            samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
            max_val = 32768.0
            clip_threshold = 32750
        elif sampwidth == 1:
            samples = (np.frombuffer(raw_data, dtype=np.uint8).astype(np.float32) - 128.0) * 256.0
            max_val = 32768.0
            clip_threshold = 32500
        else:
            # 24-bit or 32-bit fallback
            samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
            max_val = 32768.0
            clip_threshold = 32750

        # If multichannel, downmix for analysis
        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1)

        duration = len(samples) / float(sample_rate)

        # 1. Peak
        abs_samples = np.abs(samples)
        peak_raw = float(np.max(abs_samples)) if len(abs_samples) > 0 else 0.0
        peak_norm = peak_raw / max_val
        peak_db = 20.0 * np.log10(max(peak_norm, 1e-6))

        # 2. RMS
        rms_raw = float(np.sqrt(np.mean(samples**2) + 1e-12))
        rms_norm = rms_raw / max_val
        rms_db = 20.0 * np.log10(max(rms_norm, 1e-6))

        # 3. Clipping check
        clipping_count = int(np.sum(abs_samples >= clip_threshold))

        # 4. Silence ratio: frame-based energy
        frame_len = max(1, int(sample_rate * 0.02))  # 20ms frames
        num_f = len(samples) // frame_len
        if num_f > 0:
            f_samples = samples[: num_f * frame_len].reshape(num_f, frame_len)
            f_rms = np.sqrt(np.mean(f_samples**2, axis=1) + 1e-12) / max_val
            f_db = 20.0 * np.log10(np.maximum(f_rms, 1e-6))
            silent_frames = np.sum(f_db < silence_threshold_db)
            silence_ratio = float(silent_frames) / float(num_f)
        else:
            silence_ratio = 0.0

        # 5. Quality Score calculation (0 to 100)
        score = 100.0

        # Clipping penalty
        if clipping_count > 0:
            score -= min(40.0, clipping_count * 2.0)

        # Extreme silence ratio penalty (> 35% silence)
        if silence_ratio > 0.40:
            score -= (silence_ratio - 0.40) * 50.0

        # Too quiet penalty (RMS < -35 dBFS)
        if rms_db < -35.0:
            score -= min(30.0, abs(rms_db - (-35.0)) * 2.0)
        elif rms_db > -10.0:
            score -= 15.0  # Too loud / squashed

        # Duration penalties (ideal 3s - 10s)
        if duration < 1.5:
            score -= 25.0
        elif duration < 2.0:
            score -= 10.0
        elif duration > 12.0:
            score -= 15.0

        score = max(0.0, min(100.0, round(score, 1)))

        return {
            "valid": True,
            "duration": round(duration, 3),
            "sample_rate": sample_rate,
            "channels": channels,
            "peak_db": round(peak_db, 2),
            "rms_db": round(rms_db, 2),
            "silence_ratio": round(silence_ratio, 3),
            "clipping_count": clipping_count,
            "quality_score": score,
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "quality_score": 0,
        }


def normalize_audio_file(
    wav_path: str,
    output_path: Optional[str] = None,
    peak_norm: bool = False,
    loudness_norm: bool = False,
    target_lufs: float = -20.0,
) -> str:
    """
    Applies optional Peak or EBU R128 Loudness Normalization.
    Default: does nothing unless enabled.
    """
    if not peak_norm and not loudness_norm:
        return wav_path

    out_file = output_path or wav_path
    temp_file = out_file + ".norm.wav"

    if loudness_norm:
        # Use FFmpeg loudnorm filter
        args = [
            "-y",
            "-i", wav_path,
            "-af", f"loudnorm=I={target_lufs}:TP=-1.0:LRA=11",
            "-ac", "1",
            "-c:a", "pcm_s16le",
            temp_file,
        ]
        ret, _, err = run_ffmpeg(args)
        if ret == 0 and os.path.exists(temp_file):
            if os.path.exists(out_file):
                os.remove(out_file)
            os.rename(temp_file, out_file)
            return out_file

    elif peak_norm:
        # Scale to -1.0 dBFS (peak = 0.891)
        with wave.open(wav_path, "rb") as wf:
            params = wf.getparams()
            raw = wf.readframes(wf.getnframes())

        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        peak = np.max(np.abs(samples))
        if peak > 0:
            target_peak = 32767.0 * 0.89125  # -1 dBFS
            gain = target_peak / peak
            norm_samples = np.clip(samples * gain, -32768, 32767).astype(np.int16)
            with wave.open(out_file, "wb") as wf_out:
                wf_out.setparams(params)
                wf_out.writeframes(norm_samples.tobytes())
            return out_file

    return wav_path
