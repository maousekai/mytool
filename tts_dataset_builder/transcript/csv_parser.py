"""CSV/TSV/semicolon/pipe transcript parser."""

import csv
import io
import os
from typing import Any, Dict, List

from .cleaner import clean_vietnamese_text


def _open_source(value: str):
    if os.path.isfile(value):
        return open(value, "r", encoding="utf-8-sig", newline=""), True
    return io.StringIO(value), False


def _detect_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        # Prefer tab/semicolon/comma. Pipe is last because novel text can contain '|'.
        counts = {d: sample.count(d) for d in ("\t", ";", ",", "|")}
        return max(counts, key=counts.get) if max(counts.values(), default=0) else ","


def parse_csv_transcript(file_path_or_content: str) -> List[Dict[str, Any]]:
    f, should_close = _open_source(file_path_or_content)
    try:
        sample = f.read(8192)
        f.seek(0)
        delimiter = _detect_delimiter(sample)
        rows = list(csv.reader(f, delimiter=delimiter))
    finally:
        if should_close:
            f.close()

    if not rows:
        return []

    first = [c.strip().casefold() for c in rows[0]]
    aliases = {
        "start": {"start", "start_time", "starttime", "start_sec", "begin", "from"},
        "end": {"end", "end_time", "endtime", "end_sec", "to"},
        "text": {"text", "transcript", "sentence", "content", "line"},
    }
    start_col = next((i for i, c in enumerate(first) if c in aliases["start"]), -1)
    end_col = next((i for i, c in enumerate(first) if c in aliases["end"]), -1)
    text_col = next((i for i, c in enumerate(first) if c in aliases["text"]), -1)
    has_header = min(start_col, end_col, text_col) >= 0

    if not has_header:
        if len(rows[0]) < 3:
            return []
        start_col, end_col, text_col = 0, 1, 2

    results: List[Dict[str, Any]] = []
    for row in rows[1 if has_header else 0:]:
        if not row or max(start_col, end_col, text_col) >= len(row):
            continue
        try:
            start = float(row[start_col].strip().replace(",", ".") if delimiter != "," else row[start_col].strip())
            end = float(row[end_col].strip().replace(",", ".") if delimiter != "," else row[end_col].strip())
        except (TypeError, ValueError):
            continue
        text = clean_vietnamese_text(row[text_col])
        results.append({
            "index": len(results) + 1,
            "start": round(start, 3),
            "end": round(end, 3),
            "duration": round(end - start, 3),
            "text": text,
        })

    results.sort(key=lambda x: (x["start"], x["end"]))
    for i, item in enumerate(results, 1):
        item["index"] = i
    return results
