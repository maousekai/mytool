"""
Dataset Validator for Vietnamese TTS Dataset Builder.
Inspects an existing or generated dataset directory and performs rigorous checks:
- Missing WAV files referenced in metadata
- Duplicate transcripts
- Duplicate audio files (SHA256 content hashing)
- Empty or corrupted transcripts
- Duration violations (< min or > max duration)
- Sample rate / channel consistency
- Clipping detection
- High silence ratio (> 40%)
- Invalid filenames
Computes individual Quality Score (0-100) and overall dataset health metrics.
"""

import os
import csv
import hashlib
from typing import Dict, Any, List
from ..audio.analyzer import analyze_wav_file


class DatasetValidator:
    def __init__(
        self,
        dataset_dir: str = "output_dataset",
        expected_sample_rate: int = 24000,
        min_duration: float = 2.0,
        max_duration: float = 12.0,
    ):
        self.dataset_dir = dataset_dir
        self.wavs_dir = os.path.join(dataset_dir, "wavs")
        self.metadata_csv = os.path.join(dataset_dir, "metadata.csv")
        self.expected_sample_rate = expected_sample_rate
        self.min_duration = min_duration
        self.max_duration = max_duration

    def validate_dataset(self) -> Dict[str, Any]:
        """
        Runs comprehensive validation across all samples in the dataset.
        """
        if not os.path.exists(self.dataset_dir):
            return {
                "valid": False,
                "error": f"Thư mục dataset không tồn tại: {self.dataset_dir}",
                "samples": [],
                "summary": {},
            }

        if not os.path.exists(self.metadata_csv):
            return {
                "valid": False,
                "error": f"Không tìm thấy metadata.csv trong {self.dataset_dir}",
                "samples": [],
                "summary": {},
            }

        # Read metadata.csv (filename|text)
        metadata_entries: List[Dict[str, str]] = []
        with open(self.metadata_csv, "r", encoding="utf-8", errors="replace") as f:
            for line_idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                if "|" in line:
                    parts = line.split("|", 1)
                    metadata_entries.append({"filename": parts[0].strip(), "text": parts[1].strip()})
                elif "\t" in line:
                    parts = line.split("\t", 1)
                    metadata_entries.append({"filename": parts[0].strip(), "text": parts[1].strip()})
                elif "," in line and not line.lower().startswith("filename"):
                    parts = line.split(",", 1)
                    metadata_entries.append({"filename": parts[0].strip(), "text": parts[1].strip()})

        text_counts: Dict[str, int] = {}
        for entry in metadata_entries:
            t = entry["text"].lower().strip()
            text_counts[t] = text_counts.get(t, 0) + 1

        audio_hashes: Dict[str, str] = {}
        results: List[Dict[str, Any]] = []

        total_score = 0.0
        missing_count = 0
        duplicate_text_count = 0
        duplicate_audio_count = 0
        empty_text_count = 0
        duration_warning_count = 0
        sample_rate_mismatch_count = 0
        clipping_count_total = 0
        high_silence_count = 0

        for idx, entry in enumerate(metadata_entries):
            fname = entry["filename"]
            text = entry["text"]
            wav_path = os.path.join(self.wavs_dir, fname)

            issues = []
            score = 100.0

            # 1. Check filename format (e.g. 000001.wav)
            base_name, ext = os.path.splitext(fname)
            if ext.lower() != ".wav" or not base_name.isdigit():
                issues.append(f"Tên file không đúng chuẩn: '{fname}'")
                score -= 10.0

            # 2. Check empty transcript
            if not text:
                issues.append("Transcript rỗng")
                score = 0.0
                empty_text_count += 1

            # 3. Duplicate transcript
            if text and text_counts.get(text.lower().strip(), 0) > 1:
                issues.append(f"Transcript trùng lặp ({text_counts[text.lower().strip()]} lần)")
                score -= 15.0
                duplicate_text_count += 1

            # 4. Check file existence
            if not os.path.exists(wav_path):
                issues.append("File WAV không tồn tại trên đĩa")
                score = 0.0
                missing_count += 1
                results.append({
                    "id": idx + 1,
                    "filename": fname,
                    "text": text,
                    "duration": 0.0,
                    "quality_score": 0.0,
                    "issues": issues,
                    "status": "ERROR",
                })
                continue

            # 5. Duplicate audio hash check (read first 8KB or entire file)
            try:
                with open(wav_path, "rb") as af:
                    content = af.read()
                file_hash = hashlib.sha256(content).hexdigest()
                if file_hash in audio_hashes:
                    issues.append(f"Trùng file audio với {audio_hashes[file_hash]}")
                    score -= 25.0
                    duplicate_audio_count += 1
                else:
                    audio_hashes[file_hash] = fname
            except Exception:
                pass

            # 6. Audio quality analysis
            analysis = analyze_wav_file(wav_path)
            if not analysis["valid"]:
                issues.append(f"Lỗi audio: {analysis.get('error', 'Hỏng')}")
                score = 0.0
            else:
                dur = analysis["duration"]
                sr = analysis["sample_rate"]
                channels = analysis["channels"]
                clips = analysis["clipping_count"]
                silence = analysis["silence_ratio"]

                # Duration bounds
                if dur < self.min_duration:
                    issues.append(f"Duration ngắn ({dur:.2f}s < {self.min_duration}s)")
                    score -= 15.0
                    duration_warning_count += 1
                elif dur > self.max_duration:
                    issues.append(f"Duration dài ({dur:.2f}s > {self.max_duration}s)")
                    score -= 10.0
                    duration_warning_count += 1

                # Sample rate & channels
                if sr != self.expected_sample_rate:
                    issues.append(f"Sample rate sai ({sr}Hz != {self.expected_sample_rate}Hz)")
                    score -= 20.0
                    sample_rate_mismatch_count += 1
                if channels != 1:
                    issues.append(f"Không phải Mono ({channels} channels)")
                    score -= 20.0

                # Clipping
                if clips > 0:
                    issues.append(f"Bị clipping ({clips} samples)")
                    score -= min(30.0, clips * 2.0)
                    clipping_count_total += 1

                # Silence ratio
                if silence > 0.40:
                    issues.append(f"Tỷ lệ khoảng lặng cao ({silence * 100:.1f}%)")
                    score -= 15.0
                    high_silence_count += 1

            final_score = max(0.0, min(100.0, round(score, 1)))
            total_score += final_score

            status = "PERFECT" if final_score >= 90 else ("GOOD" if final_score >= 70 else ("WARNING" if final_score >= 50 else "CRITICAL"))

            results.append({
                "id": idx + 1,
                "filename": fname,
                "text": text,
                "duration": analysis.get("duration", 0.0),
                "sample_rate": analysis.get("sample_rate", 0),
                "peak_db": analysis.get("peak_db", 0.0),
                "rms_db": analysis.get("rms_db", 0.0),
                "quality_score": final_score,
                "issues": issues,
                "status": status,
            })

        avg_score = round(total_score / len(results), 1) if results else 0.0

        summary = {
            "total_checked": len(results),
            "average_quality_score": avg_score,
            "missing_wav_files": missing_count,
            "duplicate_transcripts": duplicate_text_count,
            "duplicate_audio_files": duplicate_audio_count,
            "empty_transcripts": empty_text_count,
            "duration_warnings": duration_warning_count,
            "sample_rate_mismatches": sample_rate_mismatch_count,
            "clipped_samples": clipping_count_total,
            "high_silence_samples": high_silence_count,
        }

        return {
            "valid": True,
            "summary": summary,
            "samples": results,
        }
