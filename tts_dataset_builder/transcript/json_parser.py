"""
JSON transcript parser for Vietnamese TTS Dataset Builder.
Supports various JSON structures with start, end, text.
"""

import json
from typing import List, Dict, Any
from .cleaner import clean_vietnamese_text


def parse_json_transcript(file_path_or_content: str) -> List[Dict[str, Any]]:
    """
    Parses JSON transcript file or JSON string.
    Returns list of records: [{"start": float, "end": float, "text": str}]
    """
    if file_path_or_content.strip().startswith("[") or file_path_or_content.strip().startswith("{"):
        raw_data = json.loads(file_path_or_content)
    else:
        with open(file_path_or_content, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

    # Could be wrapped in a root object like {"segments": [...]} or directly a list
    items = []
    if isinstance(raw_data, dict):
        if "segments" in raw_data:
            items = raw_data["segments"]
        elif "data" in raw_data:
            items = raw_data["data"]
        elif "transcript" in raw_data:
            items = raw_data["transcript"]
        else:
            # Maybe keys are line ids
            items = list(raw_data.values())
    elif isinstance(raw_data, list):
        items = raw_data
    else:
        raise ValueError("Invalid JSON format: expected list or object with segments")

    results: List[Dict[str, Any]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue

        # Start time key candidates
        start_val = item.get("start", item.get("start_time", item.get("startTime", None)))
        end_val = item.get("end", item.get("end_time", item.get("endTime", None)))
        text_val = item.get("text", item.get("sentence", item.get("content", "")))

        if start_val is None or end_val is None:
            continue

        try:
            start_f = float(start_val)
            end_f = float(end_val)
        except (ValueError, TypeError):
            continue

        cleaned_text = clean_vietnamese_text(str(text_val))

        results.append({
            "index": idx + 1,
            "start": round(start_f, 3),
            "end": round(end_f, 3),
            "duration": round(end_f - start_f, 3),
            "text": cleaned_text,
        })

    # Sort by start time
    results.sort(key=lambda x: x["start"])
    return results
