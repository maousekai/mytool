"""FFmpeg/FFprobe wrappers with cross-platform executable discovery."""

import json
import os
import shutil
import subprocess
import time
from typing import Any, Dict, Optional, Tuple

from .logger import get_logger, log_ffmpeg_cmd

logger = get_logger()
CUSTOM_FFMPEG_BIN = os.environ.get("FFMPEG_PATH", "")
CUSTOM_FFPROBE_BIN = os.environ.get("FFPROBE_PATH", "")


def find_binary(name: str, custom_path: str = "") -> Optional[str]:
    if custom_path and os.path.isfile(custom_path):
        return custom_path
    found = shutil.which(name)
    if found:
        return found
    if os.name == "nt":
        exe = f"{name}.exe"
        candidates = [
            os.path.join(os.getcwd(), exe), os.path.join(os.getcwd(), "bin", exe),
            os.path.join(os.environ.get("USERPROFILE", ""), "ffmpeg", "bin", exe),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links", exe),
            f"C:\\ffmpeg\\bin\\{exe}", f"C:\\Program Files\\ffmpeg\\bin\\{exe}", f"C:\\tools\\ffmpeg\\bin\\{exe}",
        ]
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate
    return None


def get_ffmpeg_path() -> Optional[str]: return find_binary("ffmpeg", CUSTOM_FFMPEG_BIN)
def get_ffprobe_path() -> Optional[str]: return find_binary("ffprobe", CUSTOM_FFPROBE_BIN)


def check_ffmpeg() -> Tuple[bool, str]:
    ffmpeg_bin, ffprobe_bin = get_ffmpeg_path(), get_ffprobe_path()
    missing = [name for name, value in (("ffmpeg", ffmpeg_bin), ("ffprobe", ffprobe_bin)) if not value]
    if missing:
        return False, (
            f"Không tìm thấy {' và '.join(missing)}.\n"
            "Windows: winget install Gyan.FFmpeg\n"
            "Hoặc tải FFmpeg và thêm thư mục bin vào PATH."
        )
    try:
        result = subprocess.run([ffmpeg_bin, "-version"], capture_output=True, text=True, timeout=5, shell=False)
        if result.returncode != 0:
            return False, f"FFmpeg chạy lỗi: {result.stderr}"
        first = result.stdout.splitlines()[0] if result.stdout else "FFmpeg OK"
        return True, f"FFmpeg sẵn sàng: {first}"
    except Exception as exc:
        return False, f"Lỗi kiểm tra FFmpeg: {exc}"


def run_ffmpeg(args: list[str], timeout: Optional[int] = None) -> Tuple[int, str, str]:
    ffmpeg_bin = get_ffmpeg_path()
    if not ffmpeg_bin:
        raise FileNotFoundError("FFmpeg executable not found")
    cmd = [ffmpeg_bin, *args]
    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False)
        log_ffmpeg_cmd(cmd, proc.returncode, time.time() - started, proc.stderr)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        log_ffmpeg_cmd(cmd, -1, time.time() - started, f"Timeout after {timeout}s")
        raise


def probe_audio(file_path: str) -> Dict[str, Any]:
    ffprobe_bin = get_ffprobe_path()
    if not ffprobe_bin:
        raise FileNotFoundError("FFprobe executable not found")
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    cmd = [
        ffprobe_bin, "-v", "error",
        "-show_entries", "format=duration,size,bit_rate:stream=codec_type,codec_name,sample_rate,channels,duration",
        "-of", "json", file_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, shell=False)
    if proc.returncode != 0:
        raise RuntimeError(f"FFprobe failed on {file_path}: {proc.stderr.strip()}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid FFprobe JSON: {exc}") from exc

    streams = data.get("streams", [])
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not audio_stream:
        raise RuntimeError(f"No audio stream found in: {file_path}")
    fmt = data.get("format", {})
    duration = float(audio_stream.get("duration") or fmt.get("duration") or 0.0)
    sample_rate = int(audio_stream.get("sample_rate") or 0)
    channels = int(audio_stream.get("channels") or 0)
    codec = str(audio_stream.get("codec_name") or "unknown")
    size_bytes = int(fmt.get("size") or os.path.getsize(file_path))
    if duration <= 0 or channels <= 0:
        raise RuntimeError(f"Invalid audio stream metadata for: {file_path}")
    return {
        "file_path": os.path.abspath(file_path),
        "duration": duration,
        "sample_rate": sample_rate,
        "channels": channels,
        "codec": codec,
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / 1048576, 2),
    }
