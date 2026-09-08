"""Audio quality analysis and optional normalization helpers."""

import os
import wave
from typing import Any, Dict, Optional

import numpy as np

from ..utils.ffmpeg import run_ffmpeg


def _pcm_to_float(raw: bytes, sampwidth: int) -> np.ndarray:
    """Decode little-endian PCM bytes to float32 in approximately [-1, 1]."""
    if sampwidth == 1:
        return (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    if sampwidth == 2:
        return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if sampwidth == 3:
        b = np.frombuffer(raw, dtype=np.uint8)
        usable = (len(b) // 3) * 3
        b = b[:usable].reshape(-1, 3)
        v = (b[:, 0].astype(np.int32)
             | (b[:, 1].astype(np.int32) << 8)
             | (b[:, 2].astype(np.int32) << 16))
        v = np.where(v & 0x800000, v - 0x1000000, v)
        return v.astype(np.float32) / 8388608.0
    if sampwidth == 4:
        return np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    raise ValueError(f"Unsupported PCM sample width: {sampwidth} bytes")


def analyze_wav_file(wav_path: str, silence_threshold_db: float = -45.0) -> Dict[str, Any]:
    if not os.path.isfile(wav_path):
        return {"valid": False, "error": "File does not exist", "quality_score": 0.0}

    try:
        with wave.open(wav_path, "rb") as wf:
            channels = int(wf.getnchannels())
            sampwidth = int(wf.getsampwidth())
            sample_rate = int(wf.getframerate())
            num_frames = int(wf.getnframes())
            comptype = wf.getcomptype()
            raw = wf.readframes(num_frames)

        if comptype != "NONE":
            return {"valid": False, "error": f"Compressed WAV is unsupported ({comptype})", "quality_score": 0.0}
        if num_frames <= 0 or not raw or sample_rate <= 0 or channels <= 0:
            return {"valid": False, "error": "Empty/invalid WAV header", "quality_score": 0.0}

        samples = _pcm_to_float(raw, sampwidth)
        if samples.size < channels:
            return {"valid": False, "error": "Audio payload is too short", "quality_score": 0.0}
        usable = (samples.size // channels) * channels
        samples = samples[:usable]
        if channels > 1:
            mono = samples.reshape(-1, channels).mean(axis=1)
        else:
            mono = samples

        duration = len(mono) / float(sample_rate)
        abs_samples = np.abs(mono)
        peak = float(np.max(abs_samples)) if abs_samples.size else 0.0
        rms = float(np.sqrt(np.mean(np.square(mono, dtype=np.float64)) + 1e-15))
        peak_db = 20.0 * np.log10(max(peak, 1e-7))
        rms_db = 20.0 * np.log10(max(rms, 1e-7))

        clipping_count = int(np.sum(abs_samples >= 0.9995))
        clipping_ratio = clipping_count / float(len(mono)) if len(mono) else 0.0

        frame_len = max(1, int(sample_rate * 0.02))
        frame_count = len(mono) // frame_len
        if frame_count:
            frames = mono[:frame_count * frame_len].reshape(frame_count, frame_len)
            frame_rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1) + 1e-15)
            frame_db = 20.0 * np.log10(np.maximum(frame_rms, 1e-7))
            silence_ratio = float(np.mean(frame_db < silence_threshold_db))
        else:
            silence_ratio = 0.0

        score = 100.0
        if clipping_count:
            score -= min(40.0, max(5.0, clipping_ratio * 5000.0))
        if silence_ratio > 0.40:
            score -= min(30.0, (silence_ratio - 0.40) * 60.0)
        if rms_db < -35.0:
            score -= min(30.0, (-35.0 - rms_db) * 2.0)
        elif rms_db > -10.0:
            score -= 15.0
        if duration < 1.5:
            score -= 25.0
        elif duration < 2.0:
            score -= 10.0
        elif duration > 12.0:
            score -= 15.0
        if channels != 1:
            score -= 10.0
        if sampwidth != 2:
            score -= 10.0
        score = round(max(0.0, min(100.0, score)), 1)

        return {
            "valid": True,
            "duration": round(duration, 3),
            "sample_rate": sample_rate,
            "channels": channels,
            "sample_width_bits": sampwidth * 8,
            "peak_db": round(float(peak_db), 2),
            "rms_db": round(float(rms_db), 2),
            "silence_ratio": round(silence_ratio, 3),
            "clipping_count": clipping_count,
            "clipping_ratio": round(clipping_ratio, 6),
            "quality_score": score,
        }
    except Exception as exc:
        return {"valid": False, "error": str(exc), "quality_score": 0.0}


def normalize_audio_file(
    wav_path: str,
    output_path: Optional[str] = None,
    peak_norm: bool = False,
    loudness_norm: bool = False,
    target_lufs: float = -20.0,
) -> str:
    if not peak_norm and not loudness_norm:
        return wav_path
    if peak_norm and loudness_norm:
        raise ValueError("Choose peak_norm or loudness_norm, not both")

    out_file = output_path or wav_path
    temp_file = out_file + ".norm.wav"

    if loudness_norm:
        args = [
            "-y", "-i", wav_path,
            "-af", f"loudnorm=I={float(target_lufs)}:TP=-1.0:LRA=11",
            "-ac", "1", "-c:a", "pcm_s16le", temp_file,
        ]
        ret, _, err = run_ffmpeg(args)
        if ret != 0 or not os.path.isfile(temp_file):
            raise RuntimeError(f"FFmpeg loudness normalization failed: {err}")
        os.replace(temp_file, out_file)
        return out_file

    with wave.open(wav_path, "rb") as wf:
        if wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
            raise ValueError("Peak normalization expects PCM16 WAV")
        params = wf.getparams()
        raw = wf.readframes(wf.getnframes())
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32)
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if peak <= 0:
        return wav_path
    gain = (32767.0 * 0.891250938) / peak  # -1 dBFS
    normalized = np.clip(samples * gain, -32768, 32767).astype("<i2")
    with wave.open(out_file, "wb") as wf:
        wf.setparams(params)
        wf.writeframes(normalized.tobytes())
    return out_file
