import React, { useState } from "react";
import { Download, FileArchive, FolderTree, Terminal, Copy, Check, Loader2, CheckCircle2, XCircle } from "lucide-react";

interface ExportTabProps { outputDir: string; }
type DownloadState = { kind: "idle"|"loading"|"ok"|"error"; message: string };

export const ExportTab: React.FC<ExportTabProps> = ({ outputDir }) => {
  const [copied, setCopied] = useState<string|null>(null);
  const [datasetState, setDatasetState] = useState<DownloadState>({kind:"idle",message:""});
  const [appState, setAppState] = useState<DownloadState>({kind:"idle",message:""});

  const copy = async (text:string,id:string) => {
    await navigator.clipboard.writeText(text);
    setCopied(id); setTimeout(()=>setCopied(null),1800);
  };

  const verifiedDownload = async (endpoint:string, filename:string, setter:(s:DownloadState)=>void) => {
    setter({kind:"loading",message:"Đang tạo và kiểm tra ZIP..."});
    try {
      const res = await fetch(endpoint, { cache:"no-store" });
      if (!res.ok) {
        const body = await res.text();
        let msg = body;
        try { msg = JSON.parse(body).error || body; } catch {}
        throw new Error(msg || `HTTP ${res.status}`);
      }
      const buf = await res.arrayBuffer();
      const bytes = new Uint8Array(buf);
      if (bytes.length < 4 || bytes[0]!==0x50 || bytes[1]!==0x4b || bytes[2]!==0x03 || bytes[3]!==0x04) {
        throw new Error("Server không trả ZIP hợp lệ (thiếu signature PK 03 04). File không được lưu.");
      }
      const blob = new Blob([buf], {type:"application/zip"});
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href=url; a.download=filename; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
      setter({kind:"ok",message:`ZIP hợp lệ • ${(bytes.length/1048576).toFixed(2)} MB • đã bắt đầu tải`});
    } catch(e:any) {
      setter({kind:"error",message:e.message || "Download failed"});
    }
  };

  return <div className="space-y-6">
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <DownloadCard icon={<FileArchive className="w-6 h-6"/>} title="Xuất Dataset (dataset.zip)"
        text="Chỉ đóng gói WAV được metadata.csv tham chiếu; backend kiểm tra signature, CRC và số lượng WAV. Frontend kiểm tra magic bytes lần nữa trước khi lưu."
        button="TẢI DATASET.ZIP" state={datasetState}
        onClick={()=>verifiedDownload(`/api/export-dataset?outputDir=${encodeURIComponent(outputDir)}`,"dataset.zip",setDatasetState)}/>
      <DownloadCard icon={<Terminal className="w-6 h-6"/>} title="Windows Local Source (.ZIP)"
        text="Gói Windows được tạo mới từ source hiện tại mỗi lần tải, không dùng file ZIP dựng sẵn đã cũ. Bao gồm app.py, run_windows.bat và requirements.txt."
        button="TẢI WINDOWS LOCAL (.ZIP)" state={appState}
        onClick={()=>verifiedDownload("/api/export-python-pkg","Vietnamese_TTS_Dataset_Builder_Windows.zip",setAppState)}/>
    </div>

    <section className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 space-y-4">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2"><FolderTree className="w-4 h-4 text-emerald-400"/>Chạy Local trên Windows</h3>
      <CommandStep title="1. Cài FFmpeg" command="winget install Gyan.FFmpeg" id="ff" copied={copied} copy={copy}/>
      <CommandStep title="2. Cài thư viện" command="python -m pip install -r requirements.txt" id="pip" copied={copied} copy={copy}/>
      <CommandStep title="3. Khởi chạy" command="python app.py" id="run" copied={copied} copy={copy}/>
      <p className="text-xs text-slate-500">Hoặc nhấp đôi <code className="text-emerald-400">run_windows.bat</code>. UI local mở tại <code className="text-emerald-400">http://127.0.0.1:7860</code>.</p>
    </section>

    <section className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 space-y-3">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Dataset đầu ra</h3>
      <pre className="p-4 rounded-xl bg-slate-950 text-slate-300 font-mono text-xs overflow-x-auto border border-slate-800 leading-relaxed">{`output_dataset/
├── wavs/
│   ├── 000001.wav          # mono PCM16 @ sample rate đã chọn
│   └── ...
├── metadata.csv            # filename.wav|transcript
├── metadata.json           # timestamps + metrics + source tracking
├── rejected.csv
├── dataset.db              # resume / exact PCM source mapping
└── dataset_report.json`}</pre>
    </section>
  </div>;
};

const DownloadCard=({icon,title,text,button,state,onClick}:{icon:React.ReactNode,title:string,text:string,button:string,state:DownloadState,onClick:()=>void})=><div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 space-y-4 flex flex-col justify-between"><div className="space-y-2"><div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">{icon}</div><h3 className="font-semibold text-slate-100">{title}</h3><p className="text-xs text-slate-400 leading-relaxed">{text}</p></div><div className="space-y-2"><button onClick={onClick} disabled={state.kind==="loading"} className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center justify-center gap-2">{state.kind==="loading"?<Loader2 className="w-4 h-4 animate-spin"/>:<Download className="w-4 h-4"/>}{button}</button>{state.message&&<div className={`text-[11px] flex gap-1.5 items-start ${state.kind==="error"?"text-rose-400":state.kind==="ok"?"text-emerald-400":"text-slate-400"}`}>{state.kind==="error"?<XCircle className="w-3.5 h-3.5 shrink-0"/>:state.kind==="ok"?<CheckCircle2 className="w-3.5 h-3.5 shrink-0"/>:null}<span>{state.message}</span></div>}</div></div>;
const CommandStep=({title,command,id,copied,copy}:{title:string,command:string,id:string,copied:string|null,copy:(t:string,id:string)=>void})=><div className="p-3 rounded-xl bg-slate-950 border border-slate-800"><div className="flex justify-between items-center"><span className="text-xs font-semibold text-emerald-400">{title}</span><button onClick={()=>copy(command,id)} className="text-[11px] text-slate-400 flex gap-1 items-center">{copied===id?<Check className="w-3 h-3 text-emerald-400"/>:<Copy className="w-3 h-3"/>}{copied===id?"Đã chép":"Sao chép"}</button></div><code className="block mt-2 p-2 rounded bg-slate-900 text-emerald-300 text-[11px]">{command}</code></div>;
