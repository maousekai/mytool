"""
FFmpeg and FFprobe wrapper for audio inspection and conversion.
Cross-platform support (Windows & Linux).
"""

import os
import shutil
import subprocess
import time
import json
from typing import Optional, Tuple, Dict, Any
from .logger import get_logger, log_ffmpeg_cmd

logger = get_logger()

# Optional custom paths via environment variables
CUSTOM_FFMPEG_BIN = os.environ.get("FFMPEG_PATH", "")
CUSTOM_FFPROBE_BIN = os.environ.get("FFPROBE_PATH", "")


def find_binary(name: str, custom_path: str = "") -> Optional[str]:
    """Find executable on system PATH or fallback locations."""
    if custom_path and os.path.isfile(custom_path):
        return custom_path

    # Check which/PATH
    found = shutil.which(name)
    if found:
        return found

    # Windows common locations
    if os.name == "nt":
        exe_name = f"{name}.exe"
        candidates = [
            os.path.join(os.getcwd(), exe_name),
            os.path.join(os.getcwd(), "bin", exe_name),
            os.path.join(os.environ.get("USERPROFILE", ""), "ffmpeg", "bin", exe_name),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links", exe_name),
            f"C:\\ffmpeg\\bin\\{exe_name}",
            f"C:\\Program Files\\ffmpeg\\bin\\{exe_name}",
            f"C:\\tools\\ffmpeg\\bin\\{exe_name}",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c

    return None


def get_ffmpeg_path() -> Optional[str]:
    return find_binary("ffmpeg", CUSTOM_FFMPEG_BIN)


def get_ffprobe_path() -> Optional[str]:
    return find_binary("ffprobe", CUSTOM_FFPROBE_BIN)


def check_ffmpeg() -> Tuple[bool, str]:
    """
    Check if FFmpeg and FFprobe are installed and usable.
    Returns (is_ok, message_or_guide).
    """
    ffmpeg_bin = get_ffmpeg_path()
    ffprobe_bin = get_ffprobe_path()

    missing = []
    if not ffmpeg_bin:
        missing.append("ffmpeg")
    if not ffprobe_bin:
        missing.append("ffprobe")

    if missing:
        guide = (
            f"LỖI: Không tìm thấy {' và '.join(missing)} trên hệ thống!\n"
            "Vui lòng cài đặt FFmpeg theo một trong các cách sau:\n\n"
            "=== DÀNH CHO WINDOWS ===\n"
            "Cách 1 (Nhanh nhất qua PowerShell / Terminal):\n"
            "    winget install Gyan.FFmpeg\n\n"
            "Cách 2 (Tải thủ công):\n"
            "  1. Truy cập https://www.gyan.dev/ffmpeg/builds/\n"
            "  2. Tải bản 'ffmpeg-release-essentials.zip'\n"
            "  3. Giải nén vào thư mục, ví dụ: C:\\ffmpeg\n"
            "  4. Thêm C:\\ffmpeg\\bin vào System PATH (Biến môi trường Windows)\n"
            "  (Hoặc copy ffmpeg.exe & ffprobe.exe vào ngay thư mục chứa app.py)\n\n"
            "=== DÀNH CHO LINUX / UBUNTU ===\n"
            "    sudo apt-get update && sudo apt-get install -y ffmpeg\n"
        )
        return False, guide

    # Test execution
    try:
        res = subprocess.run(
            [ffmpeg_bin, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if res.returncode != 0:
            return False, f"FFmpeg trả về lỗi khi chạy: {res.stderr}"
        first_line = res.stdout.split("\n")[0] if res.stdout else "FFmpeg OK"
        return True, f"FFmpeg sẵn sàng: {first_line}"
    except Exception as e:
        return False, f"Lỗi khi kiểm tra FFmpeg: {str(e)}"


def run_ffmpeg(args: list[str], timeout: Optional[int] = None) -> Tuple[int, str, str]:
    """
    Execute ffmpeg with arguments. Returns (returncode, stdout, stderr).
    """
    ffmpeg_bin = get_ffmpeg_path()
    if not ffmpeg_bin:
        raise FileNotFoundError("FFmpeg executable not found. Please install FFmpeg.")

    cmd = [ffmpeg_bin] + args
    start_t = time.time()
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        duration = time.time() - start_t
        log_ffmpeg_cmd(cmd, proc.returncode, duration, proc.stderr)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        duration = time.time() - start_t
        log_ffmpeg_cmd(cmd, -1, duration, f"Timeout after {timeout}s")
        raise


def probe_audio(file_path: str) -> Dict[str, Any]:
    """
    Inspect an audio file using ffprobe.
    Returns dictionary with: duration, sample_rate, channels, format, codec, bitrate.
    """
    ffprobe_bin = get_ffprobe_path()
    if not ffprobe_bin:
        raise FileNotFoundError("FFprobe executable not found. Please install FFmpeg.")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    cmd = [
        ffprobe_bin,
        "-v", "error",
        "-show_entries", "format=duration,size,bit_rate:stream=codec_name,sample_rate,channels,duration",
        "-of", "json",
        file_path,
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
    if proc.returncode != 0:
        raise RuntimeError(f"FFprobe failed on {file_path}: {proc.stderr}")

    data = json.loads(proc.stdout)
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    audio_stream = next((s for s in streams if s.get("codec_name") not in ("png", "mjpeg", "bmp")), {})
    if not audio_stream and streams:
        audio_stream = streams[0]

    duration = float(audio_stream.get("duration") or fmt.get("duration") or 0.0)
    sample_rate = int(audio_stream.get("sample_rate") or 0)
    channels = int(audio_stream.get("channels") or 1)
    codec = audio_stream.get("codec_name", "unknown")
    size_bytes = int(fmt.get("size") or os.path.getsize(file_path))

    return {
        "file_path": file_path,
        "duration": duration,
        "sample_rate": sample_rate,
        "channels": channels,
        "codec": codec,
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / (1024 * 1024), 2),
    }
