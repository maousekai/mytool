import React, { useEffect, useState } from "react";
import { ShieldCheck, RotateCw, Sparkles, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { ValidationResult } from "../types";

interface ValidatorTabProps { outputDir: string; }

export const ValidatorTab: React.FC<ValidatorTabProps> = ({ outputDir }) => {
  const [isValidating, setIsValidating] = useState(false);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [targetDir, setTargetDir] = useState(outputDir);

  useEffect(() => setTargetDir(outputDir), [outputDir]);

  const run = async () => {
    setIsValidating(true);
    try {
      const res = await fetch("/api/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outputDir: targetDir, sampleRate: 24000, minDuration: 2, maxDuration: 12 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Validation failed");
      setResult(data);
    } catch (e: any) {
      alert("Lỗi kiểm định: " + e.message);
      setResult(null);
    } finally { setIsValidating(false); }
  };

  const s = result?.summary;
  const ready = !!result?.ready_for_training;

  return (
    <div className="space-y-6">
      <section className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold flex items-center gap-2"><ShieldCheck className="w-5 h-5 text-emerald-400"/>Kiểm định Dataset</h3>
            <p className="text-xs text-slate-400 mt-1">REJECT = lỗi cấu trúc/format cần sửa. WARNING = vẫn dùng được nhưng nên nghe kiểm tra. PASS = không phát hiện vấn đề.</p>
          </div>
          <div className="flex gap-2">
            <input value={targetDir} onChange={(e)=>setTargetDir(e.target.value)} className="bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs"/>
            <button onClick={run} disabled={isValidating} className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-xs font-semibold flex items-center gap-2">{isValidating?<RotateCw className="w-4 h-4 animate-spin"/>:<Sparkles className="w-4 h-4"/>}QUÉT DATASET</button>
          </div>
        </div>

        {result?.error && <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">{result.error}</div>}
        {s && <>
          <div className={`p-4 rounded-xl border ${ready ? "bg-emerald-500/10 border-emerald-500/30" : "bg-amber-500/10 border-amber-500/30"}`}>
            <div className="flex items-center gap-2 font-semibold">{ready ? <CheckCircle2 className="w-5 h-5 text-emerald-400"/> : <AlertTriangle className="w-5 h-5 text-amber-400"/>}<span>{ready ? "Dataset không có lỗi cấu trúc bắt buộc" : "Dataset còn lỗi cần xử lý trước khi train"}</span></div>
            <div className="text-xs text-slate-400 mt-1">Điểm trung bình: {s.average_quality_score.toFixed(1)}/100. Warning không tự động loại sample.</div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <Metric label="Tổng" value={s.total_checked}/><Metric label="PASS" value={s.pass_samples} tone="good"/><Metric label="WARNING" value={s.warning_samples} tone="warn"/><Metric label="REJECT" value={s.reject_samples} tone="bad"/>
            <Metric label="Thiếu WAV" value={s.missing_wav_files}/><Metric label="Metadata lỗi" value={s.malformed_metadata_lines}/><Metric label="Orphan WAV" value={s.orphan_wav_files}/><Metric label="Sample rate sai" value={s.sample_rate_mismatches}/>
            <Metric label="PCM width sai" value={s.sample_width_mismatches}/><Metric label="Stereo" value={s.channel_mismatches}/><Metric label="Clipping" value={s.clipped_samples}/><Metric label="Silence cao" value={s.high_silence_samples}/>
          </div>
        </>}
      </section>

      {result?.samples && result.samples.length > 0 && <section className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
        <h3 className="text-sm uppercase tracking-wider text-slate-400 font-semibold">Chi tiết ({result.samples.length})</h3>
        <div className="max-h-[600px] overflow-auto border border-slate-800 rounded-xl divide-y divide-slate-800">
          {result.samples.map((item)=><div key={`${item.id}-${item.filename}`} className="p-3 text-xs flex gap-4 justify-between">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap gap-2 items-center"><span className="font-mono text-emerald-400">{item.filename}</span><span className="text-slate-500">{item.duration.toFixed(2)}s</span><span className="text-slate-500">{item.sample_rate || 0}Hz</span><span className="text-slate-500">{item.sample_width_bits || 0}bit</span></div>
              <p className="text-slate-200 mt-1">{item.text}</p>
              {item.issues.length>0 && <div className="flex flex-wrap gap-1 mt-2">{item.issues.map((x,i)=><span key={i} className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">{x}</span>)}</div>}
            </div>
            <div className="shrink-0 text-right"><Status status={item.status}/><div className="font-mono text-slate-300 mt-1">{item.quality_score.toFixed(0)}/100</div></div>
          </div>)}
        </div>
      </section>}
    </div>
  );
};

const Metric=({label,value,tone}:{label:string,value:number,tone?:"good"|"warn"|"bad"})=><div className="p-3 bg-slate-950 border border-slate-800 rounded-xl"><div className="text-[10px] text-slate-500">{label}</div><div className={`font-bold mt-1 ${tone==="good"?"text-emerald-400":tone==="warn"?"text-amber-400":tone==="bad"?"text-rose-400":"text-slate-200"}`}>{value}</div></div>;
const Status=({status}:{status:"PASS"|"WARNING"|"REJECT"})=>status==="PASS"?<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300"><CheckCircle2 className="w-3 h-3"/>PASS</span>:status==="WARNING"?<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-500/20 text-amber-300"><AlertTriangle className="w-3 h-3"/>WARNING</span>:<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-rose-500/20 text-rose-300"><XCircle className="w-3 h-3"/>REJECT</span>;
