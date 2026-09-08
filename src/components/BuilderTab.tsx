import React, { useRef } from "react";
import { UploadCloud, FileAudio, FileText, Sliders, Play, AlertCircle, CheckCircle, X, RotateCw } from "lucide-react";
import { AudioFileItem, TranscriptFileItem, BuildOptions, BuildProgressState, DatasetReport } from "../types";

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
  audioFiles, setAudioFiles, transcriptFiles, setTranscriptFiles,
  options, setOptions, progress, onStartBuild, onLoadSample, report,
}) => {
  const audioInputRef = useRef<HTMLInputElement>(null);
  const transcriptInputRef = useRef<HTMLInputElement>(null);

  const uploadFiles = async (files: FileList, field: "audios" | "transcript") => {
    const form = new FormData();
    Array.from(files).forEach((f) => form.append(field, f));
    const res = await fetch("/api/upload", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || "Upload failed");
    if (field === "audios") setAudioFiles((prev) => [...prev, ...(data.audioFiles || [])]);
    else setTranscriptFiles((prev) => [...prev, ...(data.transcriptFiles || [])]);
  };

  const pairOk = audioFiles.length > 0 && audioFiles.length === transcriptFiles.length;
  const canBuild = pairOk && !progress.isBuilding && options.minDuration < options.maxDuration && !(options.peakNorm && options.loudnessNorm);

  return (
    <div className="space-y-6">
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="font-semibold text-slate-100">Audio + transcript phải ghép theo cùng thứ tự</h2>
          <p className="text-xs text-slate-400 mt-1">Ví dụ audio 001 ↔ transcript 001, audio 002 ↔ transcript 002. Tool không còn tự lấy transcript đầu tiên cho mọi audio.</p>
        </div>
        <button onClick={onLoadSample} disabled={progress.isBuilding} className="px-4 py-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 text-xs hover:bg-emerald-500/20 disabled:opacity-50">Tải dữ liệu mẫu</button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7 space-y-6">
          <section className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2"><UploadCloud className="w-4 h-4 text-emerald-400"/>1. Audio & Transcript</h3>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-slate-300">Audio (chọn nhiều file)</label>
                <button type="button" onClick={() => audioInputRef.current?.click()} className="mt-2 w-full min-h-28 border-2 border-dashed border-slate-700 hover:border-emerald-500/60 rounded-xl text-xs text-slate-300 flex flex-col items-center justify-center gap-2"><FileAudio className="w-7 h-7 text-emerald-400"/>Chọn MP3/WAV/M4A/FLAC/OGG/AAC</button>
                <input ref={audioInputRef} className="hidden" type="file" multiple accept="audio/*,.mp3,.wav,.m4a,.flac,.ogg,.aac" onChange={async (e) => { if (e.target.files?.length) { try { await uploadFiles(e.target.files, "audios"); } catch (err:any) { alert(err.message); } e.target.value=""; } }}/>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-300">Transcript (chọn đúng số lượng audio)</label>
                <button type="button" onClick={() => transcriptInputRef.current?.click()} className="mt-2 w-full min-h-28 border-2 border-dashed border-slate-700 hover:border-teal-500/60 rounded-xl text-xs text-slate-300 flex flex-col items-center justify-center gap-2"><FileText className="w-7 h-7 text-teal-400"/>Chọn JSON/CSV/SRT/TSV/TXT</button>
                <input ref={transcriptInputRef} className="hidden" type="file" multiple accept=".json,.csv,.srt,.tsv,.txt" onChange={async (e) => { if (e.target.files?.length) { try { await uploadFiles(e.target.files, "transcript"); } catch (err:any) { alert(err.message); } e.target.value=""; } }}/>
              </div>
            </div>

            {(audioFiles.length > 0 || transcriptFiles.length > 0) && (
              <div className="space-y-2">
                <div className={`text-xs rounded-lg p-2 border ${pairOk ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" : "border-amber-500/30 bg-amber-500/10 text-amber-300"}`}>{pairOk ? `✓ ${audioFiles.length} cặp sẵn sàng` : `Cần số lượng bằng nhau: ${audioFiles.length} audio / ${transcriptFiles.length} transcript`}</div>
                <div className="max-h-56 overflow-auto border border-slate-800 rounded-xl divide-y divide-slate-800">
                  {Array.from({ length: Math.max(audioFiles.length, transcriptFiles.length) }).map((_, i) => (
                    <div key={i} className="grid grid-cols-[36px_1fr_1fr] gap-2 p-2 text-[11px] items-center">
                      <span className="text-slate-500 font-mono">{String(i+1).padStart(2,"0")}</span>
                      <div className="min-w-0 flex items-center gap-1"><FileAudio className="w-3 h-3 text-emerald-400 shrink-0"/><span className="truncate text-slate-300">{audioFiles[i]?.originalName || "— thiếu audio —"}</span></div>
                      <div className="min-w-0 flex items-center gap-1"><FileText className="w-3 h-3 text-teal-400 shrink-0"/><span className="truncate text-slate-300">{transcriptFiles[i]?.originalName || "— thiếu transcript —"}</span></div>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2">
                  <button onClick={() => setAudioFiles([])} className="text-[11px] px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"><X className="inline w-3 h-3 mr-1"/>Xóa audio</button>
                  <button onClick={() => setTranscriptFiles([])} className="text-[11px] px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300"><X className="inline w-3 h-3 mr-1"/>Xóa transcript</button>
                </div>
              </div>
            )}
          </section>

          <section className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-5">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2"><Sliders className="w-4 h-4 text-emerald-400"/>2. Cấu hình cắt</h3>
            <div>
              <label className="text-xs text-slate-300">Sample Rate (mono PCM16)</label>
              <div className="grid grid-cols-3 gap-2 mt-2">{[24000,44100,48000].map((rate) => <button key={rate} onClick={() => setOptions({...options, sampleRate: rate as 24000|44100|48000})} className={`py-2 rounded-xl border text-xs ${options.sampleRate===rate ? "bg-emerald-600 border-emerald-500 text-white" : "bg-slate-800 border-slate-700 text-slate-300"}`}>{rate.toLocaleString()} Hz</button>)}</div>
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <NumberField label="Padding trước (s)" value={options.paddingBefore} step={0.05} min={0} max={1} onChange={(v)=>setOptions({...options,paddingBefore:v})}/>
              <NumberField label="Padding sau (s)" value={options.paddingAfter} step={0.05} min={0} max={1} onChange={(v)=>setOptions({...options,paddingAfter:v})}/>
              <NumberField label="Min duration (s)" value={options.minDuration} step={0.5} min={0.5} max={10} onChange={(v)=>setOptions({...options,minDuration:v})}/>
              <NumberField label="Max duration (s)" value={options.maxDuration} step={0.5} min={3} max={30} onChange={(v)=>setOptions({...options,maxDuration:v})}/>
              <NumberField label="Ngưỡng silence để merge (s)" value={options.mergeSilenceThreshold} step={0.05} min={0} max={3} onChange={(v)=>setOptions({...options,mergeSilenceThreshold:v})}/>
              <NumberField label="Target LUFS" value={options.targetLufs} step={1} min={-30} max={-10} onChange={(v)=>setOptions({...options,targetLufs:v})}/>
            </div>
            <CheckField label="Auto merge câu ngắn" checked={options.autoMergeShort} onChange={(v)=>setOptions({...options,autoMergeShort:v})}/>
            <CheckField label="Refine timestamp bằng silence/VAD ±300ms" checked={options.refineVad} onChange={(v)=>setOptions({...options,refineVad:v})}/>
            <div className="grid sm:grid-cols-2 gap-3">
              <CheckField label="Peak normalization -1 dBFS" checked={options.peakNorm} onChange={(v)=>setOptions({...options,peakNorm:v,loudnessNorm:v?false:options.loudnessNorm})}/>
              <CheckField label="Loudness normalization" checked={options.loudnessNorm} onChange={(v)=>setOptions({...options,loudnessNorm:v,peakNorm:v?false:options.peakNorm})}/>
            </div>
            <p className="text-[11px] text-slate-500">Khuyến nghị narration: để cả hai normalization OFF nếu nguồn audio đã đồng đều.</p>
            <div><label className="text-xs text-slate-300">Thư mục output</label><input value={options.outputDir} onChange={(e)=>setOptions({...options,outputDir:e.target.value})} className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs"/></div>
            <button onClick={onStartBuild} disabled={!canBuild} className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-semibold flex items-center justify-center gap-2">{progress.isBuilding ? <RotateCw className="w-4 h-4 animate-spin"/> : <Play className="w-4 h-4"/>}{progress.isBuilding ? "ĐANG XỬ LÝ" : "BẮT ĐẦU XỬ LÝ & TẠO DATASET"}</button>
          </section>
        </div>

        <div className="lg:col-span-5 space-y-6">
          <section className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-3">
            <h3 className="text-sm font-semibold text-slate-300">Tiến độ xử lý</h3>
            <div className="flex justify-between text-xs text-slate-400"><span>{progress.currentFile || "Sẵn sàng"}</span><span>{progress.percentage.toFixed(1)}%</span></div>
            <div className="h-2 bg-slate-950 rounded-full overflow-hidden"><div className="h-full bg-emerald-500 transition-all" style={{width:`${Math.max(0,Math.min(100,progress.percentage))}%`}}/></div>
            <div className="text-xs text-slate-300">{progress.message}</div>
            {progress.error && <div className="p-3 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-300 text-xs flex gap-2"><AlertCircle className="w-4 h-4 shrink-0"/>{progress.error}</div>}
            {progress.recentLogs?.length>0 && <pre className="max-h-44 overflow-auto bg-slate-950 p-3 rounded-xl text-[10px] text-slate-400 whitespace-pre-wrap">{progress.recentLogs.slice(-12).join("\n")}</pre>}
          </section>
          {report && <section className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-4"><h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2"><CheckCircle className="w-4 h-4 text-emerald-400"/>Báo cáo dataset</h3><div className="grid grid-cols-2 gap-2 text-xs"><Metric label="Tổng" value={report.summary.total_samples}/><Metric label="Chấp nhận" value={report.summary.accepted_samples}/><Metric label="Loại" value={report.summary.rejected_samples}/><Metric label="Thời lượng" value={report.summary.total_duration_formatted}/><Metric label="TB" value={`${report.summary.average_duration_seconds}s`}/><Metric label="Min / Max" value={`${report.summary.min_duration_seconds}s / ${report.summary.max_duration_seconds}s`}/></div></section>}
        </div>
      </div>
    </div>
  );
};

const NumberField = ({label,value,onChange,step,min,max}:{label:string,value:number,onChange:(v:number)=>void,step:number,min:number,max:number}) => <div><label className="text-xs text-slate-300">{label}</label><input type="number" value={value} step={step} min={min} max={max} onChange={(e)=>{const v=Number(e.target.value); if(Number.isFinite(v)) onChange(v)}} className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs"/></div>;
const CheckField = ({label,checked,onChange}:{label:string,checked:boolean,onChange:(v:boolean)=>void}) => <label className="flex items-start gap-2 p-2 rounded-lg hover:bg-slate-800/30 text-xs text-slate-300 cursor-pointer"><input type="checkbox" checked={checked} onChange={(e)=>onChange(e.target.checked)} className="mt-0.5"/><span>{label}</span></label>;
const Metric = ({label,value}:{label:string,value:React.ReactNode}) => <div className="p-3 rounded-xl bg-slate-950 border border-slate-800"><div className="text-[10px] text-slate-500">{label}</div><div className="font-semibold text-slate-200 mt-1">{value}</div></div>;
