"""
CSV / TSV / Pipe-separated transcript parser for Vietnamese TTS Dataset Builder.
"""

import csv
import io
from typing import List, Dict, Any
from .cleaner import clean_vietnamese_text


def parse_csv_transcript(file_path_or_content: str) -> List[Dict[str, Any]]:
    """
    Parses CSV transcript.
    Auto-detects delimiter (, | \t ;)
    Expected columns: start, end, text (in any order, or positional start, end, text).
    """
    if "\n" in file_path_or_content and not file_path_or_content.strip().endswith(".csv"):
        f = io.StringIO(file_path_or_content)
    else:
        f = open(file_path_or_content, "r", encoding="utf-8-sig")

    try:
        sample = f.read(2048)
        f.seek(0)
        # Sniff delimiter
        delimiter = ","
        for d in ["|", "\t", ";", ","]:
            if d in sample:
                delimiter = d
                break

        reader = csv.reader(f, delimiter=delimiter)
        rows = list(reader)
    finally:
        if hasattr(f, "close") and not isinstance(f, io.StringIO):
            f.close()

    if not rows:
        return []

    # Check header
    first_row = [c.strip().lower() for c in rows[0]]
    has_header = False
    start_col, end_col, text_col = -1, -1, -1

    for idx, col in enumerate(first_row):
        if col in ("start", "start_time", "start_sec", "begin", "from"):
            start_col = idx
            has_header = True
        elif col in ("end", "end_time", "end_sec", "to"):
            end_col = idx
            has_header = True
        elif col in ("text", "transcript", "sentence", "content", "line"):
            text_col = idx
            has_header = True

    # Fallback to positional: 0=start, 1=end, 2=text or 0=filename, 1=text
    start_idx = 1 if has_header else 0
    if not has_header:
        if len(rows[0]) >= 3:
            start_col, end_col, text_col = 0, 1, 2
        elif len(rows[0]) == 2:
            # maybe metadata.csv format (filename|text)
            return []

    results: List[Dict[str, Any]] = []
    line_num = 0

    for r in rows[start_idx:]:
        if not r or len(r) <= max(start_col, end_col):
            continue

        try:
            start_f = float(r[start_col].strip())
            end_f = float(r[end_col].strip())
            raw_text = r[text_col].strip() if text_col < len(r) else ""
            cleaned_text = clean_vietnamese_text(raw_text)

            line_num += 1
            results.append({
                "index": line_num,
                "start": round(start_f, 3),
                "end": round(end_f, 3),
                "duration": round(end_f - start_f, 3),
                "text": cleaned_text,
            })
        except (ValueError, IndexError):
            continue

    results.sort(key=lambda x: x["start"])
    return results
