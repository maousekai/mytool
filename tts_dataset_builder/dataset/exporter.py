"""
Dataset Exporter for Vietnamese TTS Dataset Builder.
Creates dataset.zip containing wavs/, metadata.csv, metadata.json,
dataset_report.json, and rejected.csv.
"""

import os
import zipfile
from typing import Optional
from ..utils.logger import get_logger

logger = get_logger()


def export_dataset_to_zip(
    dataset_dir: str = "output_dataset",
    output_zip_path: Optional[str] = None,
) -> str:
    """
    Compresses the dataset into a standard distributable ZIP archive.
    """
    if not os.path.exists(dataset_dir):
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    target_zip = output_zip_path or os.path.join(dataset_dir, "dataset.zip")
    os.makedirs(os.path.dirname(os.path.abspath(target_zip)), exist_ok=True)

    wavs_dir = os.path.join(dataset_dir, "wavs")
    files_to_include = [
        "metadata.csv",
        "metadata.json",
        "rejected.csv",
        "dataset_report.json",
    ]

    logger.info(f"Creating dataset ZIP export: {target_zip}")

    with zipfile.ZipFile(target_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Add root metadata files
        for fname in files_to_include:
            fpath = os.path.join(dataset_dir, fname)
            if os.path.exists(fpath):
                zf.write(fpath, arcname=fname)

        # 2. Add all wav files inside wavs/
        if os.path.exists(wavs_dir):
            for wav_file in sorted(os.listdir(wavs_dir)):
                if wav_file.lower().endswith(".wav"):
                    full_wav_path = os.path.join(wavs_dir, wav_file)
                    zf.write(full_wav_path, arcname=f"wavs/{wav_file}")

    file_size_mb = os.path.getsize(target_zip) / (1024 * 1024)
    logger.info(f"Export completed: {target_zip} ({file_size_mb:.2f} MB)")
    return target_zip
