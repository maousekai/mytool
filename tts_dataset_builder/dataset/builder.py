"""
Dataset Builder Engine for Vietnamese TTS Dataset Builder.

This module owns deterministic source tracking, transcript validation, PCM
caching, resume/rebuild behavior, cutting, quality analysis and metadata export.
"""

import csv
import hashlib
import json
import os
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..audio.analyzer import analyze_wav_file, normalize_audio_file
from ..audio.cutter import calculate_slice_bounds, cut_pcm_slice
from ..audio.decoder import decode_source_to_pcm
from ..audio.vad import refine_boundary_with_silence
from ..transcript.csv_parser import parse_csv_transcript
from ..transcript.json_parser import parse_json_transcript
from ..transcript.srt_parser import parse_srt_transcript
from ..utils.ffmpeg import check_ffmpeg
from ..utils.logger import get_logger, log_rejected_sample
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
        self.output_dir = os.path.abspath(output_dir)
        self.wavs_dir = os.path.join(self.output_dir, "wavs")
        self.temp_pcm_dir = os.path.join(self.output_dir, "_temp_pcm")
        self.sample_rate = int(sample_rate)
        self.padding_before = float(padding_before)
        self.padding_after = float(padding_after)
        self.refine_vad = bool(refine_vad)
        self.min_duration = float(min_duration)
        self.max_duration = float(max_duration)
        self.auto_merge_short = bool(auto_merge_short)
        self.merge_silence_threshold = float(merge_silence_threshold)
        self.peak_norm = bool(peak_norm)
        self.loudness_norm = bool(loudness_norm)
        self.target_lufs = float(target_lufs)

        self._validate_config()
        os.makedirs(self.wavs_dir, exist_ok=True)
        os.makedirs(self.temp_pcm_dir, exist_ok=True)

        sqlite_path = db_path or os.path.join(self.output_dir, "dataset.db")
        self.db = DatasetDatabase(sqlite_path)

    def _validate_config(self) -> None:
        if self.sample_rate not in (24000, 44100, 48000):
            raise ValueError("sample_rate must be one of 24000, 44100, 48000 Hz")
        if self.padding_before < 0 or self.padding_after < 0:
            raise ValueError("Padding cannot be negative")
        if self.min_duration <= 0 or self.max_duration <= 0:
            raise ValueError("Duration bounds must be positive")
        if self.min_duration >= self.max_duration:
            raise ValueError("min_duration must be smaller than max_duration")
        if self.merge_silence_threshold < 0:
            raise ValueError("merge_silence_threshold cannot be negative")
        if self.peak_norm and self.loudness_norm:
            raise ValueError("Choose either peak normalization or loudness normalization, not both")

    @staticmethod
    def _hash_file(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _source_key(audio_path: str) -> str:
        """Cheap but stable fingerprint: basename + size + first/last 1 MiB."""
        size = os.path.getsize(audio_path)
        h = hashlib.sha256()
        h.update(os.path.basename(audio_path).encode("utf-8", errors="replace"))
        h.update(str(size).encode("ascii"))
        with open(audio_path, "rb") as f:
            h.update(f.read(1024 * 1024))
            if size > 1024 * 1024:
                f.seek(max(0, size - 1024 * 1024))
                h.update(f.read(1024 * 1024))
        return h.hexdigest()

    def _build_signature(self, transcript_path: str) -> str:
        payload = {
            "transcript_sha256": self._hash_file(transcript_path),
            "sample_rate": self.sample_rate,
            "padding_before": self.padding_before,
            "padding_after": self.padding_after,
            "refine_vad": self.refine_vad,
            "min_duration": self.min_duration,
            "max_duration": self.max_duration,
            "auto_merge_short": self.auto_merge_short,
            "merge_silence_threshold": self.merge_silence_threshold,
            "peak_norm": self.peak_norm,
            "loudness_norm": self.loudness_norm,
            "target_lufs": self.target_lufs,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    def parse_transcript_file(self, transcript_path: str) -> List[Dict[str, Any]]:
        ext = os.path.splitext(transcript_path)[1].lower()
        if ext == ".json":
            items = parse_json_transcript(transcript_path)
        elif ext in (".csv", ".tsv", ".txt"):
            items = parse_csv_transcript(transcript_path)
        elif ext == ".srt":
            items = parse_srt_transcript(transcript_path)
        else:
            items = []
            last_error: Optional[Exception] = None
            for parser in (parse_json_transcript, parse_csv_transcript, parse_srt_transcript):
                try:
                    items = parser(transcript_path)
                    if items:
                        break
                except Exception as exc:
                    last_error = exc
            if not items:
                raise ValueError(f"Unsupported/invalid transcript: {transcript_path}: {last_error or 'no segments'}")

        valid: List[Dict[str, Any]] = []
        invalid_count = 0
        for item in items:
            try:
                start = float(item["start"])
                end = float(item["end"])
                text = str(item.get("text", "")).strip()
            except (TypeError, ValueError, KeyError):
                invalid_count += 1
                continue
            if start < 0 or end <= start:
                invalid_count += 1
                continue
            valid.append({
                **item,
                "start": round(start, 3),
                "end": round(end, 3),
                "duration": round(end - start, 3),
                "text": text,
            })

        valid.sort(key=lambda x: (x["start"], x["end"]))
        for idx, item in enumerate(valid, 1):
            item["index"] = idx

        if invalid_count:
            logger.warning("Ignored %d invalid transcript segment(s) from %s", invalid_count, transcript_path)
        if not valid:
            raise ValueError("Transcript contains no valid segments with start < end")
        return valid

    def merge_short_sentences(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.auto_merge_short or len(items) <= 1:
            return items

        merged: List[Dict[str, Any]] = []
        i = 0
        while i < len(items):
            curr = items[i].copy()
            while i + 1 < len(items) and curr["duration"] < self.min_duration:
                nxt = items[i + 1]
                gap = nxt["start"] - curr["end"]
                combined_duration = nxt["end"] - curr["start"]
                # Negative gaps mean transcript segments overlap. Never auto-merge them.
                if 0 <= gap <= self.merge_silence_threshold and combined_duration <= self.max_duration:
                    curr["end"] = nxt["end"]
                    curr["duration"] = round(curr["end"] - curr["start"], 3)
                    curr["text"] = f"{curr['text']} {nxt['text']}".strip()
                    i += 1
                else:
                    break
            merged.append(curr)
            i += 1

        for idx, item in enumerate(merged, 1):
            item["index"] = idx
        return merged

    def _remove_wavs(self, filenames: List[str]) -> None:
        for filename in filenames:
            try:
                path = os.path.join(self.wavs_dir, os.path.basename(filename))
                if os.path.exists(path):
                    os.remove(path)
            except OSError as exc:
                logger.warning("Could not remove stale WAV %s: %s", filename, exc)

    def process_audio_file(
        self,
        audio_path: str,
        transcript_path: str,
        progress_callback: Optional[Callable[[int, int, float, float, str, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        ok, msg = check_ffmpeg()
        if not ok:
            raise RuntimeError(msg)
        if not os.path.isfile(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        if not os.path.isfile(transcript_path):
            raise FileNotFoundError(f"Transcript file not found: {transcript_path}")

        source_audio = os.path.basename(audio_path)
        source_key = self._source_key(audio_path)
        build_signature = self._build_signature(transcript_path)
        pcm_path = os.path.join(self.temp_pcm_dir, f"{source_key[:20]}_{self.sample_rate}hz.pcm")

        # A file with the same visible name but different content replaces the old source.
        for old_state in self.db.get_source_states_by_audio(source_audio):
            old_key = old_state.get("source_key", "")
            if old_key and old_key != source_key:
                self._remove_wavs(self.db.delete_samples_for_source(old_key, delete_source_state=True))
                old_pcm = old_state.get("source_pcm")
                if old_pcm and os.path.exists(old_pcm):
                    try:
                        os.remove(old_pcm)
                    except OSError:
                        pass

        previous_state = self.db.get_source_state(source_key)
        if previous_state and previous_state.get("build_signature") != build_signature:
            logger.info("Build parameters/transcript changed for %s; rebuilding that source.", source_audio)
            self._remove_wavs(self.db.delete_samples_for_source(source_key))

        raw_items = self.parse_transcript_file(transcript_path)
        items = self.merge_short_sentences(raw_items)
        logger.info("Processing %s: %d -> %d segment(s)", source_audio, len(raw_items), len(items))

        if not os.path.exists(pcm_path):
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

        total_audio_duration = float(pcm_info["total_duration"])
        if total_audio_duration <= 0:
            raise RuntimeError("Decoded PCM is empty")

        # Migrate old rows only when they clearly refer to this same named source.
        self.db.adopt_legacy_source(source_audio, source_key, pcm_path, self.sample_rate)
        self.db.set_source_state(
            source_key, source_audio, pcm_path, self.sample_rate, build_signature
        )

        total_items = len(items)
        start_time_all = time.time()
        current_max_id = self.db.get_max_sample_index()

        with open(pcm_path, "rb") as pcm_handle:
            for idx, item in enumerate(items):
                if is_cancelled and is_cancelled():
                    logger.warning("Dataset building cancelled by user")
                    break

                raw_start = float(item["start"])
                raw_end = float(item["end"])
                text = str(item.get("text", "")).strip()

                existing = self.db.find_processed_sample(
                    source_key, raw_start, raw_end, legacy_source_audio=source_audio
                )
                existing_wav = (
                    os.path.join(self.wavs_dir, existing["wav_filename"])
                    if existing and existing.get("wav_filename") else None
                )
                if existing and (
                    existing.get("status") == "rejected"
                    or (existing.get("status") == "accepted" and existing_wav and os.path.exists(existing_wav))
                ):
                    if progress_callback:
                        pct = round((idx + 1) / total_items * 100.0, 1)
                        progress_callback(idx + 1, total_items, pct, 0.0, source_audio, f"Resumed existing: {existing['wav_filename']}")
                    continue

                if existing:
                    sample_index = int(existing["sample_index"])
                    wav_filename = str(existing["wav_filename"])
                else:
                    current_max_id += 1
                    sample_index = current_max_id
                    wav_filename = f"{sample_index:06d}.wav"
                wav_path = os.path.join(self.wavs_dir, wav_filename)

                prev_end = float(items[idx - 1]["end"]) if idx > 0 else None
                next_start = float(items[idx + 1]["start"]) if idx + 1 < total_items else None

                cut_start, cut_end = raw_start, raw_end
                if self.refine_vad:
                    cut_start = refine_boundary_with_silence(
                        pcm_handle, raw_start, sample_rate=self.sample_rate,
                        search_window_sec=0.30, is_start=True, total_duration=total_audio_duration,
                    )
                    cut_end = refine_boundary_with_silence(
                        pcm_handle, raw_end, sample_rate=self.sample_rate,
                        search_window_sec=0.30, is_start=False, total_duration=total_audio_duration,
                    )
                    if cut_end <= cut_start:
                        cut_start, cut_end = raw_start, raw_end

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

                status = "accepted"
                rejection_reason = ""
                metrics: Dict[str, Any] = {
                    "quality_score": 0.0, "rms_db": -99.0, "peak_db": -99.0,
                    "silence_ratio": 1.0, "clipping_count": 0,
                }

                if not text:
                    status, rejection_reason = "rejected", "Empty transcript text"
                elif raw_end > total_audio_duration + 0.05:
                    status, rejection_reason = "rejected", (
                        f"End timestamp ({raw_end:.2f}s) exceeds audio length ({total_audio_duration:.2f}s)"
                    )
                elif slice_duration < 0.5:
                    status, rejection_reason = "rejected", f"Audio duration too short ({slice_duration:.2f}s < 0.5s)"

                if status == "accepted":
                    try:
                        cut_pcm_slice(
                            pcm_file_path=pcm_path,
                            output_wav_path=wav_path,
                            start_sec=padded_start,
                            end_sec=padded_end,
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
                        if not metrics.get("valid"):
                            status = "rejected"
                            rejection_reason = f"Audio quality error: {metrics.get('error', 'unknown')}"
                            try:
                                os.remove(wav_path)
                            except OSError:
                                pass
                        elif slice_duration > self.max_duration:
                            logger.warning("Sample %s is %.2fs (> %.2fs)", wav_filename, slice_duration, self.max_duration)
                    except Exception as exc:
                        status = "rejected"
                        rejection_reason = f"Cutting error: {exc}"
                        try:
                            if os.path.exists(wav_path):
                                os.remove(wav_path)
                        except OSError:
                            pass

                record = {
                    "sample_index": sample_index,
                    "wav_filename": wav_filename,
                    "text": text,
                    "source_audio": source_audio,
                    "source_key": source_key,
                    "source_pcm": pcm_path,
                    "sample_rate": self.sample_rate,
                    "start_time": raw_start,
                    "end_time": raw_end,
                    "actual_start": padded_start,
                    "actual_end": padded_end,
                    "duration": slice_duration,
                    "status": status,
                    "rejection_reason": rejection_reason,
                    "quality_score": metrics.get("quality_score", 0.0),
                    "rms_db": metrics.get("rms_db", -99.0),
                    "peak_db": metrics.get("peak_db", -99.0),
                    "silence_ratio": metrics.get("silence_ratio", 1.0),
                    "clipping_count": metrics.get("clipping_count", 0),
                }
                self.db.upsert_sample(record)

                if status == "rejected":
                    log_rejected_sample(
                        filename=wav_filename, text=text, reason=rejection_reason,
                        start=padded_start, end=padded_end, duration=slice_duration,
                    )

                if progress_callback:
                    elapsed = time.time() - start_time_all
                    processed = idx + 1
                    rate = processed / elapsed if elapsed > 0 else 1.0
                    eta_sec = (total_items - processed) / rate if rate > 0 else 0.0
                    pct = round(processed / total_items * 100.0, 1)
                    progress_callback(processed, total_items, pct, eta_sec, source_audio, f"Processing sample {wav_filename} ({status})")

        return self.generate_reports()

    def generate_reports(self) -> Dict[str, Any]:
        all_samples = self.db.get_all_samples()
        accepted = [s for s in all_samples if s["status"] == "accepted"]
        rejected = [s for s in all_samples if s["status"] == "rejected"]

        with open(os.path.join(self.output_dir, "metadata.csv"), "w", encoding="utf-8", newline="") as f:
            for s in accepted:
                f.write(f"{s['wav_filename']}|{s['text']}\n")

        with open(os.path.join(self.output_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(accepted, f, ensure_ascii=False, indent=2)

        with open(os.path.join(self.output_dir, "rejected.csv"), "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["filename", "text", "reason", "start", "end", "duration"])
            for r in rejected:
                writer.writerow([
                    r["wav_filename"], r["text"], r["rejection_reason"],
                    f"{float(r['actual_start']):.3f}", f"{float(r['actual_end']):.3f}",
                    f"{float(r['duration']):.3f}",
                ])

        durations = [float(s["duration"]) for s in accepted]
        total_duration = sum(durations)
        bins = {"0-2 sec": 0, "2-4 sec": 0, "4-6 sec": 0, "6-8 sec": 0, "8-10 sec": 0, "10-12 sec": 0, ">12 sec": 0}
        for d in durations:
            if d < 2: bins["0-2 sec"] += 1
            elif d < 4: bins["2-4 sec"] += 1
            elif d < 6: bins["4-6 sec"] += 1
            elif d < 8: bins["6-8 sec"] += 1
            elif d < 10: bins["8-10 sec"] += 1
            elif d <= 12: bins["10-12 sec"] += 1
            else: bins[">12 sec"] += 1

        hours = int(total_duration // 3600)
        minutes = int((total_duration % 3600) // 60)
        seconds = int(total_duration % 60)
        duration_text = f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s"

        report = {
            "summary": {
                "total_samples": len(all_samples),
                "accepted_samples": len(accepted),
                "rejected_samples": len(rejected),
                "total_duration_seconds": round(total_duration, 2),
                "total_duration_formatted": duration_text,
                "average_duration_seconds": round(total_duration / len(durations), 2) if durations else 0.0,
                "min_duration_seconds": round(min(durations), 2) if durations else 0.0,
                "max_duration_seconds": round(max(durations), 2) if durations else 0.0,
            },
            "duration_distribution": bins,
            "parameters": {
                "sample_rate": self.sample_rate,
                "padding_before": self.padding_before,
                "padding_after": self.padding_after,
                "min_duration": self.min_duration,
                "max_duration": self.max_duration,
                "auto_merge_short": self.auto_merge_short,
                "merge_silence_threshold": self.merge_silence_threshold,
                "refine_vad": self.refine_vad,
                "peak_norm": self.peak_norm,
                "loudness_norm": self.loudness_norm,
                "target_lufs": self.target_lufs,
            },
            "generated_at": datetime.now().isoformat(),
        }
        with open(os.path.join(self.output_dir, "dataset_report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        return report

    def regenerate_single_sample(
        self,
        wav_filename: str,
        new_text: str,
        new_start: float,
        new_end: float,
    ) -> Dict[str, Any]:
        sample = self.db.get_sample_by_filename(os.path.basename(wav_filename))
        if not sample:
            raise ValueError(f"Sample not found: {wav_filename}")

        start = float(new_start)
        end = float(new_end)
        if start < 0 or end <= start:
            raise ValueError("Invalid timestamps: require 0 <= start < end")
        text = str(new_text).strip()
        if not text:
            raise ValueError("Transcript text cannot be empty")

        pcm_path = str(sample.get("source_pcm") or "")
        sample_rate = int(sample.get("sample_rate") or self.sample_rate)
        if not pcm_path or not os.path.isfile(pcm_path):
            raise FileNotFoundError(
                "Exact PCM source for this sample is missing. Rebuild the source audio before regenerating; the tool will not guess another PCM file."
            )

        total_duration = (os.path.getsize(pcm_path) // 2) / float(sample_rate)
        if end > total_duration + 0.001:
            raise ValueError(f"End timestamp {end:.3f}s exceeds source audio length {total_duration:.3f}s")

        wav_path = os.path.join(self.wavs_dir, os.path.basename(wav_filename))
        cut_pcm_slice(
            pcm_file_path=pcm_path,
            output_wav_path=wav_path,
            start_sec=start,
            end_sec=end,
            sample_rate=sample_rate,
        )

        # Preserve the normalization mode recorded by this builder instance. In web
        # regeneration the generated WAV is already PCM-safe, so no implicit
        # normalization is introduced.
        if self.peak_norm or self.loudness_norm:
            normalize_audio_file(
                wav_path=wav_path, peak_norm=self.peak_norm,
                loudness_norm=self.loudness_norm, target_lufs=self.target_lufs,
            )

        metrics = analyze_wav_file(wav_path)
        if not metrics.get("valid"):
            raise RuntimeError(f"Regenerated WAV is invalid: {metrics.get('error', 'unknown')}")

        sample.update({
            "text": text,
            "actual_start": start,
            "actual_end": end,
            "duration": round(end - start, 3),
            "sample_rate": sample_rate,
            "status": "accepted",
            "rejection_reason": "",
            "quality_score": metrics.get("quality_score", 0.0),
            "rms_db": metrics.get("rms_db", -99.0),
            "peak_db": metrics.get("peak_db", -99.0),
            "silence_ratio": metrics.get("silence_ratio", 1.0),
            "clipping_count": metrics.get("clipping_count", 0),
        })
        self.db.upsert_sample(sample)
        self.generate_reports()
        return sample
