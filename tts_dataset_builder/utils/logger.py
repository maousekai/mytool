"""
Logging utility for Vietnamese TTS Dataset Builder.
Outputs both to console and logs/app.log.
"""

import os
import sys
import logging
from typing import Optional

LOGGER_NAME = "tts_dataset_builder"
_logger: Optional[logging.Logger] = None


def setup_logger(log_dir: str = "logs", log_filename: str = "app.log") -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_filename)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if re-called
    if not logger.handlers:
        # File handler (UTF-8 encoded)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s:%(funcName)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        return setup_logger()
    return _logger


def log_ffmpeg_cmd(cmd: list[str], returncode: int, duration_sec: float = 0.0, stderr: str = ""):
    logger = get_logger()
    cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)
    if returncode == 0:
        logger.debug(f"FFmpeg executed in {duration_sec:.2f}s: {cmd_str}")
    else:
        logger.error(
            f"FFmpeg failed (code {returncode}) in {duration_sec:.2f}s: {cmd_str}\nSTDERR:\n{stderr[-500:]}"
        )


def log_rejected_sample(filename: str, text: str, reason: str, start: float, end: float, duration: float):
    logger = get_logger()
    logger.warning(
        f"REJECTED SAMPLE | file={filename} | duration={duration:.2f}s [{start:.2f}->{end:.2f}] | reason={reason} | text='{text}'"
    )
