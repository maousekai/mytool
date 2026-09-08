"""Verified ZIP exporters for datasets and the standalone Windows source package."""

import os
import zipfile
from typing import Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger()


def inspect_zip(zip_path: str) -> Dict[str, object]:
    if not os.path.isfile(zip_path):
        raise FileNotFoundError(f"ZIP was not created: {zip_path}")
    with open(zip_path, "rb") as fh:
        magic = fh.read(4)
    if magic != b"PK\x03\x04":
        raise RuntimeError(f"Invalid ZIP signature: expected 50 4B 03 04, got {magic.hex(' ')}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        bad_member = zf.testzip()
        if bad_member is not None:
            raise RuntimeError(f"ZIP CRC validation failed at member: {bad_member}")
        names = zf.namelist()
    return {
        "path": os.path.abspath(zip_path),
        "size_bytes": os.path.getsize(zip_path),
        "file_count": len(names),
        "wav_count": sum(1 for n in names if n.startswith("wavs/") and n.lower().endswith(".wav")),
        "names": names,
    }


def _metadata_wavs(metadata_csv: str) -> List[str]:
    names: List[str] = []
    seen = set()
    with open(metadata_csv, "r", encoding="utf-8-sig", errors="strict") as f:
        for line_no, raw in enumerate(f, 1):
            line = raw.strip()
            if not line:
                continue
            if "|" not in line:
                raise RuntimeError(f"Malformed metadata.csv line {line_no}: missing '|' delimiter")
            filename, text = line.split("|", 1)
            filename = filename.strip()
            if not filename or not text.strip():
                raise RuntimeError(f"Malformed metadata.csv line {line_no}: filename/text is empty")
            if os.path.basename(filename) != filename or not filename.lower().endswith(".wav"):
                raise RuntimeError(f"Unsafe/invalid WAV filename in metadata line {line_no}: {filename}")
            if filename in seen:
                raise RuntimeError(f"Duplicate WAV filename in metadata.csv: {filename}")
            seen.add(filename)
            names.append(filename)
    if not names:
        raise RuntimeError("metadata.csv contains no training samples")
    return names


def export_dataset_to_zip(dataset_dir: str = "output_dataset", output_zip_path: Optional[str] = None) -> str:
    dataset_dir = os.path.abspath(dataset_dir)
    if not os.path.isdir(dataset_dir):
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")
    wavs_dir = os.path.join(dataset_dir, "wavs")
    metadata_csv = os.path.join(dataset_dir, "metadata.csv")
    if not os.path.isdir(wavs_dir):
        raise FileNotFoundError(f"Dataset WAV directory not found: {wavs_dir}")
    if not os.path.isfile(metadata_csv):
        raise FileNotFoundError(f"metadata.csv not found: {metadata_csv}")

    wav_files = _metadata_wavs(metadata_csv)
    missing = [name for name in wav_files if not os.path.isfile(os.path.join(wavs_dir, name))]
    if missing:
        preview = ", ".join(missing[:10])
        raise RuntimeError(f"Cannot export: {len(missing)} metadata WAV file(s) are missing: {preview}")

    disk_wavs = {
        name for name in os.listdir(wavs_dir)
        if name.lower().endswith(".wav") and os.path.isfile(os.path.join(wavs_dir, name))
    }
    orphan_count = len(disk_wavs.difference(wav_files))
    if orphan_count:
        logger.warning("Ignoring %d orphan WAV file(s) not referenced by metadata.csv", orphan_count)

    target_zip = os.path.abspath(output_zip_path or os.path.join(dataset_dir, "dataset.zip"))
    os.makedirs(os.path.dirname(target_zip), exist_ok=True)
    if os.path.exists(target_zip):
        os.remove(target_zip)

    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for fname in ("metadata.csv", "metadata.json", "rejected.csv", "dataset_report.json"):
            fpath = os.path.join(dataset_dir, fname)
            if os.path.isfile(fpath):
                zf.write(fpath, arcname=fname)
        for wav_file in wav_files:
            zf.write(os.path.join(wavs_dir, wav_file), arcname=f"wavs/{wav_file}")

    info = inspect_zip(target_zip)
    if info["wav_count"] != len(wav_files):
        raise RuntimeError(f"ZIP WAV count mismatch: expected {len(wav_files)}, found {info['wav_count']}")
    if "metadata.csv" not in info["names"]:
        raise RuntimeError("ZIP validation failed: metadata.csv is missing")
    logger.info(
        "Dataset ZIP PASS | path=%s | size=%.2f MB | wav_files=%d | orphan_ignored=%d",
        target_zip, int(info["size_bytes"]) / (1024 * 1024), len(wav_files), orphan_count,
    )
    return target_zip


def export_source_package(source_dir: str, output_zip_path: str) -> str:
    source_dir = os.path.abspath(source_dir)
    target_zip = os.path.abspath(output_zip_path)
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(f"Source package directory not found: {source_dir}")
    os.makedirs(os.path.dirname(target_zip), exist_ok=True)
    if os.path.exists(target_zip):
        os.remove(target_zip)

    excluded_dirs = {"__pycache__", ".git", ".pytest_cache", "output_dataset", "logs"}
    excluded_exts = {".pyc", ".pyo", ".pcm", ".db", ".log", ".zip"}
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in excluded_dirs]
            for filename in files:
                if os.path.splitext(filename)[1].lower() in excluded_exts:
                    continue
                full_path = os.path.join(root, filename)
                rel = os.path.relpath(full_path, source_dir).replace(os.sep, "/")
                zf.write(full_path, arcname=rel)

    info = inspect_zip(target_zip)
    required = {"app.py", "requirements.txt", "run_windows.bat"}
    missing = sorted(required.difference(set(info["names"])))
    if missing:
        raise RuntimeError(f"Windows source package missing required files: {', '.join(missing)}")
    logger.info("Source package ZIP PASS | path=%s | size=%.2f MB | files=%d", target_zip, int(info["size_bytes"]) / (1024 * 1024), int(info["file_count"]))
    return target_zip
