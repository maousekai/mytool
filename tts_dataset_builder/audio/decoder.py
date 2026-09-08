"""
Audio decoder for Vietnamese TTS Dataset Builder.
Decodes source audio (MP3, WAV, M4A, FLAC) once into raw 16-bit mono PCM.
Subsequent sentence cutting operates directly on this PCM stream or file.
"""

import os
import time
from typing import Dict, Any
from ..utils.ffmpeg import run_ffmpeg, probe_audio
from ..utils.logger import get_logger

logger = get_logger()


def decode_source_to_pcm(
    source_path: str,
    output_pcm_path: str,
    sample_rate: int = 24000,
) -> Dict[str, Any]:
    """
    Decodes an audio file to raw uncompressed 16-bit signed PCM (mono, s16le).
    Does this ONCE for the entire source file.
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source audio not found: {source_path}")

    os.makedirs(os.path.dirname(os.path.abspath(output_pcm_path)), exist_ok=True)

    # Probe original file
    orig_info = probe_audio(source_path)
    logger.info(
        f"Decoding source audio: '{os.path.basename(source_path)}' "
        f"({orig_info['duration']:.1f}s, {orig_info['channels']}ch, {orig_info['sample_rate']}Hz) "
        f"-> PCM s16le mono @ {sample_rate}Hz"
    )

    t0 = time.time()
    # FFmpeg command:
    # -y: overwrite
    # -i <source>
    # -vn: disable video/cover art
    # -ac 1: downmix to mono
    # -ar <sample_rate>: resample to target
    # -f s16le: raw PCM format
    # -acodec pcm_s16le: 16-bit signed little endian
    args = [
        "-y",
        "-i", source_path,
        "-vn",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        output_pcm_path,
    ]

    ret, stdout, stderr = run_ffmpeg(args)
    if ret != 0 or not os.path.exists(output_pcm_path):
        raise RuntimeError(f"Failed to decode audio to PCM: {stderr}")

    pcm_size = os.path.getsize(output_pcm_path)
    # Each sample is 2 bytes (s16le, 1 channel)
    total_samples = pcm_size // 2
    total_duration = total_samples / sample_rate
    elapsed = time.time() - t0

    logger.info(
        f"PCM decoded successfully in {elapsed:.2f}s: "
        f"{pcm_size / (1024 * 1024):.1f} MB, {total_duration:.2f}s audio."
    )

    return {
        "pcm_path": output_pcm_path,
        "sample_rate": sample_rate,
        "channels": 1,
        "bytes_per_sample": 2,
        "total_samples": total_samples,
        "total_duration": total_duration,
        "size_bytes": pcm_size,
    }
