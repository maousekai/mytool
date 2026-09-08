import React, { useRef } from "react";
import {
  UploadCloud,
  FileAudio,
  FileText,
  Sliders,
  Play,
  Clock,
  Volume2,
  CheckCircle,
  XCircle,
  AlertCircle,
  Check,
  RotateCw,
} from "lucide-react";
import {
  AudioFileItem,
  TranscriptFileItem,
  BuildOptions,
  BuildProgressState,
  DatasetReport,
} from "../types";

interface BuilderTabProps {
  audioFiles: AudioFileItem[];
  setAudioFiles: React.Dispatch<React.SetStateAction<AudioFileItem[]>>;
  transcriptFiles: TranscriptFileItem[];
  setTranscriptFiles: React.Dispatch<React.SetStateAction<TranscriptFileItem[]>>;
  options: BuildOptions;
  setOptions: React.Dispatch<React.SetStateAction<BuildOptions>>;
  progress: BuildProgressState;
  onStartBuild: () => void;
  onLoadSample: () => void;
  report: DatasetReport | null;
}

export const BuilderTab: React.FC<BuilderTabProps> = ({
  audioFiles,
  setAudioFiles,
  transcriptFiles,
  setTranscriptFiles,
  options,
  setOptions,
  progress,
  onStartBuild,
  onLoadSample,
  report,
}) => {
  const audioInputRef = useRef<HTMLInputElement>(null);
  const transcriptInputRef = useRef<HTMLInputElement>(null);

  const handleAudioUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const formData = new FormData();
    for (let i = 0; i < e.target.files.length; i++) {
      formData.append("audios", e.target.files[i]);
    }
    try {
      const res = await fetch("/api/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (data.success && data.audioFiles) {
        setAudioFiles((prev) => [...prev, ...data.audioFiles]);
      }
    } catch (err) {
      console.error("Upload error:", err);
    }
  };

  const handleTranscriptUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const formData = new FormData();
    for (let i = 0; i < e.target.files.length; i++) {
      formData.append("transcript", e.target.files[i]);
    }
    try {
      const res = await fetch("/api/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (data.success && data.transcriptFiles) {
        setTranscriptFiles(data.transcriptFiles);
      }
    } catch (err) {
      console.error("Upload error:", err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner / Sample loader */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 sm:p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center justify-center w-2 h-2 rounded-full bg-emerald-400"></span>
            <h2 className="text-base font-semibold text-slate-100">
              Quy trình chuẩn: Cắt audio audiobook thành Dataset TTS chất lượng cao
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-slate-400">
            Hỗ trợ MP3, WAV, M4A, FLAC và transcript JSON, CSV, SRT. Tự động giải mã PCM 1 lần, chống cắt cụt âm, gộp câu ngắn.
          </p>
        </div>
        <button
          id="btn-quick-load-sample"
          onClick={onLoadSample}
          disabled={progress.isBuilding}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs sm:text-sm font-medium transition whitespace-nowrap"
        >
          <FileAudio className="w-4 h-4 text-emerald-400" />
          <span>Tải Audio & Transcript Mẫu</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Input and Parameters */}
        <div className="lg:col-span-7 space-y-6">
          {/* Audio & Transcript Inputs */}
          <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 space-y-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <UploadCloud className="w-4 h-4 text-emerald-400" />
              1. Tải lên Audio và Transcript
            </h3>

            {/* Audio Upload Area */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                File Audio (MP3, WAV, M4A, FLAC) - Có thể chọn nhiều file
              </label>
              <div
                onClick={() => audioInputRef.current?.click()}
                className="border-2 border-dashed border-slate-700 hover:border-emerald-500/60 rounded-xl p-4 text-center cursor-pointer transition bg-slate-950/40 hover:bg-slate-950/70"
              >
                <FileAudio className="w-7 h-7 mx-auto text-slate-400 mb-1.5" />
                <p className="text-xs text-slate-300 font-medium">
                  Nhấn để chọn hoặc kéo thả file audio vào đây
                </p>
                <p className="text-[11px] text-slate-500 mt-0.5">MP3, WAV, M4A, FLAC, OGG, AAC</p>
                <input
                  ref={audioInputRef}
                  type="file"
                  multiple
                  accept="audio/*,.mp3,.wav,.m4a,.flac,.ogg,.aac"
                  className="hidden"
                  onChange={handleAudioUpload}
                />
              </div>

              {/* Audio list */}
              {audioFiles.length > 0 && (
                <div className="mt-2.5 space-y-1.5 max-h-36 overflow-y-auto pr-1">
                  {audioFiles.map((file, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-slate-800/70 border border-slate-700/60 text-xs"
                    >
                      <div className="flex items-center gap-2 truncate">
                        <FileAudio className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        <span className="text-slate-200 truncate">{file.originalName}</span>
                      </div>
                      <span className="text-slate-400 text-[11px] shrink-0 ml-2">{file.sizeMb} MB</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Transcript Upload Area */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                File Transcript có mốc thời gian (JSON, CSV, SRT)
              </label>
              <div
                onClick={() => transcriptInputRef.current?.click()}
                className="border-2 border-dashed border-slate-700 hover:border-emerald-500/60 rounded-xl p-4 text-center cursor-pointer transition bg-slate-950/40 hover:bg-slate-950/70"
              >
                <FileText className="w-7 h-7 mx-auto text-slate-400 mb-1.5" />
                <p className="text-xs text-slate-300 font-medium">
                  Nhấn để chọn file transcript có start, end, text
                </p>
                <p className="text-[11px] text-slate-500 mt-0.5">Định dạng hỗ trợ: .json, .csv, .srt, .tsv</p>
                <input
                  ref={transcriptInputRef}
                  type="file"
                  accept=".json,.csv,.srt,.tsv,.txt"
                  className="hidden"
                  onChange={handleTranscriptUpload}
                />
              </div>

              {/* Transcript list */}
              {transcriptFiles.length > 0 && (
                <div className="mt-2.5 space-y-1.5">
                  {transcriptFiles.map((file, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-slate-800/70 border border-slate-700/60 text-xs"
                    >
                      <div className="flex items-center gap-2 truncate">
                        <FileText className="w-3.5 h-3.5 text-teal-400 shrink-0" />
                        <span className="text-slate-200 truncate">{file.originalName}</span>
                      </div>
                      <span className="text-slate-400 text-[11px] shrink-0 ml-2">{file.sizeKb} KB</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Configuration Parameters */}
          <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 space-y-5">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Sliders className="w-4 h-4 text-emerald-400" />
              2. Cấu hình Cắt & Chuẩn Hóa Âm Thanh
            </h3>

            {/* Target Sample Rate */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-2">
                Target Sample Rate (Mono 16-bit PCM WAV)
              </label>
              <div className="grid grid-cols-3 gap-2.5">
                {[24000, 44100, 48000].map((rate) => (
                  <button
                    key={rate}
                    type="button"
                    onClick={() => setOptions({ ...options, sampleRate: rate as any })}
                    className={`py-2 px-3 rounded-xl text-xs font-semibold border transition ${
                      options.sampleRate === rate
                        ? "bg-emerald-600 text-white border-emerald-500 shadow-sm"
                        : "bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-750"
                    }`}
                  >
                    {rate.toLocaleString()} Hz
                    <span className="block text-[10px] opacity-80 font-normal">
                      {rate === 24000 ? "Chuẩn VITS/XTTS" : rate === 44100 ? "Studio CD" : "High-Def"}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {/* Padding Controls */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Padding Trước (giây)
                </label>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1.0"
                  value={options.paddingBefore}
                  onChange={(e) => setOptions({ ...options, paddingBefore: parseFloat(e.target.value) || 0 })}
                  className="w-full bg-slate-950/70 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-emerald-500"
                />
                <span className="text-[11px] text-slate-500 mt-1 block">Mặc định 0.15s tránh cắt phụ âm đầu</span>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Padding Sau (giây)
                </label>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1.0"
                  value={options.paddingAfter}
                  onChange={(e) => setOptions({ ...options, paddingAfter: parseFloat(e.target.value) || 0 })}
                  className="w-full bg-slate-950/70 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-emerald-500"
                />
                <span className="text-[11px] text-slate-500 mt-1 block">Mặc định 0.20s tránh cụt đuôi câu</span>
              </div>
            </div>

            {/* Duration bounds & Auto merge */}
            <div className="pt-2 border-t border-slate-800 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Min Duration (giây)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0.5"
                    max="10.0"
                    value={options.minDuration}
                    onChange={(e) => setOptions({ ...options, minDuration: parseFloat(e.target.value) || 2.0 })}
                    className="w-full bg-slate-950/70 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Max Duration (giây)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="3.0"
                    max="30.0"
                    value={options.maxDuration}
                    onChange={(e) => setOptions({ ...options, maxDuration: parseFloat(e.target.value) || 12.0 })}
                    className="w-full bg-slate-950/70 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              {/* Auto merge short samples checkbox */}
              <div className="flex items-start gap-2.5 pt-1">
                <input
                  type="checkbox"
                  id="chk-auto-merge"
                  checked={options.autoMergeShort}
                  onChange={(e) => setOptions({ ...options, autoMergeShort: e.target.checked })}
                  className="mt-0.5 rounded border-slate-700 text-emerald-500 focus:ring-0 bg-slate-950"
                />
                <div>
                  <label htmlFor="chk-auto-merge" className="text-xs font-medium text-slate-200 cursor-pointer">
                    Auto merge short samples (Tự động gộp câu quá ngắn)
                  </label>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Gộp các câu ngắn &lt; {options.minDuration}s (như "Không.", "Được.") với câu liền kề nếu khoảng lặng &lt; {options.mergeSilenceThreshold}s và tổng thời lượng &le; {options.maxDuration}s.
                  </p>
                </div>
              </div>

              {/* VAD / Silence Refinement */}
              <div className="flex items-start gap-2.5 pt-1">
                <input
                  type="checkbox"
                  id="chk-refine-vad"
                  checked={options.refineVad}
                  onChange={(e) => setOptions({ ...options, refineVad: e.target.checked })}
                  className="mt-0.5 rounded border-slate-700 text-emerald-500 focus:ring-0 bg-slate-950"
                />
                <div>
                  <label htmlFor="chk-refine-vad" className="text-xs font-medium text-slate-200 cursor-pointer">
                    Refine timestamps using silence/VAD (Dò tìm khoảng lặng ±300ms)
                  </label>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Dò tìm điểm năng lượng thấp nhất quanh mốc cắt để tránh ngắt giữa từ, giữ nguyên văn bản.
                  </p>
                </div>
              </div>

              {/* Normalization options */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                <label className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-950/50 border border-slate-800 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={options.peakNorm}
                    onChange={(e) => setOptions({ ...options, peakNorm: e.target.checked })}
                    className="rounded border-slate-700 text-emerald-500 focus:ring-0 bg-slate-950"
                  />
                  <span className="text-xs text-slate-300">Peak Normalization (-1 dBFS)</span>
                </label>
                <label className="flex items-center gap-2 p-2.5 rounded-xl bg-slate-950/50 border border-slate-800 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={options.loudnessNorm}
                    onChange={(e) => setOptions({ ...options, loudnessNorm: e.target.checked })}
                    className="rounded border-slate-700 text-emerald-500 focus:ring-0 bg-slate-950"
                  />
                  <span className="text-xs text-slate-300">Loudness Norm (-20 LUFS)</span>
                </label>
              </div>

              {/* Output Directory */}
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Thư mục xuất Dataset</label>
                <input
                  type="text"
                  value={options.outputDir}
                  onChange={(e) => setOptions({ ...options, outputDir: e.target.value })}
                  className="w-full bg-slate-950/70 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            {/* Build action button */}
            <button
              id="btn-start-build"
              onClick={onStartBuild}
              disabled={progress.isBuilding || audioFiles.length === 0 || transcriptFiles.length === 0}
              className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold text-sm shadow-lg shadow-emerald-900/30 flex items-center justify-center gap-2 transition disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {progress.isBuilding ? (
                <>
                  <RotateCw className="w-4 h-4 animate-spin" />
                  <span>ĐANG XỬ LÝ & CẮT AUDIO DATASET...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current" />
                  <span>BẮT ĐẦU XỬ LÝ & TẠO DATASET</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Right Column: Real-time Progress & Dataset Summary */}
        <div className="lg:col-span-5 space-y-6">
          {/* Progress Card */}
          <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 space-y-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-emerald-400" />
                Tiến độ xử lý
              </span>
              <span className="text-xs font-normal text-slate-400">
                {progress.percentage.toFixed(1)}%
              </span>
            </h3>

            {/* Progress Bar */}
            <div className="w-full bg-slate-950 rounded-full h-3 overflow-hidden border border-slate-800">
              <div
                className="bg-gradient-to-r from-emerald-500 to-teal-400 h-full transition-all duration-300 rounded-full"
                style={{ width: `${Math.min(100, Math.max(0, progress.percentage))}%` }}
              ></div>
            </div>

            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>
                {progress.total > 0
                  ? `Đang xử lý ${progress.current} / ${progress.total} câu`
                  : progress.message}
              </span>
              {progress.etaSeconds > 0 && <span>ETA: ~{progress.etaSeconds}s</span>}
            </div>

            {/* Current status message */}
            <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/70 text-xs font-mono text-emerald-400/90 truncate">
              {progress.currentFile ? `[${progress.currentFile}] ` : ""}
              {progress.message}
            </div>
          </div>

          {/* Dataset Summary & Metrics */}
          {report ? (
            <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 space-y-4">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <Volume2 className="w-4 h-4 text-emerald-400" />
                  Báo cáo Dataset (Summary)
                </span>
                <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs font-medium border border-emerald-500/30">
                  Hoàn thành
                </span>
              </h3>

              {/* Metric grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">Tổng số câu</span>
                  <span className="text-lg font-bold text-slate-100">{report.summary.total_samples}</span>
                </div>
                <div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-800/50">
                  <span className="text-[11px] text-emerald-400 block">Chấp nhận</span>
                  <span className="text-lg font-bold text-emerald-300">{report.summary.accepted_samples}</span>
                </div>
                <div className="p-3 rounded-xl bg-rose-950/30 border border-rose-800/50">
                  <span className="text-[11px] text-rose-400 block">Loại bỏ</span>
                  <span className="text-lg font-bold text-rose-300">{report.summary.rejected_samples}</span>
                </div>
                <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">Tổng thời lượng</span>
                  <span className="text-sm font-semibold text-slate-200">
                    {report.summary.total_duration_formatted}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">Độ dài TB</span>
                  <span className="text-sm font-semibold text-slate-200">
                    {report.summary.average_duration_seconds}s
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">Min / Max</span>
                  <span className="text-xs font-semibold text-slate-200">
                    {report.summary.min_duration_seconds}s / {report.summary.max_duration_seconds}s
                  </span>
                </div>
              </div>

              {/* Duration Distribution chart */}
              <div className="pt-2 border-t border-slate-800">
                <span className="text-xs font-medium text-slate-300 mb-2 block">
                  Phân bố độ dài câu (Duration Distribution)
                </span>
                <div className="space-y-2">
                  {Object.entries(report.duration_distribution || {}).map(([bin, count]) => {
                    const counts = Object.values(report.duration_distribution || {}) as number[];
                    const maxCount = counts.length > 0 ? Math.max(...counts, 1) : 1;
                    const numCount = Number(count) || 0;
                    const pct = (numCount / maxCount) * 100;
                    return (
                      <div key={bin} className="space-y-1">
                        <div className="flex items-center justify-between text-xs text-slate-400">
                          <span>{bin}</span>
                          <span className="font-mono text-slate-300">{count} câu</span>
                        </div>
                        <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden">
                          <div
                            className="bg-emerald-500 h-full rounded-full"
                            style={{ width: `${pct}%` }}
                          ></div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 text-center text-slate-500 space-y-2">
              <FileAudio className="w-8 h-8 mx-auto text-slate-600" />
              <p className="text-xs text-slate-400">
                Chưa có báo cáo dataset. Chọn audio và transcript rồi nhấn Bắt đầu xử lý.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
