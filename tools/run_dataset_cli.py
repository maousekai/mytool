"""CLI bridge between the web server and the Python dataset engine."""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_dataset_builder.dataset.builder import DatasetBuilder
from tts_dataset_builder.dataset.exporter import export_dataset_to_zip, export_source_package, inspect_zip
from tts_dataset_builder.dataset.validator import DatasetValidator
from tts_dataset_builder.utils.logger import setup_logger

setup_logger()


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def emit_progress(curr, total, pct, eta, cur_file, msg):
    emit({
        "type": "progress",
        "current": curr,
        "total": total,
        "percentage": pct,
        "eta_seconds": round(float(eta), 1),
        "current_file": cur_file,
        "message": msg,
    })


def cmd_build(args):
    audio_files = [os.path.abspath(p) for p in args.audio_files]
    transcripts = [os.path.abspath(p) for p in args.transcript_files]
    if len(audio_files) != len(transcripts):
        raise ValueError(
            "Số file audio phải bằng số file transcript. Mỗi audio cần đúng một transcript tương ứng."
        )
    if not audio_files:
        raise ValueError("Không có file audio để xử lý")

    for p in audio_files + transcripts:
        if not os.path.isfile(p):
            raise FileNotFoundError(p)

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

    file_count = len(audio_files)
    for file_idx, (audio_p, transcript_p) in enumerate(zip(audio_files, transcripts), 1):
        def mapped_progress(curr, total, pct, eta, cur_file, msg, file_idx=file_idx):
            overall = ((file_idx - 1) + float(pct) / 100.0) / file_count * 100.0
            emit_progress(curr, total, round(overall, 1), eta, cur_file, msg)

        emit_progress(0, 0, round((file_idx - 1) / file_count * 100, 1), 0.0,
                      os.path.basename(audio_p), f"Chuẩn bị {file_idx}/{file_count}: {os.path.basename(audio_p)}")
        builder.process_audio_file(audio_p, transcript_p, progress_callback=mapped_progress)

    emit({"type": "completed", "report": builder.generate_reports()})


def cmd_regenerate(args):
    builder = DatasetBuilder(output_dir=args.output_dir)
    sample = builder.regenerate_single_sample(
        wav_filename=args.filename,
        new_text=args.text,
        new_start=args.start,
        new_end=args.end,
    )
    emit({"type": "regenerated", "sample": sample})


def cmd_validate(args):
    result = DatasetValidator(
        dataset_dir=args.output_dir,
        expected_sample_rate=args.sample_rate,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
    ).validate_dataset()
    emit({"type": "validated", "result": result})


def cmd_export(args):
    path = export_dataset_to_zip(args.output_dir)
    info = inspect_zip(path)
    emit({
        "type": "exported",
        "zip_path": path,
        "size_bytes": info["size_bytes"],
        "file_count": info["file_count"],
        "wav_count": info["wav_count"],
        "valid": True,
    })


def cmd_package(args):
    path = export_source_package(args.source_dir, args.output_zip)
    info = inspect_zip(path)
    emit({
        "type": "packaged",
        "zip_path": path,
        "size_bytes": info["size_bytes"],
        "file_count": info["file_count"],
        "valid": True,
    })


def main():
    parser = argparse.ArgumentParser(description="TTS Dataset Builder CLI")
    sub = parser.add_subparsers(dest="action", required=True)

    build = sub.add_parser("build")
    build.add_argument("--output-dir", default="output_dataset")
    build.add_argument("--audio-files", nargs="+", required=True)
    build.add_argument("--transcript-files", nargs="+", required=True)
    build.add_argument("--sample-rate", type=int, default=24000)
    build.add_argument("--padding-before", type=float, default=0.15)
    build.add_argument("--padding-after", type=float, default=0.20)
    build.add_argument("--refine-vad", action="store_true")
    build.add_argument("--min-duration", type=float, default=2.0)
    build.add_argument("--max-duration", type=float, default=12.0)
    build.add_argument("--auto-merge-short", action="store_true")
    build.add_argument("--merge-silence-threshold", type=float, default=0.80)
    build.add_argument("--peak-norm", action="store_true")
    build.add_argument("--loudness-norm", action="store_true")
    build.add_argument("--target-lufs", type=float, default=-20.0)

    regen = sub.add_parser("regenerate")
    regen.add_argument("--output-dir", default="output_dataset")
    regen.add_argument("--filename", required=True)
    regen.add_argument("--text", required=True)
    regen.add_argument("--start", type=float, required=True)
    regen.add_argument("--end", type=float, required=True)

    val = sub.add_parser("validate")
    val.add_argument("--output-dir", default="output_dataset")
    val.add_argument("--sample-rate", type=int, default=24000)
    val.add_argument("--min-duration", type=float, default=2.0)
    val.add_argument("--max-duration", type=float, default=12.0)

    exp = sub.add_parser("export")
    exp.add_argument("--output-dir", default="output_dataset")

    pkg = sub.add_parser("package")
    pkg.add_argument("--source-dir", required=True)
    pkg.add_argument("--output-zip", required=True)

    args = parser.parse_args()
    actions = {
        "build": cmd_build,
        "regenerate": cmd_regenerate,
        "validate": cmd_validate,
        "export": cmd_export,
        "package": cmd_package,
    }
    actions[args.action](args)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        emit({"type": "error", "error": str(exc)})
        raise
