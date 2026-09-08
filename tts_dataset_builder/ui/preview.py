"""
Preview and Waveform Tab for Gradio interface.
Displays sample list, audio player, waveform display, and interactive regeneration.
"""

import os
import gradio as gr
from typing import Optional
from ..dataset.builder import DatasetBuilder
from ..audio.analyzer import analyze_wav_file
from ..dataset.database import DatasetDatabase


def create_preview_page(builder_state: dict):
    with gr.Row():
        with gr.Column(scale=3):
            gr.Markdown("### Danh sách các Sample đã cắt")
            with gr.Row():
                dataset_dir_input = gr.Textbox(label="Thư mục Dataset", value="output_dataset", scale=3)
                refresh_btn = gr.Button("🔄 Tải lại danh sách", scale=1)

            samples_table = gr.Dataframe(
                headers=["ID", "Filename", "Text", "Start (s)", "End (s)", "Duration (s)", "Status", "Score"],
                datatype=["number", "str", "str", "number", "number", "number", "str", "number"],
                interactive=False,
                label="Click để chọn sample",
            )

        with gr.Column(scale=2):
            gr.Markdown("### Nghe & Tinh chỉnh Sample")
            selected_id_box = gr.Textbox(label="Sample Filename", interactive=False)
            audio_player = gr.Audio(label="Trình phát Audio Sample (WAV)", type="filepath")

            edit_text = gr.Textbox(label="Nội dung Text (Sửa nếu cần)", lines=3)
            with gr.Row():
                edit_start = gr.Number(label="Start Time (s)", precision=3)
                edit_end = gr.Number(label="End Time (s)", precision=3)
                edit_dur = gr.Number(label="Duration (s)", precision=3, interactive=False)

            regen_btn = gr.Button("⚡ CẮT LẠI SAMPLE (REGENERATE)", variant="secondary")
            regen_result = gr.Markdown("")

    def load_table_data(dataset_dir: str):
        db_path = os.path.join(dataset_dir, "dataset.db")
        if not os.path.exists(db_path):
            return []

        db = DatasetDatabase(db_path)
        samples = db.get_all_samples()
        rows = []
        for s in samples:
            rows.append([
                s["sample_index"],
                s["wav_filename"],
                s["text"],
                round(s["actual_start"], 3),
                round(s["actual_end"], 3),
                round(s["duration"], 3),
                s["status"].upper(),
                round(s.get("quality_score", 100.0), 1),
            ])
        return rows

    def on_select_row(evt: gr.SelectData, dataset_dir: str):
        row_idx = evt.index[0]
        db_path = os.path.join(dataset_dir, "dataset.db")
        if not os.path.exists(db_path):
            return "", None, "", 0.0, 0.0, 0.0

        db = DatasetDatabase(db_path)
        samples = db.get_all_samples()
        if row_idx >= len(samples):
            return "", None, "", 0.0, 0.0, 0.0

        s = samples[row_idx]
        wav_path = os.path.join(dataset_dir, "wavs", s["wav_filename"])
        if not os.path.exists(wav_path):
            wav_path = None

        return (
            s["wav_filename"],
            wav_path,
            s["text"],
            s["actual_start"],
            s["actual_end"],
            s["duration"],
        )

    def on_regenerate(filename, text, start, end, dataset_dir):
        if not filename:
            return "Vui lòng chọn một sample từ bảng!", None, []

        db_path = os.path.join(dataset_dir, "dataset.db")
        builder = builder_state.get("builder")
        if not builder:
            builder = DatasetBuilder(output_dir=dataset_dir, db_path=db_path)

        try:
            updated = builder.regenerate_single_sample(
                wav_filename=filename,
                new_text=text,
                new_start=float(start),
                new_end=float(end),
            )
            wav_path = os.path.join(dataset_dir, "wavs", filename)
            table_data = load_table_data(dataset_dir)
            msg = f"✅ Đã cắt lại thành công sample `{filename}` ({updated['duration']:.2f}s)!"
            return msg, wav_path, table_data
        except Exception as e:
            return f"❌ Lỗi khi cắt lại: {str(e)}", None, []

    refresh_btn.click(
        fn=load_table_data,
        inputs=[dataset_dir_input],
        outputs=[samples_table],
    )

    samples_table.select(
        fn=on_select_row,
        inputs=[dataset_dir_input],
        outputs=[selected_id_box, audio_player, edit_text, edit_start, edit_end, edit_dur],
    )

    regen_btn.click(
        fn=on_regenerate,
        inputs=[selected_id_box, edit_text, edit_start, edit_end, dataset_dir_input],
        outputs=[regen_result, audio_player, samples_table],
    )
