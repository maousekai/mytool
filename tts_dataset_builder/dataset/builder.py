"""
Dataset Builder Engine for Vietnamese TTS Dataset Builder.
Coordinates audio decoding, transcript parsing, short sentence merging,
padding, VAD refinement, cutting, quality checks, reporting, and resuming.
"""

import os
import csv
import json
import time
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime

from ..utils.logger import get_logger, log_rejected_sample
from ..utils.ffmpeg import check_ffmpeg, probe_audio
from ..audio.decoder import decode_source_to_pcm
from ..audio.cutter import calculate_slice_bounds, cut_pcm_slice
from ..audio.vad import refine_boundary_with_silence
from ..audio.analyzer import analyze_wav_file, normalize_audio_file
from ..transcript.json_parser import parse_json_transcript
from ..transcript.csv_parser import parse_csv_transcript
from ..transcript.srt_parser import parse_srt_transcript
from .database import DatasetDatabase

logger = get_logger()


class DatasetBuilder:
    def __init__(
        self,
        output_dir: str = "output_dataset",
        sample_rate: int = 24000,
        padding_before: float = 0.15,
        padding_after: float = 0.20,
        refine_vad: bool = False,
        min_duration: float = 2.0,
        max_duration: float = 12.0,
        auto_merge_short: bool = True,
        merge_silence_threshold: float = 0.80,
        peak_norm: bool = False,
        loudness_norm: bool = False,
        target_lufs: float = -20.0,
        db_path: Optional[str] = None,
    ):
        self.output_dir = output_dir
        self.wavs_dir = os.path.join(output_dir, "wavs")
        self.temp_pcm_dir = os.path.join(output_dir, "_temp_pcm")
        self.sample_rate = sample_rate
        self.padding_before = padding_before
        self.padding_after = padding_after
        self.refine_vad = refine_vad
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.auto_merge_short = auto_merge_short
        self.merge_silence_threshold = merge_silence_threshold
        self.peak_norm = peak_norm
        self.loudness_norm = loudness_norm
        self.target_lufs = target_lufs

        os.makedirs(self.wavs_dir, exist_ok=True)
        os.makedirs(self.temp_pcm_dir, exist_ok=True)

        sqlite_path = db_path or os.path.join(output_dir, "dataset.db")
        self.db = DatasetDatabase(sqlite_path)

    def parse_transcript_file(self, transcript_path: str) -> List[Dict[str, Any]]:
        """Auto-detects format from extension and parses transcript."""
        ext = os.path.splitext(transcript_path)[1].lower()
        if ext == ".json":
            return parse_json_transcript(transcript_path)
        elif ext == ".csv" or ext == ".tsv" or ext == ".txt":
            return parse_csv_transcript(transcript_path)
        elif ext == ".srt":
            return parse_srt_transcript(transcript_path)
        else:
            # Try JSON first, then CSV, then SRT
            for parser in [parse_json_transcript, parse_csv_transcript, parse_srt_transcript]:
                try:
                    res = parser(transcript_path)
                    if res:
                        return res
                except Exception:
                    pass
            raise ValueError(f"Unsupported transcript format: {transcript_path}")

    def merge_short_sentences(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merges short sentences (< min_duration) with the next sentence if:
        - The gap/silence between them is <= merge_silence_threshold
        - Total combined duration <= max_duration
        """
        if not self.auto_merge_short or len(items) <= 1:
            return items

        merged: List[Dict[str, Any]] = []
        i = 0
        n = len(items)

        while i < n:
            curr = items[i].copy()
            # Try merging with subsequent sentences as long as curr is short
            while i + 1 < n and curr["duration"] < self.min_duration:
                nxt = items[i + 1]
                gap = nxt["start"] - curr["end"]
                combined_duration = nxt["end"] - curr["start"]

                if gap <= self.merge_silence_threshold and combined_duration <= self.max_duration:
                    logger.debug(
                        f"Auto-merging short sample ({curr['duration']:.2f}s) with next ({nxt['duration']:.2f}s): "
                        f"'{curr['text']}' + '{nxt['text']}'"
                    )
                    curr["end"] = nxt["end"]
                    curr["duration"] = round(curr["end"] - curr["start"], 3)
                    curr["text"] = f"{curr['text']} {nxt['text']}".strip()
                    i += 1
                else:
                    break

            merged.append(curr)
            i += 1

        # Re-index
        for idx, it in enumerate(merged):
            it["index"] = idx + 1

        return merged

    def process_audio_file(
        self,
        audio_path: str,
        transcript_path: str,
        progress_callback: Optional[Callable[[int, int, float, float, str, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Processes a single audio file and its matching transcript.
        Sequential ID continues from database's max index.
        """
        ok, msg = check_ffmpeg()
        if not ok:
            raise RuntimeError(msg)

        logger.info(f"Starting processing: audio='{audio_path}', transcript='{transcript_path}'")
        raw_items = self.parse_transcript_file(transcript_path)
        logger.info(f"Parsed {len(raw_items)} transcript segments.")

        items = self.merge_short_sentences(raw_items)
        logger.info(f"After short-sentence merge: {len(items)} segments.")

        # Step 1: Decode source audio ONCE to PCM s16le mono at self.sample_rate
        audio_name = os.path.splitext(os.path.basename(audio_path))[0]
        pcm_path = os.path.join(self.temp_pcm_dir, f"{audio_name}_{self.sample_rate}hz.pcm")

        # Decode if not already existing or older than audio file
        if not os.path.exists(pcm_path) or os.path.getmtime(pcm_path) < os.path.getmtime(audio_path):
            pcm_info = decode_source_to_pcm(audio_path, pcm_path, sample_rate=self.sample_rate)
        else:
            pcm_size = os.path.getsize(pcm_path)
            total_samples = pcm_size // 2
            pcm_info = {
                "pcm_path": pcm_path,
                "sample_rate": self.sample_rate,
                "total_samples": total_samples,
                "total_duration": total_samples / self.sample_rate,
            }

        total_audio_duration = pcm_info["total_duration"]
        total_items = len(items)
        start_time_all = time.time()

        # Resume state: find current maximum ID in database
        current_max_id = self.db.get_max_sample_index()

        accepted_count = 0
        rejected_count = 0

        with open(pcm_path, "rb") as pcm_file_handle:
            for idx, item in enumerate(items):
                if is_cancelled and is_cancelled():
                    logger.warning("Dataset building cancelled by user.")
                    break

                raw_start = item["start"]
                raw_end = item["end"]
                text = item["text"]

                # Check if already processed (resume capability)
                existing = self.db.find_processed_sample(os.path.basename(audio_path), raw_start, raw_end)
                if existing:
                    # Already processed earlier
                    if existing["status"] == "accepted":
                        accepted_count += 1
                    else:
                        rejected_count += 1

                    # Send progress
                    if progress_callback:
                        elapsed = time.time() - start_time_all
                        pct = round((idx + 1) / total_items * 100.0, 1)
                        progress_callback(
                            idx + 1, total_items, pct, 0.0,
                            os.path.basename(audio_path),
                            f"Resumed existing: {existing['wav_filename']}"
                        )
                    continue

                # New sample index
                current_max_id += 1
                sample_code = f"{current_max_id:06d}"
                wav_filename = f"{sample_code}.wav"
                wav_path = os.path.join(self.wavs_dir, wav_filename)

                # Overlap context
                prev_end = items[idx - 1]["end"] if idx > 0 else None
                next_start = items[idx + 1]["start"] if idx + 1 < total_items else None

                # VAD silence boundary refinement if enabled
                cut_start = raw_start
                cut_end = raw_end

                if self.refine_vad:
                    cut_start = refine_boundary_with_silence(
                        pcm_file_handle, raw_start, sample_rate=self.sample_rate,
                        search_window_sec=0.30, is_start=True, total_duration=total_audio_duration
                    )
                    cut_end = refine_boundary_with_silence(
                        pcm_file_handle, raw_end, sample_rate=self.sample_rate,
                        search_window_sec=0.30, is_start=False, total_duration=total_audio_duration
                    )

                # Add padding and clamp overlap
                padded_start, padded_end = calculate_slice_bounds(
                    start_sec=cut_start,
                    end_sec=cut_end,
                    padding_before=self.padding_before,
                    padding_after=self.padding_after,
                    prev_end_sec=prev_end,
                    next_start_sec=next_start,
                    total_audio_duration=total_audio_duration,
                )

                slice_duration = round(padded_end - padded_start, 3)

                # Rejection checks
                rejection_reason = ""
                status = "accepted"

                if not text or len(text.strip()) == 0:
                    rejection_reason = "Empty transcript text"
                    status = "rejected"
                elif slice_duration < 0.5:
                    rejection_reason = f"Audio duration too short ({slice_duration:.2f}s < 0.5s)"
                    status = "rejected"
                elif padded_start >= total_audio_duration:
                    rejection_reason = f"Start timestamp ({padded_start:.2f}s) exceeds total audio length ({total_audio_duration:.2f}s)"
                    status = "rejected"

                # If not rejected upfront, cut slice from PCM
                if status == "accepted":
                    try:
                        cut_pcm_slice(
                            pcm_file_path=pcm_path,
                            output_wav_path=wav_path,
                            start_sec=padded_start,
                            end_sec=padded_end,
                            sample_rate=self.sample_rate,
                        )

                        # Optional normalization
                        if self.peak_norm or self.loudness_norm:
                            normalize_audio_file(
                                wav_path=wav_path,
                                peak_norm=self.peak_norm,
                                loudness_norm=self.loudness_norm,
                                target_lufs=self.target_lufs,
                            )

                        # Quality analysis
                        metrics = analyze_wav_file(wav_path)
                        if not metrics["valid"]:
                            status = "rejected"
                            rejection_reason = f"Audio quality error: {metrics.get('error')}"
                        else:
                            # Check for warning condition: > max_duration (do NOT reject, but log warning)
                            if slice_duration > self.max_duration:
                                logger.warning(
                                    f"Sample {wav_filename} duration {slice_duration:.2f}s exceeds max duration {self.max_duration:.2f}s"
                                )
                    except Exception as e:
                        status = "rejected"
                        rejection_reason = f"Cutting error: {str(e)}"
                        metrics = {
                            "quality_score": 0.0, "rms_db": -99.0,
                            "peak_db": -99.0, "silence_ratio": 1.0, "clipping_count": 0
                        }
                else:
                    metrics = {
                        "quality_score": 0.0, "rms_db": -99.0,
                        "peak_db": -99.0, "silence_ratio": 1.0, "clipping_count": 0
                    }

                # Save record to SQLite
                record = {
                    "sample_index": current_max_id,
                    "wav_filename": wav_filename,
                    "text": text,
                    "source_audio": os.path.basename(audio_path),
                    "start_time": raw_start,
                    "end_time": raw_end,
                    "actual_start": padded_start,
                    "actual_end": padded_end,
                    "duration": slice_duration,
                    "status": status,
                    "rejection_reason": rejection_reason,
                    "quality_score": metrics.get("quality_score", 100.0),
                    "rms_db": metrics.get("rms_db", 0.0),
                    "peak_db": metrics.get("peak_db", 0.0),
                    "silence_ratio": metrics.get("silence_ratio", 0.0),
                    "clipping_count": metrics.get("clipping_count", 0),
                }
                self.db.upsert_sample(record)

                if status == "accepted":
                    accepted_count += 1
                else:
                    rejected_count += 1
                    log_rejected_sample(
                        filename=wav_filename,
                        text=text,
                        reason=rejection_reason,
                        start=padded_start,
                        end=padded_end,
                        duration=slice_duration,
                    )

                # Progress callback
                if progress_callback:
                    elapsed = time.time() - start_time_all
                    processed = idx + 1
                    rate = processed / elapsed if elapsed > 0 else 1.0
                    remaining_items = total_items - processed
                    eta_sec = remaining_items / rate if rate > 0 else 0.0
                    pct = round(processed / total_items * 100.0, 1)
                    progress_callback(
                        processed, total_items, pct, eta_sec,
                        os.path.basename(audio_path),
                        f"Processing sample {wav_filename} ({status})"
                    )

        # Build output metadata and report
        report = self.generate_reports()
        return report

    def generate_reports(self) -> Dict[str, Any]:
        """
        Builds metadata.csv, metadata.json, rejected.csv, and dataset_report.json
        from the current SQLite database state.
        """
        all_samples = self.db.get_all_samples()
        accepted = [s for s in all_samples if s["status"] == "accepted"]
        rejected = [s for s in all_samples if s["status"] == "rejected"]

        # 1. metadata.csv (Format: 000001.wav|Ta mỗi ngày nhận được một hệ thống mới.)
        metadata_csv_path = os.path.join(self.output_dir, "metadata.csv")
        with open(metadata_csv_path, "w", encoding="utf-8", newline="") as f:
            for s in accepted:
                f.write(f"{s['wav_filename']}|{s['text']}\n")

        # 2. metadata.json
        metadata_json_path = os.path.join(self.output_dir, "metadata.json")
        with open(metadata_json_path, "w", encoding="utf-8") as f:
            json.dump(accepted, f, ensure_ascii=False, indent=2)

        # 3. rejected.csv
        rejected_csv_path = os.path.join(self.output_dir, "rejected.csv")
        with open(rejected_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["filename", "text", "reason", "start", "end", "duration"])
            for r in rejected:
                writer.writerow([
                    r["wav_filename"],
                    r["text"],
                    r["rejection_reason"],
                    f"{r['actual_start']:.3f}",
                    f"{r['actual_end']:.3f}",
                    f"{r['duration']:.3f}",
                ])

        # 4. dataset_report.json
        durations = [s["duration"] for s in accepted]
        total_duration_sec = sum(durations)
        avg_duration = total_duration_sec / len(durations) if durations else 0.0
        min_dur = min(durations) if durations else 0.0
        max_dur = max(durations) if durations else 0.0

        # Duration bins
        bins = {
            "0-2 sec": 0,
            "2-4 sec": 0,
            "4-6 sec": 0,
            "6-8 sec": 0,
            "8-10 sec": 0,
            "10-12 sec": 0,
            ">12 sec": 0,
        }
        for d in durations:
            if d < 2.0:
                bins["0-2 sec"] += 1
            elif d < 4.0:
                bins["2-4 sec"] += 1
            elif d < 6.0:
                bins["4-6 sec"] += 1
            elif d < 8.0:
                bins["6-8 sec"] += 1
            elif d < 10.0:
                bins["8-10 sec"] += 1
            elif d <= 12.0:
                bins["10-12 sec"] += 1
            else:
                bins[">12 sec"] += 1

        # Format total duration as Xh Ym Zs
        hours = int(total_duration_sec // 3600)
        minutes = int((total_duration_sec % 3600) // 60)
        secs = int(total_duration_sec % 60)
        duration_formatted = f"{hours}h {minutes}m {secs}s" if hours > 0 else f"{minutes}m {secs}s"

        report = {
            "summary": {
                "total_samples": len(all_samples),
                "accepted_samples": len(accepted),
                "rejected_samples": len(rejected),
                "total_duration_seconds": round(total_duration_sec, 2),
                "total_duration_formatted": duration_formatted,
                "average_duration_seconds": round(avg_duration, 2),
                "min_duration_seconds": round(min_dur, 2),
                "max_duration_seconds": round(max_dur, 2),
            },
            "duration_distribution": bins,
            "parameters": {
                "sample_rate": self.sample_rate,
                "padding_before": self.padding_before,
                "padding_after": self.padding_after,
                "min_duration": self.min_duration,
                "max_duration": self.max_duration,
                "auto_merge_short": self.auto_merge_short,
                "refine_vad": self.refine_vad,
                "peak_norm": self.peak_norm,
                "loudness_norm": self.loudness_norm,
            },
            "generated_at": datetime.now().isoformat(),
        }

        report_json_path = os.path.join(self.output_dir, "dataset_report.json")
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return report

    def regenerate_single_sample(
        self,
        wav_filename: str,
        new_text: str,
        new_start: float,
        new_end: float,
    ) -> Dict[str, Any]:
        """
        Allows editing text, start, and end time in Preview, and re-cuts that exact sample.
        """
        sample = self.db.get_sample_by_filename(wav_filename)
        if not sample:
            raise ValueError(f"Sample not found: {wav_filename}")

        source_audio_name = sample.get("source_audio", "")
        # Find pcm file
        pcm_candidates = [
            os.path.join(self.temp_pcm_dir, f"{os.path.splitext(source_audio_name)[0]}_{self.sample_rate}hz.pcm"),
        ]
        # Also check any pcm in temp_pcm_dir
        pcm_path = None
        for cand in pcm_candidates:
            if os.path.exists(cand):
                pcm_path = cand
                break

        if not pcm_path and os.path.exists(self.temp_pcm_dir):
            files = [f for f in os.listdir(self.temp_pcm_dir) if f.endswith(".pcm")]
            if files:
                pcm_path = os.path.join(self.temp_pcm_dir, files[0])

        if not pcm_path:
            raise FileNotFoundError("PCM file not found for regeneration. Source audio must be available.")

        wav_path = os.path.join(self.wavs_dir, wav_filename)
        new_duration = round(new_end - new_start, 3)

        # Cut new slice
        cut_pcm_slice(
            pcm_file_path=pcm_path,
            output_wav_path=wav_path,
            start_sec=new_start,
            end_sec=new_end,
            sample_rate=self.sample_rate,
        )

        if self.peak_norm or self.loudness_norm:
            normalize_audio_file(
                wav_path=wav_path,
                peak_norm=self.peak_norm,
                loudness_norm=self.loudness_norm,
                target_lufs=self.target_lufs,
            )

        metrics = analyze_wav_file(wav_path)
        status = "accepted" if metrics["valid"] else "rejected"
        rejection_reason = "" if metrics["valid"] else metrics.get("error", "Invalid audio")

        sample["text"] = new_text.strip()
        sample["actual_start"] = new_start
        sample["actual_end"] = new_end
        sample["duration"] = new_duration
        sample["status"] = status
        sample["rejection_reason"] = rejection_reason
        sample["quality_score"] = metrics.get("quality_score", 100.0)
        sample["rms_db"] = metrics.get("rms_db", 0.0)
        sample["peak_db"] = metrics.get("peak_db", 0.0)
        sample["silence_ratio"] = metrics.get("silence_ratio", 0.0)
        sample["clipping_count"] = metrics.get("clipping_count", 0)

        self.db.upsert_sample(sample)
        self.generate_reports()

        return sample
