import React, { useState, useEffect, useCallback } from "react";
import { Navbar } from "./components/Navbar";
import { BuilderTab } from "./components/BuilderTab";
import { PreviewTab } from "./components/PreviewTab";
import { ValidatorTab } from "./components/ValidatorTab";
import { ExportTab } from "./components/ExportTab";
import { LogsTab } from "./components/LogsTab";
import {
  AudioFileItem,
  TranscriptFileItem,
  BuildOptions,
  BuildProgressState,
  DatasetSample,
  RejectedSample,
  DatasetReport,
  SystemStatus,
} from "./types";

export function App() {
  const [activeTab, setActiveTab] = useState<string>("builder");
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [audioFiles, setAudioFiles] = useState<AudioFileItem[]>([]);
  const [transcriptFiles, setTranscriptFiles] = useState<TranscriptFileItem[]>([]);

  const [options, setOptions] = useState<BuildOptions>({
    sampleRate: 24000,
    paddingBefore: 0.15,
    paddingAfter: 0.20,
    refineVad: false,
    minDuration: 2.0,
    maxDuration: 12.0,
    autoMergeShort: true,
    mergeSilenceThreshold: 0.80,
    peakNorm: false,
    loudnessNorm: false,
    targetLufs: -20.0,
    outputDir: "output_dataset",
  });

  const [progress, setProgress] = useState<BuildProgressState>({
    isBuilding: false,
    current: 0,
    total: 0,
    percentage: 0,
    etaSeconds: 0,
    currentFile: "",
    message: "Sẵn sàng",
    error: null,
    report: null,
    recentLogs: [],
  });

  const [samples, setSamples] = useState<DatasetSample[]>([]);
  const [rejected, setRejected] = useState<RejectedSample[]>([]);
  const [report, setReport] = useState<DatasetReport | null>(null);

  useEffect(() => {
    fetch("/api/system-status")
      .then(async (res) => {
        if (!res.ok) throw new Error(await res.text());
        return res.json();
      })
      .then(setSystemStatus)
      .catch((err) => console.error("Error fetching system status:", err));
  }, []);

  const fetchDataset = useCallback(async (dir?: string) => {
    const targetDir = dir || options.outputDir;
    try {
      const res = await fetch(`/api/dataset?outputDir=${encodeURIComponent(targetDir)}`);
      const data = await res.json();
      if (!res.ok || !data.exists) {
        setSamples([]);
        setRejected([]);
        setReport(null);
        return;
      }
      setSamples(Array.isArray(data.samples) ? data.samples : []);
      setRejected(Array.isArray(data.rejected) ? data.rejected : []);
      setReport(data.report || null);
    } catch (err) {
      console.error("Error loading dataset:", err);
      setSamples([]);
      setRejected([]);
      setReport(null);
    }
  }, [options.outputDir]);

  useEffect(() => { fetchDataset(); }, [fetchDataset]);

  useEffect(() => {
    if (!progress.isBuilding) return;
    const timer = setInterval(async () => {
      try {
        const res = await fetch("/api/progress");
        const data: BuildProgressState = await res.json();
        setProgress(data);
        if (!data.isBuilding) {
          if (data.report) setReport(data.report);
          await fetchDataset(options.outputDir);
        }
      } catch (e) {
        console.error("Progress polling error:", e);
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [progress.isBuilding, fetchDataset, options.outputDir]);

  const handleLoadSample = async () => {
    try {
      const res = await fetch("/api/load-sample", { method: "POST" });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || "Không thể tải dữ liệu mẫu.");
      setAudioFiles(data.audioFiles || []);
      setTranscriptFiles(data.transcriptFiles || []);
    } catch (e: any) {
      alert("Lỗi tải mẫu: " + e.message);
    }
  };

  const handleStartBuild = async () => {
    if (!audioFiles.length || !transcriptFiles.length) {
      alert("Vui lòng chọn audio và transcript.");
      return;
    }
    if (audioFiles.length !== transcriptFiles.length) {
      alert(`Cần đúng 1 transcript cho mỗi audio. Hiện có ${audioFiles.length} audio và ${transcriptFiles.length} transcript.`);
      return;
    }
    if (options.minDuration >= options.maxDuration) {
      alert("Min Duration phải nhỏ hơn Max Duration.");
      return;
    }
    if (options.peakNorm && options.loudnessNorm) {
      alert("Chỉ bật một kiểu normalization: Peak hoặc Loudness.");
      return;
    }

    try {
      const res = await fetch("/api/build", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          audioFiles: audioFiles.map((a) => a.path),
          transcriptFiles: transcriptFiles.map((t) => t.path),
          ...options,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || "Lỗi khi bắt đầu build.");
      setSamples([]);
      setRejected([]);
      setReport(null);
      setProgress((prev) => ({
        ...prev,
        isBuilding: true,
        percentage: 0,
        error: null,
        report: null,
        message: "Bắt đầu tiến trình xử lý audio...",
      }));
    } catch (e: any) {
      alert("Không thể bắt đầu build: " + e.message);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-emerald-500/30 selection:text-emerald-200">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        systemStatus={systemStatus}
        onLoadSample={handleLoadSample}
        isBuilding={progress.isBuilding}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === "builder" && (
          <BuilderTab
            audioFiles={audioFiles}
            setAudioFiles={setAudioFiles}
            transcriptFiles={transcriptFiles}
            setTranscriptFiles={setTranscriptFiles}
            options={options}
            setOptions={setOptions}
            progress={progress}
            onStartBuild={handleStartBuild}
            onLoadSample={handleLoadSample}
            report={report}
          />
        )}
        {activeTab === "preview" && (
          <PreviewTab
            samples={samples}
            rejected={rejected}
            outputDir={options.outputDir}
            onRefresh={() => fetchDataset(options.outputDir)}
          />
        )}
        {activeTab === "validator" && <ValidatorTab outputDir={options.outputDir} />}
        {activeTab === "export" && <ExportTab outputDir={options.outputDir} />}
        {activeTab === "logs" && <LogsTab />}
      </main>

      <footer className="border-t border-slate-900 bg-slate-950/80 py-4 text-center text-xs text-slate-500">
        Vietnamese TTS Dataset Builder &bull; Python 3.11 &bull; FFmpeg &bull; LJSpeech-style metadata &bull; Dataset preparation only
      </footer>
    </div>
  );
}

export default App;
