import React, { useState } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RotateCw,
  Award,
  Sparkles,
  Info,
} from "lucide-react";
import { ValidationResult } from "../types";

interface ValidatorTabProps {
  outputDir: string;
}

export const ValidatorTab: React.FC<ValidatorTabProps> = ({ outputDir }) => {
  const [isValidating, setIsValidating] = useState(false);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [targetDir, setTargetDir] = useState(outputDir);

  const handleRunValidation = async () => {
    setIsValidating(true);
    try {
      const res = await fetch("/api/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          outputDir: targetDir,
          sampleRate: 24000,
          minDuration: 2.0,
          maxDuration: 12.0,
        }),
      });
      const data = await res.json();
      setResult(data);
    } catch (e: any) {
      alert("Lỗi khi chạy kiểm định: " + e.message);
    } finally {
      setIsValidating(false);
    }
  };

  const score = result?.summary?.average_quality_score ?? 0;
  const scoreColor =
    score >= 85
      ? "text-emerald-400 border-emerald-500/30 bg-emerald-500/10"
      : score >= 70
      ? "text-amber-400 border-amber-500/30 bg-amber-500/10"
      : "text-rose-400 border-rose-500/30 bg-rose-500/10";

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              Kiểm định Chất lượng Dataset (Dataset Validator)
            </h3>
            <p className="text-xs text-slate-400">
              Tự động quét và phát hiện lỗi âm thanh, audio clipping, trùng lặp transcript, câu rỗng và chấm điểm Quality Score (0–100).
            </p>
          </div>

          <div className="flex items-center gap-3">
            <input
              type="text"
              value={targetDir}
              onChange={(e) => setTargetDir(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
              placeholder="Thư mục dataset..."
            />
            <button
              id="btn-run-validation"
              onClick={handleRunValidation}
              disabled={isValidating}
              className="py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-2 transition whitespace-nowrap disabled:opacity-50 cursor-pointer shadow-sm"
            >
              {isValidating ? (
                <>
                  <RotateCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Đang kiểm định...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>BẮT ĐẦU QUÉT & CHẤM ĐIỂM</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Overview Score Card if result available */}
        {result?.summary && (
          <div className="pt-4 border-t border-slate-800 grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
            {/* Big Score Gauge */}
            <div className="md:col-span-4 p-4 rounded-xl bg-slate-950/70 border border-slate-800 text-center space-y-2">
              <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">
                Điểm Chất Lượng Trung Bình
              </span>
              <div className="flex items-center justify-center gap-1">
                <span className="text-4xl font-black text-slate-100 tracking-tight">
                  {score.toFixed(1)}
                </span>
                <span className="text-slate-500 text-base font-bold">/100</span>
              </div>
              <div className={`inline-block px-3 py-1 rounded-full text-xs font-bold border ${scoreColor}`}>
                {score >= 85 ? "🟢 XUẤT SẮC - SẴN SÀNG FINE-TUNE" : score >= 70 ? "🟡 ĐẠT YÊU CẦU" : "🔴 CẦN KIỂM TRA LẠI"}
              </div>
            </div>

            {/* Checklist summary */}
            <div className="md:col-span-8 grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
              <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800">
                <span className="text-slate-400 text-[11px] block">Tổng số mẫu</span>
                <span className="font-bold text-slate-200">{result.summary.total_checked} câu</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800">
                <span className="text-slate-400 text-[11px] block">Thiếu file WAV</span>
                <span className={`font-bold ${result.summary.missing_wav_files > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                  {result.summary.missing_wav_files}
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800">
                <span className="text-slate-400 text-[11px] block">Trùng lặp Transcript</span>
                <span className={`font-bold ${result.summary.duplicate_transcripts > 0 ? "text-amber-400" : "text-emerald-400"}`}>
                  {result.summary.duplicate_transcripts}
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800">
                <span className="text-slate-400 text-[11px] block">Trùng Audio (Hash)</span>
                <span className={`font-bold ${result.summary.duplicate_audio_files > 0 ? "text-amber-400" : "text-emerald-400"}`}>
                  {result.summary.duplicate_audio_files}
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800">
                <span className="text-slate-400 text-[11px] block">Transcript Rỗng</span>
                <span className={`font-bold ${result.summary.empty_transcripts > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                  {result.summary.empty_transcripts}
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800">
                <span className="text-slate-400 text-[11px] block">Lệch Sample Rate</span>
                <span className={`font-bold ${result.summary.sample_rate_mismatches > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                  {result.summary.sample_rate_mismatches}
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800">
                <span className="text-slate-400 text-[11px] block">Bị Clipping (Vỡ âm)</span>
                <span className={`font-bold ${result.summary.clipped_samples > 0 ? "text-rose-400" : "text-emerald-400"}`}>
                  {result.summary.clipped_samples}
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800">
                <span className="text-slate-400 text-[11px] block">Silence Quá Dài (&gt;40%)</span>
                <span className={`font-bold ${result.summary.high_silence_samples > 0 ? "text-amber-400" : "text-emerald-400"}`}>
                  {result.summary.high_silence_samples}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Detailed Validation Table */}
      {result?.samples && (
        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
            Chi tiết kiểm tra từng mẫu ({result.samples.length})
          </h3>
          <div className="border border-slate-800 rounded-xl overflow-hidden">
            <div className="max-h-[500px] overflow-y-auto divide-y divide-slate-800/60">
              {result.samples.map((item) => (
                <div key={item.filename} className="p-3 text-xs flex items-start justify-between gap-4 hover:bg-slate-800/40">
                  <div className="space-y-1 min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-emerald-400 font-semibold">{item.filename}</span>
                      <span className="text-slate-400 text-[11px]">{item.duration.toFixed(2)}s</span>
                      <span className="text-slate-500 text-[11px]">{item.sample_rate} Hz</span>
                      {item.peak_db !== undefined && (
                        <span className="text-slate-500 text-[11px]">Peak: {item.peak_db.toFixed(1)} dB</span>
                      )}
                    </div>
                    <p className="text-slate-200">{item.text}</p>
                    {item.issues.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {item.issues.map((iss, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 rounded text-[10px] font-medium bg-rose-950/60 text-rose-300 border border-rose-800/60"
                          >
                            {iss}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="shrink-0 text-right space-y-1">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-[10px] font-semibold ${
                        item.status === "PERFECT" || item.status === "GOOD"
                          ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                          : "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                      }`}
                    >
                      {item.status}
                    </span>
                    <div className="font-mono font-bold text-slate-200">
                      {item.quality_score.toFixed(0)}/100
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
