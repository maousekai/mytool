"""Gradio Dataset Builder page used by the standalone Windows package."""

import os
from typing import Any, List

import gradio as gr

from ..dataset.builder import DatasetBuilder
from ..utils.ffmpeg import check_ffmpeg


def _path(item: Any) -> str:
    return item.name if hasattr(item, "name") else str(item)


def create_dataset_page(builder_state: dict):
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 1. Nguồn Audio & Transcript")
            gr.Markdown("**Mỗi audio cần đúng 1 transcript tương ứng và hai danh sách phải cùng thứ tự.**")
            audio_files_input = gr.File(
                label="Audio (MP3/WAV/M4A/FLAC/OGG/AAC) - chọn nhiều file",
                file_count="multiple",
                file_types=[".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"],
            )
            transcript_files_input = gr.File(
                label="Transcript (JSON/CSV/SRT/TSV/TXT) - chọn đúng số lượng audio",
                file_count="multiple",
                file_types=[".json", ".csv", ".srt", ".tsv", ".txt"],
            )

            gr.Markdown("### 2. Cấu hình Audio Output")
            sample_rate_select = gr.Radio(
                label="Sample Rate (Mono 16-bit PCM)", choices=[24000, 44100, 48000], value=24000
            )
            with gr.Row():
                pad_before = gr.Number(label="Padding Before (s)", value=0.15, precision=2)
                pad_after = gr.Number(label="Padding After (s)", value=0.20, precision=2)
            refine_vad_chk = gr.Checkbox(
                label="Refine timestamps bằng silence/VAD ±300ms", value=False
            )

            gr.Markdown("### 3. Độ dài & Ghép câu")
            with gr.Row():
                min_dur = gr.Number(label="Min Duration (s)", value=2.0, precision=1)
                max_dur = gr.Number(label="Max Duration (s)", value=12.0, precision=1)
            auto_merge_chk = gr.Checkbox(label="Auto merge short samples", value=True)
            merge_thresh = gr.Number(label="Ngưỡng silence để merge (s)", value=0.80, precision=2)

            gr.Markdown("### 4. Chuẩn hóa âm lượng - mặc định OFF")
            with gr.Row():
                peak_norm_chk = gr.Checkbox(label="Peak Normalization (-1 dBFS)", value=False)
                loudness_norm_chk = gr.Checkbox(label="Loudness Normalization (-20 LUFS)", value=False)
            output_dir_input = gr.Textbox(label="Thư mục xuất Dataset", value="output_dataset")
            build_btn = gr.Button("🚀 BẮT ĐẦU XỬ LÝ & TẠO DATASET", variant="primary", size="lg")

        with gr.Column(scale=1):
            gr.Markdown("### 5. Tiến độ")
            progress_status = gr.Textbox(label="Trạng thái", value="Sẵn sàng", interactive=False)
            progress_bar_text = gr.Markdown("Chưa chạy tiến trình nào.")
            gr.Markdown("### 6. Báo cáo Dataset")
            summary_markdown = gr.Markdown("*Chưa có dữ liệu.*")
            distribution_df = gr.Dataframe(
                headers=["Khoảng thời gian", "Số samples"],
                datatype=["str", "number"], interactive=False,
            )

    def run_build_process(
        audio_files, transcript_files, sample_rate, pad_b, pad_a, refine_vad,
        min_d, max_d, auto_merge, merge_th, peak_n, loud_n, out_dir,
        progress=gr.Progress(track_tqdm=False),
    ):
        audio_files = audio_files or []
        transcript_files = transcript_files or []
        if not audio_files:
            return "Lỗi", "Chưa chọn audio.", "", []
        if len(audio_files) != len(transcript_files):
            return (
                "Lỗi ghép file",
                f"Có {len(audio_files)} audio nhưng {len(transcript_files)} transcript. Cần số lượng bằng nhau.",
                "", [],
            )
        if float(min_d) >= float(max_d):
            return "Lỗi cấu hình", "Min Duration phải nhỏ hơn Max Duration.", "", []
        if bool(peak_n) and bool(loud_n):
            return "Lỗi cấu hình", "Chỉ bật Peak hoặc Loudness normalization, không bật cả hai.", "", []

        ok, ffmpeg_msg = check_ffmpeg()
        if not ok:
            return "LỖI FFMPEG", ffmpeg_msg, "", []

        builder = DatasetBuilder(
            output_dir=str(out_dir), sample_rate=int(sample_rate),
            padding_before=float(pad_b), padding_after=float(pad_a),
            refine_vad=bool(refine_vad), min_duration=float(min_d), max_duration=float(max_d),
            auto_merge_short=bool(auto_merge), merge_silence_threshold=float(merge_th),
            peak_norm=bool(peak_n), loudness_norm=bool(loud_n),
        )
        builder_state["builder"] = builder

        pairs = list(zip([_path(x) for x in audio_files], [_path(x) for x in transcript_files]))
        for file_idx, (audio_p, transcript_p) in enumerate(pairs):
            def callback(curr, total, pct, eta, cur_file, msg, file_idx=file_idx):
                overall = (file_idx + pct / 100.0) / len(pairs)
                progress(overall, desc=f"{os.path.basename(cur_file)} - {msg}")

            builder.process_audio_file(audio_p, transcript_p, progress_callback=callback)

        report = builder.generate_reports()
        summ = report["summary"]
        bins = report["duration_distribution"]
        summary_md = f"""
### Dataset Summary
- **Tổng:** {summ['total_samples']}
- **Accepted:** ✅ **{summ['accepted_samples']}**
- **Rejected:** ❌ **{summ['rejected_samples']}**
- **Thời lượng:** **{summ['total_duration_formatted']}**
- **Trung bình:** **{summ['average_duration_seconds']}s**
- **Min / Max:** {summ['min_duration_seconds']}s / {summ['max_duration_seconds']}s
"""
        return (
            "Hoàn thành",
            f"✅ Dataset đã tạo tại `{builder.output_dir}`",
            summary_md,
            [[k, v] for k, v in bins.items()],
        )

    build_btn.click(
        fn=run_build_process,
        inputs=[
            audio_files_input, transcript_files_input, sample_rate_select,
            pad_before, pad_after, refine_vad_chk, min_dur, max_dur,
            auto_merge_chk, merge_thresh, peak_norm_chk, loudness_norm_chk,
            output_dir_input,
        ],
        outputs=[progress_status, progress_bar_text, summary_markdown, distribution_df],
    )
