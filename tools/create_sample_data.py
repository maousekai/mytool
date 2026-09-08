"""
Helper script to generate realistic sample Vietnamese audiobook audio and transcripts.
Generates modulated multi-harmonic speech-like audio with pause gaps that match
the exact timestamps in JSON, CSV, and SRT transcripts.
"""

import os
import json
import csv
import math
import struct
import wave
import subprocess

SAMPLE_RATE = 24000
SEGMENTS = [
    {"start": 1.50, "end": 7.85, "text": "Ta mỗi ngày nhận được một hệ thống mới."},
    {"start": 8.35, "end": 13.95, "text": "Hôm nay lại là một ngày bình thường."},
    {"start": 14.70, "end": 15.50, "text": "Không."},  # 0.8s short sample for testing auto-merge
    {"start": 16.10, "end": 20.10, "text": "Hắn lập tức quay đầu nhìn lại."},
    {"start": 20.80, "end": 27.20, "text": "Một thanh niên mặc áo lam bước từ trong sương mù đi ra."},
    {"start": 27.80, "end": 33.50, "text": "Trên người hắn tản ra khí tức vô cùng thần bí."},
    {"start": 34.20, "end": 40.80, "text": "Thế giới này quả thực có quá nhiều điều chưa thể lý giải được."},
]

TOTAL_DURATION = 42.0  # seconds


def generate_speech_like_audio(output_wav: str):
    total_samples = int(SAMPLE_RATE * TOTAL_DURATION)
    samples = [0] * total_samples

    for seg in SEGMENTS:
        s_idx = int(seg["start"] * SAMPLE_RATE)
        e_idx = min(total_samples, int(seg["end"] * SAMPLE_RATE))
        seg_len = e_idx - s_idx

        # Fundamental frequencies simulating Vietnamese pitch contour & speech harmonics
        f0 = 150.0  # fundamental
        for i in range(seg_len):
            t = i / SAMPLE_RATE
            # Formant simulation: f0, 3*f0, 5*f0 with AM modulation
            envelope = math.sin(math.pi * i / seg_len) ** 0.5  # smooth onset/offset
            vibrato = 1.0 + 0.03 * math.sin(2 * math.pi * 5.0 * t)
            pitch = f0 * vibrato + 25.0 * math.sin(2 * math.pi * 0.8 * t)

            # Sum of harmonics with realistic decay
            val = (
                0.60 * math.sin(2 * math.pi * pitch * t)
                + 0.25 * math.sin(2 * math.pi * 2.1 * pitch * t)
                + 0.15 * math.sin(2 * math.pi * 3.2 * pitch * t)
            )
            # Syllable rhythm modulation (~4 syllables per sec)
            syllable_mod = 0.5 + 0.5 * (math.sin(2 * math.pi * 3.8 * t) ** 2)
            sample_val = val * envelope * syllable_mod * 0.70

            int_val = int(sample_val * 32767.0)
            samples[s_idx + i] = max(-32768, min(32767, int_val))

    os.makedirs(os.path.dirname(os.path.abspath(output_wav)), exist_ok=True)
    with wave.open(output_wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        raw_bytes = struct.pack(f"<{len(samples)}h", *samples)
        wf.writeframes(raw_bytes)


def main():
    os.makedirs("sample_data", exist_ok=True)
    wav_path = "sample_data/audiobook_chapter_01.wav"
    mp3_path = "sample_data/audiobook_chapter_01.mp3"

    print("Generating sample audio...")
    generate_speech_like_audio(wav_path)

    # Convert to MP3
    subprocess.run(["ffmpeg", "-y", "-i", wav_path, "-b:a", "192k", mp3_path], check=True)
    print(f"Generated {mp3_path} ({os.path.getsize(mp3_path)} bytes)")

    # 1. JSON
    with open("sample_data/transcript.json", "w", encoding="utf-8") as f:
        json.dump(SEGMENTS, f, ensure_ascii=False, indent=2)

    # 2. CSV
    with open("sample_data/transcript.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["start", "end", "text"])
        for s in SEGMENTS:
            writer.writerow([s["start"], s["end"], s["text"]])

    # 3. SRT
    with open("sample_data/transcript.srt", "w", encoding="utf-8") as f:
        for idx, s in enumerate(SEGMENTS):
            sh = int(s["start"] // 3600)
            sm = int((s["start"] % 3600) // 60)
            ss = int(s["start"] % 60)
            sms = int(round((s["start"] - int(s["start"])) * 1000))

            eh = int(s["end"] // 3600)
            em = int((s["end"] % 3600) // 60)
            es = int(s["end"] % 60)
            ems = int(round((s["end"] - int(s["end"])) * 1000))

            f.write(f"{idx + 1}\n")
            f.write(f"{sh:02d}:{sm:02d}:{ss:02d},{sms:03d} --> {eh:02d}:{em:02d}:{es:02d},{ems:03d}\n")
            f.write(f"{s['text']}\n\n")

    print("Sample transcripts generated successfully!")


if __name__ == "__main__":
    main()
