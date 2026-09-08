"""
SRT Subtitle parser for Vietnamese TTS Dataset Builder.
Parses standard SubRip format:
1
00:00:12,350 --> 00:00:18,720
Ta mỗi ngày nhận được một hệ thống mới.
"""

import re
from typing import List, Dict, Any
from .cleaner import clean_vietnamese_text


def srt_time_to_seconds(time_str: str) -> float:
    """Convert '00:01:23,450' or '00:01:23.450' to float seconds."""
    time_str = time_str.strip().replace(",", ".")
    parts = time_str.split(":")
    if len(parts) == 3:
        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
        return hours * 3600.0 + minutes * 60.0 + seconds
    elif len(parts) == 2:
        minutes = float(parts[0])
        seconds = float(parts[1])
        return minutes * 60.0 + seconds
    return float(time_str)


def parse_srt_transcript(file_path_or_content: str) -> List[Dict[str, Any]]:
    """
    Parses SRT subtitle content or file.
    Returns list of records with start, end, duration, text.
    """
    if "\n" in file_path_or_content and not file_path_or_content.strip().endswith(".srt"):
        content = file_path_or_content
    else:
        with open(file_path_or_content, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read()

    # Normalize newlines
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    # Blocks separated by double newlines
    blocks = re.split(r"\n\s*\n", content.strip())

    results: List[Dict[str, Any]] = []
    timing_regex = re.compile(
        r"(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})"
    )

    idx = 0
    for block in blocks:
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue

        # Look for timing line
        match = None
        timing_line_idx = -1
        for i, line in enumerate(lines):
            m = timing_regex.search(line)
            if m:
                match = m
                timing_line_idx = i
                break

        if not match or timing_line_idx == -1:
            continue

        start_sec = srt_time_to_seconds(match.group(1))
        end_sec = srt_time_to_seconds(match.group(2))

        # Text is all lines following the timing line
        text_lines = lines[timing_line_idx + 1:]
        raw_text = " ".join(text_lines)
        cleaned_text = clean_vietnamese_text(raw_text)

        if not cleaned_text:
            continue

        idx += 1
        results.append({
            "index": idx,
            "start": round(start_sec, 3),
            "end": round(end_sec, 3),
            "duration": round(end_sec - start_sec, 3),
            "text": cleaned_text,
        })

    results.sort(key=lambda x: x["start"])
    return results
