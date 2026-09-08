"""
Vietnamese TTS Dataset Builder - Main Application Entrypoint.
Launch local Gradio UI: python app.py -> http://127.0.0.1:7860
"""

import os
import sys
import gradio as gr

# Ensure root directory is on Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import setup_logger, get_logger
from utils.ffmpeg import check_ffmpeg
from dataset.exporter import export_dataset_to_zip
from ui.dataset_page import create_dataset_page
from ui.preview import create_preview_page
from ui.validator_page import create_validator_page

# Setup logging
setup_logger(log_dir="logs", log_filename="app.log")
logger = get_logger()


def main():
    logger.info("Starting Vietnamese TTS Dataset Builder...")
    ffmpeg_ok, ffmpeg_msg = check_ffmpeg()

    builder_state = {"builder": None}

    # Custom Gradio Blocks interface
    with gr.Blocks(
        title="Vietnamese TTS Dataset Builder",
        theme=gr.themes.Soft(
            primary_hue="emerald",
            secondary_hue="slate",
            neutral_hue="slate",
        ),
    ) as demo:
        gr.Markdown("""
# 🎙️ Vietnamese TTS Dataset Builder
### Tự động xử lý và cắt audio audiobook theo transcript có mốc thời gian thành Dataset chuẩn fine-tune Text-to-Speech
""")

        if not ffmpeg_ok:
            gr.Warning("⚠️ KHÔNG TÌM THẤY FFMPEG: Vui lòng cài đặt FFmpeg trên Windows để ứng dụng hoạt động!")
            with gr.Accordion("📌 Hướng dẫn cài đặt FFmpeg trên Windows (Nhấn để xem)", open=True):
                gr.Markdown(f"```text\n{ffmpeg_msg}\n```")
        else:
            gr.Info(f"✅ {ffmpeg_msg}")

        with gr.Tabs():
            with gr.TabItem("🚀 1. Tạo Dataset (Builder)"):
                create_dataset_page(builder_state)

            with gr.TabItem("🎧 2. Nghe thử & Tinh chỉnh (Preview & Waveform)"):
                create_preview_page(builder_state)

            with gr.TabItem("🛡️ 3. Kiểm định Chất lượng (Validator)"):
                create_validator_page()

            with gr.TabItem("📦 4. Xuất File & Nhật ký (Export & Logs)"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### 📦 Xuất Dataset thành file ZIP")
                        gr.Markdown("Đóng gói toàn bộ thư mục `wavs/`, `metadata.csv`, `metadata.json`, `rejected.csv`, `dataset_report.json` thành `dataset.zip`.")
                        export_dir_in = gr.Textbox(label="Thư mục Dataset cần nén", value="output_dataset")
                        export_btn = gr.Button("🎁 NÉN VÀ TẢI VỀ DATASET.ZIP", variant="primary")
                        export_file_out = gr.File(label="File ZIP tải về")

                        def on_export(d_dir):
                            try:
                                zip_p = export_dataset_to_zip(d_dir)
                                return zip_p
                            except Exception as e:
                                gr.Warning(f"Lỗi nén ZIP: {str(e)}")
                                return None

                        export_btn.click(fn=on_export, inputs=[export_dir_in], outputs=[export_file_out])

                    with gr.Column():
                        gr.Markdown("### 📜 Nhật ký xử lý (logs/app.log)")
                        refresh_logs_btn = gr.Button("🔄 Làm mới Logs")
                        logs_box = gr.TextArea(label="Nội dung Logs gần nhất", lines=15, interactive=False)

                        def get_recent_logs():
                            log_p = os.path.join("logs", "app.log")
                            if not os.path.exists(log_p):
                                return "Chưa có file log."
                            try:
                                with open(log_p, "r", encoding="utf-8", errors="replace") as f:
                                    lines = f.readlines()
                                return "".join(lines[-150:])
                            except Exception as e:
                                return f"Lỗi đọc log: {str(e)}"

                        refresh_logs_btn.click(fn=get_recent_logs, inputs=[], outputs=[logs_box])

    print("Khởi chạy giao diện Gradio tại: http://127.0.0.1:7860")
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)


if __name__ == "__main__":
    main()
