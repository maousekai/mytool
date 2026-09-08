import React, { useEffect, useMemo, useRef, useState } from "react";
import { Play, Pause, RotateCcw, Volume2, Edit3, Search, RefreshCw } from "lucide-react";
import { DatasetSample, RejectedSample } from "../types";

interface PreviewTabProps {
  samples: DatasetSample[];
  rejected: RejectedSample[];
  outputDir: string;
  onRefresh: () => void;
}

export const PreviewTab: React.FC<PreviewTabProps> = ({ samples, outputDir, onRefresh }) => {
  const [selected, setSelected] = useState<DatasetSample | null>(samples[0] || null);
  const [query, setQuery] = useState("");
  const [editText, setEditText] = useState("");
  const [editStart, setEditStart] = useState(0);
  const [editEnd, setEditEnd] = useState(0);
  const [regenerating, setRegenerating] = useState(false);
  const [message, setMessage] = useState("");
  const [audioVersion, setAudioVersion] = useState(0);
  const [waveform, setWaveform] = useState<number[]>([]);
  const [waveError, setWaveError] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [rate, setRate] = useState(1);

  const audioUrl = selected
    ? `/api/audio/${encodeURIComponent(selected.wav_filename)}?outputDir=${encodeURIComponent(outputDir)}&v=${audioVersion}`
    : "";

  useEffect(() => {
    if (!samples.length) { setSelected(null); return; }
    setSelected((prev) => samples.find((s) => s.wav_filename === prev?.wav_filename) || samples[0]);
  }, [samples]);

  useEffect(() => {
    if (!selected) return;
    setEditText(selected.text);
    setEditStart(selected.actual_start ?? selected.start_time);
    setEditEnd(selected.actual_end ?? selected.end_time);
    setMessage("");
    setCurrentTime(0);
    setDuration(0);
    setPlaying(false);
  }, [selected]);

  useEffect(() => {
    if (!audioUrl) { setWaveform([]); return; }
    const controller = new AbortController();
    let ctx: AudioContext | null = null;
    setWaveError("");
    setWaveform([]);
    (async () => {
      try {
        const res = await fetch(audioUrl, { signal: controller.signal, cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const buf = await res.arrayBuffer();
        ctx = new AudioContext();
        const decoded = await ctx.decodeAudioData(buf.slice(0));
        const data = decoded.getChannelData(0);
        const bars = 64;
        const step = Math.max(1, Math.floor(data.length / bars));
        const values: number[] = [];
        for (let i = 0; i < bars; i++) {
          const start = i * step;
          const end = Math.min(data.length, start + step);
          let peak = 0;
          for (let j = start; j < end; j++) peak = Math.max(peak, Math.abs(data[j]));
          values.push(Math.max(0.04, peak));
        }
        const max = Math.max(...values, 0.001);
        setWaveform(values.map((v) => v / max));
      } catch (e: any) {
        if (e.name !== "AbortError") setWaveError("Không đọc được waveform: " + e.message);
      } finally {
        if (ctx) ctx.close().catch(() => {});
      }
    })();
    return () => controller.abort();
  }, [audioUrl]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? samples.filter((s) => s.text.toLowerCase().includes(q) || s.wav_filename.toLowerCase().includes(q)) : samples;
  }, [samples, query]);

  const progress = duration > 0 ? Math.min(100, (currentTime / duration) * 100) : 0;

  const regenerate = async () => {
    if (!selected) return;
    if (!editText.trim() || editStart < 0 || editEnd <= editStart) {
      alert("Text hoặc timestamp không hợp lệ."); return;
    }
    setRegenerating(true); setMessage("");
    try {
      const res = await fetch("/api/regenerate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outputDir, filename: selected.wav_filename, text: editText, start: editStart, end: editEnd }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || "Regenerate failed");
      setMessage(`✓ Đã cắt lại ${selected.wav_filename} (${Number(data.sample.duration).toFixed(2)}s)`);
      setAudioVersion((v) => v + 1);
      await Promise.resolve(onRefresh());
    } catch (e: any) { alert("Lỗi cắt lại: " + e.message); }
    finally { setRegenerating(false); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <section className="lg:col-span-7 bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2"><Volume2 className="w-4 h-4 text-emerald-400"/>Samples ({filtered.length})</h3>
          <button onClick={onRefresh} className="p-2 rounded-lg bg-slate-800 text-slate-300"><RefreshCw className="w-4 h-4"/></button>
        </div>
        <div className="relative"><Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-500"/><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Tìm text hoặc filename..." className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-9 pr-3 py-2 text-xs"/></div>
        <div className="max-h-[600px] overflow-auto border border-slate-800 rounded-xl divide-y divide-slate-800">
          {!filtered.length && <div className="p-8 text-center text-xs text-slate-500">Chưa có sample trong dataset này.</div>}
          {filtered.map((s)=><button key={s.wav_filename} onClick={()=>setSelected(s)} className={`w-full text-left p-3 text-xs ${selected?.wav_filename===s.wav_filename?"bg-emerald-500/10 border-l-4 border-emerald-400":"hover:bg-slate-800/40"}`}>
            <div className="flex justify-between gap-3"><div className="min-w-0"><div className="flex gap-2 items-center"><span className="font-mono text-emerald-400">{s.wav_filename}</span><span className="text-slate-500">{s.duration.toFixed(2)}s</span><span className="text-slate-500">{s.source_audio || ""}</span></div><p className="mt-1 text-slate-200 line-clamp-2">{s.text}</p></div><span className="shrink-0 text-slate-500 font-mono">{s.quality_score?.toFixed(0) ?? 0}/100</span></div>
          </button>)}
        </div>
      </section>

      <section className="lg:col-span-5 bg-slate-900/80 border border-slate-800 rounded-2xl p-5 space-y-5">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex justify-between"><span className="flex gap-2 items-center"><Edit3 className="w-4 h-4 text-emerald-400"/>Nghe & chỉnh sample</span><span className="font-mono text-emerald-400">{selected?.wav_filename}</span></h3>
        {!selected ? <div className="text-xs text-slate-500">Chọn một sample ở bên trái.</div> : <>
          <div>
            <div className="flex justify-between text-xs text-slate-400 mb-2"><span>Waveform thật từ WAV</span><span className="font-mono">{currentTime.toFixed(2)} / {(duration || selected.duration).toFixed(2)}s</span></div>
            <div className="h-24 bg-slate-950 border border-slate-800 rounded-xl p-3 flex items-center gap-1 relative overflow-hidden">
              <div className="absolute top-0 bottom-0 w-0.5 bg-emerald-400 z-10" style={{left:`${progress}%`}}/>
              {waveform.length ? waveform.map((h,i)=><div key={i} className={`${(i/waveform.length)*100<=progress?"bg-emerald-400":"bg-slate-700"} flex-1 rounded-full`} style={{height:`${Math.max(8,h*100)}%`}}/>) : <div className="w-full text-center text-[11px] text-slate-600">{waveError || "Đang đọc waveform..."}</div>}
            </div>
          </div>
          <audio ref={audioRef} src={audioUrl} preload="metadata" onLoadedMetadata={()=>{if(audioRef.current && Number.isFinite(audioRef.current.duration)) setDuration(audioRef.current.duration)}} onTimeUpdate={()=>audioRef.current&&setCurrentTime(audioRef.current.currentTime)} onEnded={()=>setPlaying(false)} onError={()=>setWaveError("Không tải được WAV từ dataset.")} className="hidden"/>
          <input type="range" min={0} max={duration||selected.duration||1} step={0.01} value={Math.min(currentTime,duration||selected.duration||1)} onChange={(e)=>{const v=Number(e.target.value);setCurrentTime(v);if(audioRef.current)audioRef.current.currentTime=v}} className="w-full accent-emerald-500"/>
          <div className="flex justify-between items-center"><div className="flex gap-2"><button onClick={async()=>{if(!audioRef.current)return;if(playing){audioRef.current.pause();setPlaying(false)}else{audioRef.current.playbackRate=rate;try{await audioRef.current.play();setPlaying(true)}catch{}}}} className="p-2.5 rounded-xl bg-emerald-600 text-white">{playing?<Pause className="w-4 h-4"/>:<Play className="w-4 h-4"/>}</button><button onClick={()=>{if(audioRef.current){audioRef.current.currentTime=0;setCurrentTime(0)}} className="p-2.5 rounded-xl bg-slate-800"><RotateCcw className="w-4 h-4"/></button></div><div className="flex gap-1 text-xs">{[0.8,1,1.2].map((x)=><button key={x} onClick={()=>{setRate(x);if(audioRef.current)audioRef.current.playbackRate=x}} className={`px-2 py-1 rounded ${rate===x?"bg-slate-700 text-emerald-400":"text-slate-500"}`}>{x}x</button>)}</div></div>

          <div className="pt-4 border-t border-slate-800 space-y-3">
            <label className="text-[11px] text-slate-400">Transcript<textarea value={editText} onChange={(e)=>setEditText(e.target.value)} rows={4} className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-xs text-slate-200"/></label>
            <TimeEditor label="Start" value={editStart} setValue={setEditStart}/>
            <TimeEditor label="End" value={editEnd} setValue={setEditEnd}/>
            <div className="text-[11px] text-slate-500">Duration mới: {Math.max(0,editEnd-editStart).toFixed(3)}s. Tool bắt buộc dùng đúng PCM nguồn đã ghi trong database; không đoán file khác.</div>
            <button onClick={regenerate} disabled={regenerating} className="w-full py-2.5 rounded-xl bg-teal-700 hover:bg-teal-600 disabled:opacity-50 text-xs font-semibold">{regenerating?"ĐANG CẮT LẠI...":"CẮT LẠI SAMPLE"}</button>
            {message && <div className="text-xs text-emerald-400">{message}</div>}
          </div>
        </>}
      </section>
    </div>
  );
};

const TimeEditor=({label,value,setValue}:{label:string,value:number,setValue:(v:number)=>void})=><div><div className="flex justify-between items-center"><label className="text-[11px] text-slate-400">{label} Time</label><div className="flex gap-1">{[-0.1,-0.05,0.05,0.1].map((d)=><button key={d} onClick={()=>setValue(Math.max(0,Number((value+d).toFixed(3))))} className="px-1.5 py-1 text-[10px] bg-slate-800 rounded">{d>0?"+":""}{Math.round(d*1000)}ms</button>)}</div></div><input type="number" step={0.01} value={value} onChange={(e)=>{const v=Number(e.target.value);if(Number.isFinite(v))setValue(v)}} className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs"/></div>;
