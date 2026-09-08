# Vietnamese TTS Dataset Builder

Tool local để biến **audio audiobook + transcript có `start/end/text`** thành dataset WAV + metadata phục vụ huấn luyện hoặc fine-tune TTS.

> Tool này chỉ chuẩn bị dataset. Nó không chứa model train/voice-cloning và không gọi API cloud.

## Pipeline

```text
Audio MP3/WAV/M4A/FLAC
        +
Transcript JSON/CSV/SRT/TSV/TXT
        ↓
FFmpeg decode 1 lần → PCM16 mono
        ↓
validate timestamp → optional merge/VAD → cut WAV
        ↓
SQLite resume + quality metrics
        ↓
wavs/ + metadata.csv/json + rejected.csv + report
        ↓
Validator PASS / WARNING / REJECT
        ↓
verified dataset.zip
```

## Điểm quan trọng

- Output WAV: mono PCM16, chọn 24 kHz / 44.1 kHz / 48 kHz.
- Padding mặc định: `0.15s` trước, `0.20s` sau.
- VAD/silence refinement mặc định **OFF**; chỉ nên bật khi timestamp cần tinh chỉnh.
- Peak/Loudness normalization mặc định **OFF**.
- Nhiều audio: **mỗi audio bắt buộc có đúng một transcript tương ứng và cùng thứ tự**.
- SQLite ghi `source_key`, exact PCM path và sample rate để regenerate không thể lấy nhầm audiobook khác.
- Resume chỉ bỏ qua sample accepted khi WAV thật vẫn tồn tại.
- Nếu transcript/config của cùng source thay đổi, source đó được rebuild thay vì reuse dataset cũ sai cấu hình.
- Preview web dùng WAV thật + HTTP Range, waveform thật từ audio chứ không phải hình giả.
- ZIP export kiểm tra signature, CRC và chỉ đóng gói WAV được `metadata.csv` tham chiếu.

## Windows

### 1. Cài Python 3.10/3.11 và FFmpeg

```powershell
winget install Gyan.FFmpeg
```

Đóng/mở lại terminal rồi kiểm tra:

```powershell
python --version
ffmpeg -version
ffprobe -version
```

### 2. Chạy

Cách nhanh: double-click `run_windows.bat`.

Hoặc:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Mở `http://127.0.0.1:7860`.

## Ghép nhiều file

Hai danh sách phải tương ứng theo index:

```text
Audio                       Transcript
001.mp3                 ↔   001.json
002.mp3                 ↔   002.json
003.mp3                 ↔   003.json
```

Không dùng một transcript cho nhiều audio.

## Output

```text
output_dataset/
├── _temp_pcm/               # cache PCM để resume/regenerate, không export
├── wavs/
│   ├── 000001.wav
│   ├── 000002.wav
│   └── ...
├── metadata.csv             # 000001.wav|Transcript tiếng Việt
├── metadata.json            # source/timestamp/quality metrics
├── rejected.csv
├── dataset_report.json
├── dataset.db               # state/resume/source mapping
└── dataset.zip              # tạo khi Export
```

## Validator

- **PASS**: không phát hiện vấn đề.
- **WARNING**: sample vẫn có thể dùng nhưng nên nghe kiểm tra, ví dụ hơi dài, silence cao hoặc clipping nhẹ.
- **REJECT**: lỗi cấu trúc cần sửa trước khi train, ví dụ thiếu/hỏng WAV, sai sample rate, stereo hoặc không phải PCM16.

Validator còn kiểm tra duplicate filename/text/audio, orphan WAV và metadata lỗi.

## Regenerate sample

Khi sửa text/start/end, tool chỉ sử dụng **exact PCM source** đã ghi trong `dataset.db`. Nếu PCM đó không còn, regenerate sẽ báo lỗi và yêu cầu rebuild source thay vì tự chọn một PCM khác.

Nếu dataset ban đầu có normalization, CLI/web regeneration đọc lại cấu hình trong `dataset_report.json` để giữ cùng thiết lập.

## ZIP export

`dataset.zip` chỉ được trả về sau khi:

1. có `metadata.csv` hợp lệ;
2. mọi WAV được metadata tham chiếu đều tồn tại;
3. ZIP có magic bytes `50 4B 03 04`;
4. CRC `ZipFile.testzip()` pass;
5. số WAV trong ZIP khớp metadata.

Orphan WAV không được đưa vào ZIP.

## Tests / CI

```bash
python -m compileall -q tts_dataset_builder tools tests
python -m unittest discover -s tests -v
npm run lint
npm run build
```

GitHub Actions chạy các kiểm tra trên cho pull request.
