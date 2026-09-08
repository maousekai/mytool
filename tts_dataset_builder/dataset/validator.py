"""Dataset validator with PASS / WARNING / REJECT severity."""

import csv
import hashlib
import os
from typing import Any, Dict, List, Tuple

from ..audio.analyzer import analyze_wav_file


class DatasetValidator:
    def __init__(
        self,
        dataset_dir: str = "output_dataset",
        expected_sample_rate: int = 24000,
        min_duration: float = 2.0,
        max_duration: float = 12.0,
    ):
        self.dataset_dir = os.path.abspath(dataset_dir)
        self.wavs_dir = os.path.join(self.dataset_dir, "wavs")
        self.metadata_csv = os.path.join(self.dataset_dir, "metadata.csv")
        self.expected_sample_rate = int(expected_sample_rate)
        self.min_duration = float(min_duration)
        self.max_duration = float(max_duration)

    @staticmethod
    def _sha256(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _read_metadata(self) -> Tuple[List[Dict[str, str]], int]:
        entries: List[Dict[str, str]] = []
        malformed = 0
        with open(self.metadata_csv, "r", encoding="utf-8-sig", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                if "|" in line:
                    filename, text = line.split("|", 1)
                elif "\t" in line:
                    filename, text = line.split("\t", 1)
                else:
                    try:
                        row = next(csv.reader([line]))
                    except Exception:
                        malformed += 1
                        continue
                    if len(row) < 2 or row[0].strip().lower() == "filename":
                        malformed += 1
                        continue
                    filename, text = row[0], ",".join(row[1:])
                filename = filename.strip()
                text = text.strip()
                if not filename:
                    malformed += 1
                    continue
                entries.append({"filename": filename, "text": text})
        return entries, malformed

    def validate_dataset(self) -> Dict[str, Any]:
        if not os.path.isdir(self.dataset_dir):
            return {"valid": False, "ready_for_training": False, "error": f"Thư mục dataset không tồn tại: {self.dataset_dir}", "summary": {}, "samples": []}
        if not os.path.isfile(self.metadata_csv):
            return {"valid": False, "ready_for_training": False, "error": "Không tìm thấy metadata.csv", "summary": {}, "samples": []}
        if not os.path.isdir(self.wavs_dir):
            return {"valid": False, "ready_for_training": False, "error": "Không tìm thấy thư mục wavs/", "summary": {}, "samples": []}

        entries, malformed_count = self._read_metadata()
        filename_counts: Dict[str, int] = {}
        text_counts: Dict[str, int] = {}
        for e in entries:
            filename_counts[e["filename"]] = filename_counts.get(e["filename"], 0) + 1
            key = e["text"].casefold().strip()
            if key:
                text_counts[key] = text_counts.get(key, 0) + 1

        referenced = {e["filename"] for e in entries}
        disk_wavs = {
            f for f in os.listdir(self.wavs_dir)
            if f.lower().endswith(".wav") and os.path.isfile(os.path.join(self.wavs_dir, f))
        }
        orphan_wavs = sorted(disk_wavs - referenced)

        hashes: Dict[str, str] = {}
        results: List[Dict[str, Any]] = []
        counters = {
            "missing_wav_files": 0,
            "duplicate_transcripts": 0,
            "duplicate_audio_files": 0,
            "duplicate_filenames": 0,
            "empty_transcripts": 0,
            "duration_warnings": 0,
            "sample_rate_mismatches": 0,
            "channel_mismatches": 0,
            "sample_width_mismatches": 0,
            "clipped_samples": 0,
            "high_silence_samples": 0,
            "corrupt_audio_files": 0,
        }
        scores: List[float] = []
        pass_count = warning_count = reject_count = 0

        for idx, entry in enumerate(entries, 1):
            fname = entry["filename"]
            text = entry["text"]
            wav_path = os.path.join(self.wavs_dir, fname)
            warnings: List[str] = []
            errors: List[str] = []

            base, ext = os.path.splitext(fname)
            if ext.lower() != ".wav" or not base.isdigit() or os.path.basename(fname) != fname:
                errors.append(f"Tên file không hợp lệ: {fname}")
            if filename_counts.get(fname, 0) > 1:
                errors.append(f"Filename xuất hiện {filename_counts[fname]} lần trong metadata")
                counters["duplicate_filenames"] += 1
            if not text:
                errors.append("Transcript rỗng")
                counters["empty_transcripts"] += 1
            elif text_counts.get(text.casefold().strip(), 0) > 1:
                warnings.append(f"Transcript trùng ({text_counts[text.casefold().strip()]} lần)")
                counters["duplicate_transcripts"] += 1

            if not os.path.isfile(wav_path):
                errors.append("File WAV không tồn tại")
                counters["missing_wav_files"] += 1
                analysis: Dict[str, Any] = {"valid": False, "duration": 0.0, "sample_rate": 0, "quality_score": 0.0}
            else:
                analysis = analyze_wav_file(wav_path)
                if not analysis.get("valid"):
                    errors.append(f"Audio hỏng/không đọc được: {analysis.get('error', 'unknown')}")
                    counters["corrupt_audio_files"] += 1
                else:
                    try:
                        digest = self._sha256(wav_path)
                        if digest in hashes:
                            warnings.append(f"Audio trùng byte-for-byte với {hashes[digest]}")
                            counters["duplicate_audio_files"] += 1
                        else:
                            hashes[digest] = fname
                    except OSError as exc:
                        errors.append(f"Không hash được audio: {exc}")

                    dur = float(analysis["duration"])
                    if dur < self.min_duration:
                        warnings.append(f"Duration ngắn: {dur:.2f}s < {self.min_duration:.2f}s")
                        counters["duration_warnings"] += 1
                    elif dur > self.max_duration:
                        warnings.append(f"Duration dài: {dur:.2f}s > {self.max_duration:.2f}s")
                        counters["duration_warnings"] += 1
                    if int(analysis["sample_rate"]) != self.expected_sample_rate:
                        errors.append(f"Sample rate {analysis['sample_rate']}Hz != {self.expected_sample_rate}Hz")
                        counters["sample_rate_mismatches"] += 1
                    if int(analysis.get("channels", 0)) != 1:
                        errors.append(f"Yêu cầu mono, nhận {analysis.get('channels')} channels")
                        counters["channel_mismatches"] += 1
                    if int(analysis.get("sample_width_bits", 0)) != 16:
                        errors.append(f"Yêu cầu PCM16, nhận {analysis.get('sample_width_bits')} bit")
                        counters["sample_width_mismatches"] += 1
                    if int(analysis.get("clipping_count", 0)) > 0:
                        warnings.append(f"Có clipping ({analysis['clipping_count']} samples)")
                        counters["clipped_samples"] += 1
                    if float(analysis.get("silence_ratio", 0.0)) > 0.40:
                        warnings.append(f"Silence cao ({analysis['silence_ratio'] * 100:.1f}%)")
                        counters["high_silence_samples"] += 1

            base_score = float(analysis.get("quality_score", 0.0)) if analysis.get("valid") else 0.0
            score = max(0.0, min(100.0, base_score - min(30.0, len(warnings) * 5.0)))
            if errors:
                status = "REJECT"
                score = min(score, 49.0)
                reject_count += 1
            elif warnings:
                status = "WARNING"
                warning_count += 1
            else:
                status = "PASS"
                pass_count += 1
            scores.append(score)
            results.append({
                "id": idx,
                "filename": fname,
                "text": text,
                "duration": float(analysis.get("duration", 0.0)),
                "sample_rate": int(analysis.get("sample_rate", 0)),
                "sample_width_bits": int(analysis.get("sample_width_bits", 0)),
                "peak_db": float(analysis.get("peak_db", 0.0)),
                "rms_db": float(analysis.get("rms_db", 0.0)),
                "quality_score": round(score, 1),
                "issues": errors + warnings,
                "errors": errors,
                "warnings": warnings,
                "status": status,
            })

        avg = round(sum(scores) / len(scores), 1) if scores else 0.0
        summary: Dict[str, Any] = {
            "total_checked": len(results),
            "average_quality_score": avg,
            "pass_samples": pass_count,
            "warning_samples": warning_count,
            "reject_samples": reject_count,
            "malformed_metadata_lines": malformed_count,
            "orphan_wav_files": len(orphan_wavs),
            **counters,
        }
        ready = bool(results) and reject_count == 0 and malformed_count == 0
        return {
            "valid": reject_count == 0 and malformed_count == 0,
            "ready_for_training": ready,
            "summary": summary,
            "orphan_wavs": orphan_wavs,
            "samples": results,
        }
