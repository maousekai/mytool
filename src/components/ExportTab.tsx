import React, { useState } from "react";
import {
  Download,
  FileArchive,
  FolderTree,
  Terminal,
  ExternalLink,
  CheckCircle,
  Copy,
  Check,
} from "lucide-react";

interface ExportTabProps {
  outputDir: string;
}

export const ExportTab: React.FC<ExportTabProps> = ({ outputDir }) => {
  const [copiedCmd, setCopiedCmd] = useState<string | null>(null);

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCmd(id);
    setTimeout(() => setCopiedCmd(null), 2000);
  };

  return (
    <div className="space-y-6">
      {/* 2 Big Download Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Card 1: Export Dataset ZIP */}
        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 space-y-4 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <FileArchive className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-slate-100">
              Xuất Dataset Chuẩn (dataset.zip)
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Tải toàn bộ bộ dữ liệu đã cắt bao gồm thư mục <code className="text-emerald-400">wavs/</code>, file <code className="text-emerald-400">metadata.csv</code> (chuẩn LJSpeech), <code className="text-emerald-400">metadata.json</code>, <code className="text-rose-400">rejected.csv</code>, và <code className="text-emerald-400">dataset_report.json</code>.
            </p>
          </div>

          <a
            id="btn-download-dataset-zip"
            href={`/api/export-dataset?outputDir=${encodeURIComponent(outputDir)}`}
            download="dataset.zip"
            className="w-full py-3 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center justify-center gap-2 transition shadow-md shadow-emerald-950/50"
          >
            <Download className="w-4 h-4" />
            <span>TẢI VỀ DATASET.ZIP</span>
          </a>
        </div>

        {/* Card 2: Export Standalone Windows Python App */}
        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 space-y-4 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="w-12 h-12 rounded-xl bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-400">
              <Terminal className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-slate-100">
              Tải Trọn Bộ Mã Nguồn Windows Local (.ZIP)
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Tải trọn bộ ứng dụng Python độc lập kèm file <code className="text-teal-400">run_windows.bat</code>, <code className="text-teal-400">app.py</code> (Gradio Web UI), <code className="text-teal-400">requirements.txt</code>, và dữ liệu mẫu. Nhấp đúp chuột là chạy ngay trên Windows mà không cần cloud.
            </p>
          </div>

          <a
            id="btn-download-python-app"
            href="/api/export-python-pkg"
            download="Vietnamese_TTS_Dataset_Builder_Windows.zip"
            className="w-full py-3 px-4 rounded-xl bg-teal-600 hover:bg-teal-500 text-white font-semibold text-xs flex items-center justify-center gap-2 transition shadow-md shadow-teal-950/50"
          >
            <Download className="w-4 h-4" />
            <span>TẢI MÃ NGUỒN WINDOWS LOCAL (.ZIP)</span>
          </a>
        </div>
      </div>

      {/* Guide: Running on Local Windows */}
      <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 space-y-4">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
          <FolderTree className="w-4 h-4 text-emerald-400" />
          Hướng dẫn Chạy Local trên Windows
        </h3>

        <div className="space-y-3 text-xs text-slate-300">
          <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-emerald-400">Bước 1: Cài đặt FFmpeg trên Windows</span>
              <button
                onClick={() => copyToClipboard("winget install Gyan.FFmpeg", "cmd1")}
                className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1"
              >
                {copiedCmd === "cmd1" ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copiedCmd === "cmd1" ? "Đã chép" : "Sao chép lệnh"}</span>
              </button>
            </div>
            <p className="text-slate-400">Mở PowerShell (Run as Administrator) và gõ:</p>
            <code className="block p-2 rounded bg-slate-900 text-emerald-300 font-mono text-[11px]">
              winget install Gyan.FFmpeg
            </code>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-emerald-400">Bước 2: Cài đặt thư viện Python</span>
              <button
                onClick={() => copyToClipboard("pip install -r requirements.txt", "cmd2")}
                className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1"
              >
                {copiedCmd === "cmd2" ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copiedCmd === "cmd2" ? "Đã chép" : "Sao chép lệnh"}</span>
              </button>
            </div>
            <p className="text-slate-400">Giải nén file ZIP, mở thư mục và chạy:</p>
            <code className="block p-2 rounded bg-slate-900 text-emerald-300 font-mono text-[11px]">
              pip install -r requirements.txt
            </code>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-emerald-400">Bước 3: Khởi chạy ứng dụng</span>
              <button
                onClick={() => copyToClipboard("python app.py", "cmd3")}
                className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1"
              >
                {copiedCmd === "cmd3" ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copiedCmd === "cmd3" ? "Đã chép" : "Sao chép lệnh"}</span>
              </button>
            </div>
            <p className="text-slate-400">Nhấp đúp chuột vào file <strong className="text-slate-200">run_windows.bat</strong> hoặc gõ:</p>
            <code className="block p-2 rounded bg-slate-900 text-emerald-300 font-mono text-[11px]">
              python app.py
            </code>
            <p className="text-slate-400">Trình duyệt sẽ tự động mở tại: <span className="text-emerald-400 font-mono">http://127.0.0.1:7860</span></p>
          </div>
        </div>
      </div>

      {/* Dataset Structure Reference */}
      <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 space-y-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Cấu trúc Thư mục Dataset Đầu Ra
        </h3>
        <pre className="p-4 rounded-xl bg-slate-950 text-slate-300 font-mono text-xs overflow-x-auto border border-slate-800 leading-relaxed">
{`output_dataset/
├── wavs/
│   ├── 000001.wav          # 16-bit PCM s16le Mono 24,000 Hz
│   ├── 000002.wav
│   └── 000003.wav
├── metadata.csv            # 000001.wav|Ta mỗi ngày nhận được một hệ thống mới.
├── metadata.json           # Chi tiết mốc thời gian, duration, metrics, quality score
├── rejected.csv            # Các câu bị loại kèm lý do chi tiết
├── dataset.db              # SQLite Database lưu tiến độ (Resume capability)
└── dataset_report.json     # Thống kê tổng quan và phân bố độ dài câu`}
        </pre>
      </div>
    </div>
  );
};
