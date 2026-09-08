"""Gradio validator page for the standalone Windows app."""

import gradio as gr

from ..dataset.validator import DatasetValidator


def create_validator_page():
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 🛡️ Kiểm định Chất lượng Dataset")
            gr.Markdown("**PASS** = không phát hiện lỗi; **WARNING** = nên nghe kiểm tra; **REJECT** = cần sửa trước khi train.")
            with gr.Row():
                target_dir = gr.Textbox(label="Thư mục Dataset", value="output_dataset", scale=3)
                expected_sr = gr.Radio(label="Sample Rate chuẩn", choices=[24000, 44100, 48000], value=24000, scale=2)
            with gr.Row():
                min_dur = gr.Number(label="Min Duration (s)", value=2.0, precision=1)
                max_dur = gr.Number(label="Max Duration (s)", value=12.0, precision=1)
            validate_btn = gr.Button("🔍 BẮT ĐẦU KIỂM ĐỊNH", variant="primary", size="lg")
            summary_report = gr.Markdown("Nhấn nút trên để bắt đầu kiểm tra.")

    results_table = gr.Dataframe(
        headers=["ID", "File", "Text", "Duration", "Sample Rate", "Bit", "Peak dB", "RMS dB", "Score", "Status", "Issues"],
        datatype=["number", "str", "str", "number", "number", "number", "number", "number", "number", "str", "str"],
        interactive=False,
        label="Chi tiết từng sample",
    )

    def run_validation(dir_path, sr, min_d, max_d):
        try:
            res = DatasetValidator(
                dataset_dir=str(dir_path),
                expected_sample_rate=int(sr),
                min_duration=float(min_d),
                max_duration=float(max_d),
            ).validate_dataset()
        except Exception as exc:
            return f"❌ Validator lỗi: {exc}", []

        if res.get("error"):
            return f"❌ {res['error']}", []

        s = res["summary"]
        ready = bool(res.get("ready_for_training"))
        badge = "🟢 KHÔNG CÓ LỖI CẤU TRÚC BẮT BUỘC" if ready else "🔴 CÒN LỖI CẦN SỬA"
        report = f"""
### {badge}
- **Điểm trung bình:** {s['average_quality_score']} / 100
- **Tổng:** {s['total_checked']} | **PASS:** {s['pass_samples']} | **WARNING:** {s['warning_samples']} | **REJECT:** {s['reject_samples']}
- **Metadata lỗi:** {s['malformed_metadata_lines']} | **Orphan WAV:** {s['orphan_wav_files']} | **Thiếu WAV:** {s['missing_wav_files']}
- **Duplicate text:** {s['duplicate_transcripts']} | **Duplicate audio:** {s['duplicate_audio_files']} | **Duplicate filename:** {s['duplicate_filenames']}
- **Sai sample rate:** {s['sample_rate_mismatches']} | **Sai channels:** {s['channel_mismatches']} | **Sai bit depth:** {s['sample_width_mismatches']}
- **Clipping:** {s['clipped_samples']} | **Silence cao:** {s['high_silence_samples']} | **Audio hỏng:** {s['corrupt_audio_files']}
"""
        rows = [[
            x["id"], x["filename"], x["text"], round(x["duration"], 3),
            x.get("sample_rate", 0), x.get("sample_width_bits", 0),
            round(x.get("peak_db", 0.0), 1), round(x.get("rms_db", 0.0), 1),
            x["quality_score"], x["status"], "; ".join(x["issues"]) or "No issues",
        ] for x in res.get("samples", [])]
        return report, rows

    validate_btn.click(
        fn=run_validation,
        inputs=[target_dir, expected_sr, min_dur, max_dur],
        outputs=[summary_report, results_table],
    )
