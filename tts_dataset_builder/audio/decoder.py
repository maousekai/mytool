"""Decode source audio once into raw mono PCM16 using FFmpeg."""

import os
import time
from typing import Any, Dict

from ..utils.ffmpeg import probe_audio, run_ffmpeg
from ..utils.logger import get_logger

logger = get_logger()


def decode_source_to_pcm(source_path: str, output_pcm_path: str, sample_rate: int = 24000) -> Dict[str, Any]:
    if not os.path.isfile(source_path):
        raise FileNotFoundError(f"Source audio not found: {source_path}")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")

    os.makedirs(os.path.dirname(os.path.abspath(output_pcm_path)), exist_ok=True)
    info = probe_audio(source_path)
    if info.get("duration", 0.0) <= 0:
        raise RuntimeError("FFprobe could not find a valid audio duration")

    logger.info(
        "Decoding %s (%.1fs, %sch, %sHz) -> PCM16 mono @ %sHz",
        os.path.basename(source_path), info["duration"], info["channels"], info["sample_rate"], sample_rate,
    )

    temp_path = output_pcm_path + ".part"
    if os.path.exists(temp_path):
        try: os.remove(temp_path)
        except OSError: pass

    t0 = time.time()
    args = [
        "-y", "-i", source_path,
        "-map", "0:a:0",
        "-vn", "-sn", "-dn",
        "-ac", "1", "-ar", str(sample_rate),
        "-f", "s16le", "-acodec", "pcm_s16le", temp_path,
    ]
    try:
        ret, _, stderr = run_ffmpeg(args)
        if ret != 0 or not os.path.isfile(temp_path):
            raise RuntimeError(f"Failed to decode audio to PCM: {stderr}")
        pcm_size = os.path.getsize(temp_path)
        if pcm_size < 2:
            raise RuntimeError("Decoded PCM is empty")
        if pcm_size % 2:
            raise RuntimeError("Decoded PCM byte size is not aligned to PCM16 samples")
        os.replace(temp_path, output_pcm_path)
    finally:
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except OSError: pass

    pcm_size = os.path.getsize(output_pcm_path)
    total_samples = pcm_size // 2
    total_duration = total_samples / float(sample_rate)
    logger.info("PCM decoded in %.2fs: %.1f MB, %.2fs", time.time() - t0, pcm_size / 1048576, total_duration)
    return {
        "pcm_path": output_pcm_path,
        "sample_rate": sample_rate,
        "channels": 1,
        "bytes_per_sample": 2,
        "total_samples": total_samples,
        "total_duration": total_duration,
        "size_bytes": pcm_size,
    }
