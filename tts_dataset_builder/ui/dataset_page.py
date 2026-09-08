"""
Dataset Builder Tab for Gradio interface.
Provides audio/transcript uploads, audio format options, duration bounds,
padding, VAD refinement, normalization, and real-time build progress.
"""

import os
import gradio as gr
from typing import List, Optional
from ..dataset.builder import DatasetBuilder
from ..utils.ffmpeg import check_ffmpeg
from ..utils.logger import get_logger

logger = get_logger()


def create_dataset_page(builder_state: dict):
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 1. Nguồn Audio & Transcript")
            audio_files_input = gr.File(
                label="Chọn File Audio (MP3, WAV, M4A, FLAC) - Có thể chọn nhiều file",
                file_count="multiple",
                file_types=[".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"],
            )
            transcript_file_input = gr.File(
                label="Chọn File Transcript (JSON, CSV, SRT)",
                file_count="single",
                file_types=[".json", ".csv", ".srt", ".tsv", ".txt"],
            )

            gr.Markdown("### 2. Cấu hình Audio Output")
            sample_rate_select = gr.Radio(
                label="Sample Rate (Mono 16-bit PCM)",
                choices=[24000, 44100, 48000],
                value=24000,
                info="Mặc định 24,000 Hz chuẩn cho đa số mô hình TTS tiếng Việt hiện đại",
            )

            with gr.Row():
                pad_before = gr.Number(label="Padding Before (giây)", value=0.15, precision=2)
                pad_after = gr.Number(label="Padding After (giây)", value=0.20, precision=2)

            refine_vad_chk = gr.Checkbox(
                label="Refine timestamps using silence/VAD (Tìm điểm dừng âm ±300ms)",
                value=False,
                info="Chỉ tinh chỉnh điểm cắt ở khoảng lặng gần nhất, không sửa nội dung câu",
            )

            gr.Markdown("### 3. Bộ lọc Độ dài & Ghép câu")
            with gr.Row():
                min_dur = gr.Number(label="Min Duration (giây)", value=2.0, precision=1)
                max_dur = gr.Number(label="Max Duration (giây)", value=12.0, precision=1)

            auto_merge_chk = gr.Checkbox(
                label="Auto merge short samples (Tự động gộp câu quá ngắn)",
                value=True,
                info="Gộp câu < Min Duration nếu khoảng lặng giữa hai câu nhỏ và tổng <= Max Duration",
            )
            merge_thresh = gr.Number(
                label="Ngưỡng khoảng lặng ghép câu (giây)",
                value=0.80,
                precision=2,
            )

            gr.Markdown("### 4. Chuẩn hóa Âm lượng (Tùy chọn)")
            with gr.Row():
                peak_norm_chk = gr.Checkbox(label="Peak Normalization (-1 dBFS)", value=False)
                loudness_norm_chk = gr.Checkbox(label="Loudness Normalization (-20 LUFS)", value=False)

            output_dir_input = gr.Textbox(
                label="Thư mục xuất Dataset",
                value="output_dataset",
            )

            build_btn = gr.Button("🚀 BẮT ĐẦU XỬ LÝ & TẠO DATASET", variant="primary", size="lg")

        with gr.Column(scale=1):
            gr.Markdown("### 5. Tiến độ Xử lý Thực tế")
            progress_status = gr.Textbox(
                label="Trạng thái",
                value="Sẵn sàng...",
                interactive=False,
            )
            progress_bar_text = gr.Markdown("Chưa chạy tiến trình nào.")

            gr.Markdown("### 6. Báo cáo Dataset (Dataset Summary)")
            summary_markdown = gr.Markdown("""
*Chưa có dữ liệu. Vui lòng chọn audio + transcript và nhấn Bắt đầu xử lý.*
            """)

            gr.Markdown("### Phân bố độ dài câu (Duration Distribution)")
            distribution_df = gr.Dataframe(
                headers=["Khoảng thời gian", "Số lượng câu (Samples)"],
                datatype=["str", "number"],
                interactive=False,
            )

    def run_build_process(
        audio_files,
        transcript_file,
        sample_rate,
        pad_b,
        pad_a,
        refine_vad,
        min_d,
        max_d,
        auto_merge,
        merge_th,
        peak_n,
        loud_n,
        out_dir,
    ):
        if not audio_files:
            yield "Lỗi: Bạn chưa chọn file audio nào!", "Vui lòng tải lên ít nhất 1 file audio.", "", []
            return

        if not transcript_file:
            yield "Lỗi: Bạn chưa chọn file transcript!", "Vui lòng tải lên file transcript (JSON, CSV, SRT).", "", []
            return

        # Check FFmpeg first
        ok, ffmpeg_msg = check_ffmpeg()
        if not ok:
            yield f"LỖI FFMPEG:\n{ffmpeg_msg}", "Không thể chạy vì thiếu FFmpeg.", "", []
            return

        builder = DatasetBuilder(
            output_dir=out_dir,
            sample_rate=int(sample_rate),
            padding_before=float(pad_b),
            padding_after=float(pad_a),
            refine_vad=bool(refine_vad),
            min_duration=float(min_d),
            max_duration=float(max_d),
            auto_merge_short=bool(auto_merge),
            merge_silence_threshold=float(merge_th),
            peak_norm=bool(peak_n),
            loudness_norm=bool(loud_n),
        )
        builder_state["builder"] = builder

        transcript_path = transcript_file.name if hasattr(transcript_file, "name") else str(transcript_file)
        audio_paths = [a.name if hasattr(a, "name") else str(a) for a in audio_files]

        for audio_p in audio_paths:
            current_status = f"Đang xử lý {os.path.basename(audio_p)}..."

            def update_progress(curr, total, pct, eta, cur_file, msg):
                pass  # Gradio generator handles yield

            report = builder.process_audio_file(audio_p, transcript_path)

        final_report = builder.generate_reports()
        summ = final_report["summary"]
        bins = final_report["duration_distribution"]

        summary_md = f"""
### Dataset Summary
- **Tổng số câu (Samples):** {summ['total_samples']}
- **Chấp nhận (Accepted):** ✅ **{summ['accepted_samples']}**
- **Loại bỏ (Rejected):** ❌ **{summ['rejected_samples']}**
- **Tổng thời lượng audio:** **{summ['total_duration_formatted']}** ({summ['total_duration_seconds']}s)
- **Độ dài trung bình:** **{summ['average_duration_seconds']}s**
- **Độ dài ngắn nhất:** {summ['min_duration_seconds']}s | **Dài nhất:** {summ['max_duration_seconds']}s
"""
        bin_data = [[k, v] for k, v in bins.items()]

        yield (
            "Hoàn thành xử lý dataset!",
            f"✅ Đã xử lý xong toàn bộ {summ['total_samples']} câu vào `{out_dir}`.",
            summary_md,
            bin_data,
        )

    build_btn.click(
        fn=run_build_process,
        inputs=[
            audio_files_input,
            transcript_file_input,
            sample_rate_select,
            pad_before,
            pad_after,
            refine_vad_chk,
            min_dur,
            max_dur,
            auto_merge_chk,
            merge_thresh,
            peak_norm_chk,
            loudness_norm_chk,
            output_dir_input,
        ],
        outputs=[
            progress_status,
            progress_bar_text,
            summary_markdown,
            distribution_df,
        ],
    )
