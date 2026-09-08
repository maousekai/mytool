"""
Dataset Exporter for Vietnamese TTS Dataset Builder.
Creates and verifies dataset.zip containing wavs/, metadata.csv,
metadata.json, dataset_report.json, and rejected.csv.
"""

import os
import zipfile
from typing import Optional
from ..utils.logger import get_logger

logger = get_logger()


def _verify_zip(zip_path: str, expected_wav_count: int) -> None:
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"ZIP was not created: {zip_path}")

    with open(zip_path, "rb") as fh:
        magic = fh.read(4)
    if magic != b"PK\x03\x04":
        raise RuntimeError(
            f"Invalid ZIP signature for {zip_path}: expected 50 4B 03 04, got {magic.hex(' ')}"
        )

    with zipfile.ZipFile(zip_path, "r") as zf:
        bad_member = zf.testzip()
        if bad_member is not None:
            raise RuntimeError(f"ZIP validation failed at member: {bad_member}")

        names = zf.namelist()
        wav_count = sum(1 for name in names if name.startswith("wavs/") and name.lower().endswith(".wav"))
        if wav_count != expected_wav_count:
            raise RuntimeError(
                f"ZIP WAV count mismatch: expected {expected_wav_count}, found {wav_count}"
            )

        if "metadata.csv" not in names:
            raise RuntimeError("ZIP validation failed: metadata.csv is missing")


def export_dataset_to_zip(
    dataset_dir: str = "output_dataset",
    output_zip_path: Optional[str] = None,
) -> str:
    """Compresses the dataset into a verified distributable ZIP archive."""
    dataset_dir = os.path.abspath(dataset_dir)
    if not os.path.isdir(dataset_dir):
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    wavs_dir = os.path.join(dataset_dir, "wavs")
    if not os.path.isdir(wavs_dir):
        raise FileNotFoundError(f"Dataset WAV directory not found: {wavs_dir}")

    wav_files = sorted(
        name for name in os.listdir(wavs_dir)
        if name.lower().endswith(".wav") and os.path.isfile(os.path.join(wavs_dir, name))
    )
    if not wav_files:
        raise RuntimeError("Dataset has no WAV files to export")

    metadata_csv = os.path.join(dataset_dir, "metadata.csv")
    if not os.path.isfile(metadata_csv):
        raise FileNotFoundError(f"metadata.csv not found: {metadata_csv}")

    target_zip = os.path.abspath(output_zip_path or os.path.join(dataset_dir, "dataset.zip"))
    os.makedirs(os.path.dirname(target_zip), exist_ok=True)

    if os.path.exists(target_zip):
        os.remove(target_zip)

    files_to_include = [
        "metadata.csv",
        "metadata.json",
        "rejected.csv",
        "dataset_report.json",
    ]

    logger.info(f"Creating dataset ZIP export: {target_zip}")

    with zipfile.ZipFile(
        target_zip,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        allowZip64=True,
    ) as zf:
        for fname in files_to_include:
            fpath = os.path.join(dataset_dir, fname)
            if os.path.isfile(fpath):
                zf.write(fpath, arcname=fname)

        for wav_file in wav_files:
            full_wav_path = os.path.join(wavs_dir, wav_file)
            zf.write(full_wav_path, arcname=f"wavs/{wav_file}")

    _verify_zip(target_zip, expected_wav_count=len(wav_files))

    file_size_mb = os.path.getsize(target_zip) / (1024 * 1024)
    logger.info(
        "ZIP created successfully | path=%s | size=%.2f MB | wav_files=%d | validation=PASS",
        target_zip,
        file_size_mb,
        len(wav_files),
    )
    return target_zip
