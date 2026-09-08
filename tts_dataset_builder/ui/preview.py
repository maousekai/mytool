"""Preview/regeneration tab for the standalone Gradio interface."""

import json
import os

import gradio as gr

from ..dataset.builder import DatasetBuilder
from ..dataset.database import DatasetDatabase


def _builder_from_dataset(dataset_dir: str) -> DatasetBuilder:
    params = {}
    report_path = os.path.join(dataset_dir, "dataset_report.json")
    if os.path.isfile(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                params = json.load(f).get("parameters", {})
        except (OSError, ValueError, TypeError):
            params = {}
    return DatasetBuilder(
        output_dir=dataset_dir,
        db_path=os.path.join(dataset_dir, "dataset.db"),
        sample_rate=int(params.get("sample_rate", 24000)),
        padding_before=float(params.get("padding_before", 0.15)),
        padding_after=float(params.get("padding_after", 0.20)),
        refine_vad=bool(params.get("refine_vad", False)),
        min_duration=float(params.get("min_duration", 2.0)),
        max_duration=float(params.get("max_duration", 12.0)),
        auto_merge_short=bool(params.get("auto_merge_short", True)),
        merge_silence_threshold=float(params.get("merge_silence_threshold", 0.80)),
        peak_norm=bool(params.get("peak_norm", False)),
        loudness_norm=bool(params.get("loudness_norm", False)),
        target_lufs=float(params.get("target_lufs", -20.0)),
    )


def create_preview_page(builder_state: dict):
    with gr.Row():
        with gr.Column(scale=3):
            gr.Markdown("### Danh sách Sample")
            with gr.Row():
                dataset_dir_input = gr.Textbox(label="Thư mục Dataset", value="output_dataset", scale=3)
                refresh_btn = gr.Button("🔄 Tải lại", scale=1)
            samples_table = gr.Dataframe(
                headers=["ID", "Filename", "Text", "Start", "End", "Duration", "Status", "Score"],
                datatype=["number", "str", "str", "number", "number", "number", "str", "number"],
                interactive=False,
            )
        with gr.Column(scale=2):
            gr.Markdown("### Nghe & Tinh chỉnh")
            selected_id_box = gr.Textbox(label="Sample Filename", interactive=False)
            audio_player = gr.Audio(label="WAV", type="filepath")
            edit_text = gr.Textbox(label="Text", lines=3)
            with gr.Row():
                edit_start = gr.Number(label="Start (s)", precision=3)
                edit_end = gr.Number(label="End (s)", precision=3)
                edit_dur = gr.Number(label="Duration (s)", precision=3, interactive=False)
            regen_btn = gr.Button("⚡ CẮT LẠI SAMPLE", variant="secondary")
            regen_result = gr.Markdown("")

    def load_table_data(dataset_dir: str):
        db_path = os.path.join(dataset_dir, "dataset.db")
        if not os.path.isfile(db_path):
            return []
        rows = []
        for s in DatasetDatabase(db_path).get_all_samples():
            rows.append([
                s["sample_index"], s["wav_filename"], s["text"],
                round(float(s["actual_start"]), 3), round(float(s["actual_end"]), 3),
                round(float(s["duration"]), 3), str(s["status"]).upper(),
                round(float(s.get("quality_score", 0.0)), 1),
            ])
        return rows

    def on_select_row(evt: gr.SelectData, dataset_dir: str):
        row_idx = int(evt.index[0])
        db_path = os.path.join(dataset_dir, "dataset.db")
        if not os.path.isfile(db_path):
            return "", None, "", 0.0, 0.0, 0.0
        samples = DatasetDatabase(db_path).get_all_samples()
        if row_idx < 0 or row_idx >= len(samples):
            return "", None, "", 0.0, 0.0, 0.0
        s = samples[row_idx]
        wav_path = os.path.join(dataset_dir, "wavs", s["wav_filename"])
        if not os.path.isfile(wav_path):
            wav_path = None
        return s["wav_filename"], wav_path, s["text"], s["actual_start"], s["actual_end"], s["duration"]

    def on_regenerate(filename, text, start, end, dataset_dir):
        if not filename:
            return "Vui lòng chọn một sample.", None, load_table_data(dataset_dir)
        builder = builder_state.get("builder")
        if not builder or os.path.abspath(builder.output_dir) != os.path.abspath(dataset_dir):
            builder = _builder_from_dataset(dataset_dir)
            builder_state["builder"] = builder
        try:
            updated = builder.regenerate_single_sample(
                wav_filename=str(filename), new_text=str(text),
                new_start=float(start), new_end=float(end),
            )
            wav_path = os.path.join(dataset_dir, "wavs", str(filename))
            return (
                f"✅ Đã cắt lại `{filename}` ({updated['duration']:.2f}s) bằng đúng PCM nguồn và cấu hình dataset.",
                wav_path,
                load_table_data(dataset_dir),
            )
        except Exception as exc:
            return f"❌ Lỗi: {exc}", None, load_table_data(dataset_dir)

    refresh_btn.click(fn=load_table_data, inputs=[dataset_dir_input], outputs=[samples_table])
    samples_table.select(
        fn=on_select_row, inputs=[dataset_dir_input],
        outputs=[selected_id_box, audio_player, edit_text, edit_start, edit_end, edit_dur],
    )
    regen_btn.click(
        fn=on_regenerate,
        inputs=[selected_id_box, edit_text, edit_start, edit_end, dataset_dir_input],
        outputs=[regen_result, audio_player, samples_table],
    )
