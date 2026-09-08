import os
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from tts_dataset_builder.audio.cutter import calculate_slice_bounds, cut_pcm_slice
from tts_dataset_builder.dataset.database import DatasetDatabase
from tts_dataset_builder.dataset.exporter import export_dataset_to_zip, inspect_zip


class CutterTests(unittest.TestCase):
    def test_overlap_does_not_move_start_into_speech(self):
        start, end = calculate_slice_bounds(
            start_sec=10.0,
            end_sec=12.0,
            padding_before=0.15,
            padding_after=0.20,
            prev_end_sec=10.10,  # transcript overlap
            next_start_sec=12.50,
            total_audio_duration=20.0,
        )
        self.assertLessEqual(start, 10.0)
        self.assertGreater(end, 12.0)

    def test_cut_writes_pcm16_mono_wave(self):
        with tempfile.TemporaryDirectory() as td:
            pcm = Path(td) / "source.pcm"
            wav = Path(td) / "out.wav"
            sr = 24000
            samples = [1000] * sr
            pcm.write_bytes(struct.pack("<" + "h" * len(samples), *samples))
            written = cut_pcm_slice(str(pcm), str(wav), 0.1, 0.6, sr)
            self.assertGreater(written, 0)
            with wave.open(str(wav), "rb") as wf:
                self.assertEqual(wf.getnchannels(), 1)
                self.assertEqual(wf.getsampwidth(), 2)
                self.assertEqual(wf.getframerate(), sr)
                self.assertAlmostEqual(wf.getnframes() / sr, 0.5, places=2)


class DatabaseTests(unittest.TestCase):
    def test_source_mapping_is_exact(self):
        with tempfile.TemporaryDirectory() as td:
            db = DatasetDatabase(os.path.join(td, "dataset.db"))
            pcm = os.path.join(td, "source.pcm")
            Path(pcm).write_bytes(b"\0\0" * 100)
            db.set_source_state("key-a", "book.mp3", pcm, 24000, "sig")
            db.upsert_sample({
                "sample_index": 1,
                "wav_filename": "000001.wav",
                "text": "Xin chào.",
                "source_audio": "book.mp3",
                "source_key": "key-a",
                "source_pcm": pcm,
                "sample_rate": 24000,
                "start_time": 1.0,
                "end_time": 2.0,
            })
            sample = db.find_processed_sample("key-a", 1.0, 2.0)
            self.assertIsNotNone(sample)
            self.assertEqual(sample["source_pcm"], pcm)
            self.assertEqual(sample["sample_rate"], 24000)
            self.assertIsNone(db.find_processed_sample("key-b", 1.0, 2.0))


class ExportTests(unittest.TestCase):
    def _wav(self, path: Path):
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(b"\0\0" * 2400)

    def test_export_contains_only_metadata_referenced_wavs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wavs = root / "wavs"
            wavs.mkdir()
            self._wav(wavs / "000001.wav")
            self._wav(wavs / "999999.wav")  # orphan; must not be exported
            (root / "metadata.csv").write_text("000001.wav|Xin chào.\n", encoding="utf-8")
            (root / "metadata.json").write_text("[]", encoding="utf-8")
            zip_path = export_dataset_to_zip(str(root))
            info = inspect_zip(zip_path)
            self.assertEqual(info["wav_count"], 1)
            self.assertIn("wavs/000001.wav", info["names"])
            self.assertNotIn("wavs/999999.wav", info["names"])

    def test_export_rejects_missing_referenced_wav(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "wavs").mkdir()
            (root / "metadata.csv").write_text("000001.wav|Xin chào.\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                export_dataset_to_zip(str(root))


if __name__ == "__main__":
    unittest.main()
