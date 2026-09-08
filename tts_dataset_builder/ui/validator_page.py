"""
Dataset Validator Tab for Gradio interface.
Provides automated quality scanning, issue detection, and Quality Score (0-100).
"""

import gradio as gr
from ..dataset.validator import DatasetValidator


def create_validator_page():
    with gr.Row():
        with gr.Column():
            gr.Markdown("### 🛡️ Kiểm định Chất lượng Dataset (Dataset Validator)")
            gr.Markdown("Quét toàn bộ thư mục dataset để phát hiện lỗi âm thanh, câu trùng lặp, clipping, và tính điểm chất lượng.")

            with gr.Row():
                target_dir = gr.Textbox(label="Đường dẫn thư mục Dataset", value="output_dataset", scale=3)
                expected_sr = gr.Radio(label="Sample Rate chuẩn", choices=[24000, 44100, 48000], value=24000, scale=2)

            with gr.Row():
                min_dur = gr.Number(label="Min Duration (s)", value=2.0, precision=1)
                max_dur = gr.Number(label="Max Duration (s)", value=12.0, precision=1)

            validate_btn = gr.Button("🔍 BẮT ĐẦU KIỂM ĐỊNH DATASET", variant="primary", size="lg")

            summary_report = gr.Markdown("Nhấn nút trên để bắt đầu kiểm tra.")

    with gr.Row():
        results_table = gr.Dataframe(
            headers=["ID", "File", "Text", "Duration", "Sample Rate", "Peak (dB)", "RMS (dB)", "Score (0-100)", "Trạng thái", "Vấn đề phát hiện"],
            datatype=["number", "str", "str", "number", "number", "number", "number", "number", "str", "str"],
            interactive=False,
            label="Chi tiết kiểm định từng sample",
        )

    def run_validation(dir_path, sr, min_d, max_d):
        validator = DatasetValidator(
            dataset_dir=dir_path,
            expected_sample_rate=int(sr),
            min_duration=float(min_d),
            max_duration=float(max_d),
        )
        res = validator.validate_dataset()
        if not res["valid"]:
            return f"❌ Lỗi: {res.get('error')}", []

        summ = res["summary"]
        score = summ["average_quality_score"]
        status_badge = "🟢 XUẤT SẮC" if score >= 85 else ("🟡 ĐẠT YÊU CẦU" if score >= 70 else "🔴 CẦN KIỂM TRA LẠI")

        report_md = f"""
### Kết quả Đánh giá Dataset: {status_badge}
- **Điểm Chất Lượng Trung Bình:** **{score} / 100**
- **Tổng số sample đã quét:** {summ['total_checked']}
- **File WAV bị thiếu:** {summ['missing_wav_files']}
- **Transcript trùng lặp:** {summ['duplicate_transcripts']}
- **Audio trùng lặp (Hash):** {summ['duplicate_audio_files']}
- **Transcript rỗng:** {summ['empty_transcripts']}
- **Cảnh báo độ dài (< min hoặc > max):** {summ['duration_warnings']}
- **Sai lệch Sample Rate:** {summ['sample_rate_mismatches']}
- **Số sample bị Clipping:** {summ['clipped_samples']}
- **Số sample có khoảng lặng quá dài (>40%):** {summ['high_silence_samples']}
"""
        rows = []
        for s in res["samples"]:
            rows.append([
                s["id"],
                s["filename"],
                s["text"],
                round(s["duration"], 2),
                s.get("sample_rate", 0),
                round(s.get("peak_db", 0.0), 1),
                round(s.get("rms_db", 0.0), 1),
                s["quality_score"],
                s["status"],
                "; ".join(s["issues"]) if s["issues"] else "Tốt (No issues)",
            ])

        return report_md, rows

    validate_btn.click(
        fn=run_validation,
        inputs=[target_dir, expected_sr, min_dur, max_dur],
        outputs=[summary_report, results_table],
    )
