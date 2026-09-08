"""
CLI Bridge between Express web server and Python TTS Dataset Builder.
Emits structured JSON lines to stdout for real-time progress tracking.
"""

import sys
import os
import json
import argparse

# Add tts_dataset_builder to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_dataset_builder.dataset.builder import DatasetBuilder
from tts_dataset_builder.dataset.validator import DatasetValidator
from tts_dataset_builder.dataset.exporter import export_dataset_to_zip
from tts_dataset_builder.utils.ffmpeg import check_ffmpeg
from tts_dataset_builder.utils.logger import setup_logger, get_logger

setup_logger()
logger = get_logger()


def emit_progress(curr, total, pct, eta, cur_file, msg):
    event = {
        "type": "progress",
        "current": curr,
        "total": total,
        "percentage": pct,
        "eta_seconds": round(eta, 1),
        "current_file": cur_file,
        "message": msg,
    }
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


def cmd_build(args):
    builder = DatasetBuilder(
        output_dir=args.output_dir,
        sample_rate=args.sample_rate,
        padding_before=args.padding_before,
        padding_after=args.padding_after,
        refine_vad=args.refine_vad,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        auto_merge_short=args.auto_merge_short,
        merge_silence_threshold=args.merge_silence_threshold,
        peak_norm=args.peak_norm,
        loudness_norm=args.loudness_norm,
        target_lufs=args.target_lufs,
    )

    audio_files = args.audio_files.split(",")
    transcripts = args.transcript_files.split(",")

    for idx, audio_p in enumerate(audio_files):
        audio_p = audio_p.strip()
        if not audio_p or not os.path.exists(audio_p):
            continue
        # Use corresponding transcript or first one
        tr_p = transcripts[idx].strip() if idx < len(transcripts) else transcripts[0].strip()
        if not os.path.exists(tr_p):
            continue

        emit_progress(0, 100, 0.0, 0.0, os.path.basename(audio_p), f"Bắt đầu giải mã PCM {os.path.basename(audio_p)}")
        builder.process_audio_file(audio_p, tr_p, progress_callback=emit_progress)

    final_report = builder.generate_reports()
    result_event = {"type": "completed", "report": final_report}
    sys.stdout.write(json.dumps(result_event) + "\n")
    sys.stdout.flush()


def cmd_regenerate(args):
    builder = DatasetBuilder(output_dir=args.output_dir)
    updated = builder.regenerate_single_sample(
        wav_filename=args.filename,
        new_text=args.text,
        new_start=args.start,
        new_end=args.end,
    )
    sys.stdout.write(json.dumps({"type": "regenerated", "sample": updated}) + "\n")
    sys.stdout.flush()


def cmd_validate(args):
    validator = DatasetValidator(
        dataset_dir=args.output_dir,
        expected_sample_rate=args.sample_rate,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
    )
    result = validator.validate_dataset()
    sys.stdout.write(json.dumps({"type": "validated", "result": result}) + "\n")
    sys.stdout.flush()


def cmd_export(args):
    zip_path = export_dataset_to_zip(args.output_dir)
    sys.stdout.write(json.dumps({"type": "exported", "zip_path": zip_path}) + "\n")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="TTS Dataset Builder CLI Bridge")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # Build subparser
    build_p = subparsers.add_parser("build")
    build_p.add_argument("--output-dir", default="output_dataset")
    build_p.add_argument("--audio-files", required=True)
    build_p.add_argument("--transcript-files", required=True)
    build_p.add_argument("--sample-rate", type=int, default=24000)
    build_p.add_argument("--padding-before", type=float, default=0.15)
    build_p.add_argument("--padding-after", type=float, default=0.20)
    build_p.add_argument("--refine-vad", action="store_true")
    build_p.add_argument("--min-duration", type=float, default=2.0)
    build_p.add_argument("--max-duration", type=float, default=12.0)
    build_p.add_argument("--auto-merge-short", action="store_true")
    build_p.add_argument("--merge-silence-threshold", type=float, default=0.80)
    build_p.add_argument("--peak-norm", action="store_true")
    build_p.add_argument("--loudness-norm", action="store_true")
    build_p.add_argument("--target-lufs", type=float, default=-20.0)

    # Regenerate subparser
    regen_p = subparsers.add_parser("regenerate")
    regen_p.add_argument("--output-dir", default="output_dataset")
    regen_p.add_argument("--filename", required=True)
    regen_p.add_argument("--text", required=True)
    regen_p.add_argument("--start", type=float, required=True)
    regen_p.add_argument("--end", type=float, required=True)

    # Validate subparser
    val_p = subparsers.add_parser("validate")
    val_p.add_argument("--output-dir", default="output_dataset")
    val_p.add_argument("--sample-rate", type=int, default=24000)
    val_p.add_argument("--min-duration", type=float, default=2.0)
    val_p.add_argument("--max-duration", type=float, default=12.0)

    # Export subparser
    exp_p = subparsers.add_parser("export")
    exp_p.add_argument("--output-dir", default="output_dataset")

    args = parser.parse_args()

    if args.action == "build":
        cmd_build(args)
    elif args.action == "regenerate":
        cmd_regenerate(args)
    elif args.action == "validate":
        cmd_validate(args)
    elif args.action == "export":
        cmd_export(args)


if __name__ == "__main__":
    main()
