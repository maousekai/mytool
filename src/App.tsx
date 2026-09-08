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

  // File uploads
  const [audioFiles, setAudioFiles] = useState<AudioFileItem[]>([]);
  const [transcriptFiles, setTranscriptFiles] = useState<TranscriptFileItem[]>([]);

  // Build Options
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

  // Build Progress
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

  // Dataset items
  const [samples, setSamples] = useState<DatasetSample[]>([]);
  const [rejected, setRejected] = useState<RejectedSample[]>([]);
  const [report, setReport] = useState<DatasetReport | null>(null);

  // Fetch system status
  useEffect(() => {
    fetch("/api/system-status")
      .then((res) => res.json())
      .then((data) => setSystemStatus(data))
      .catch((err) => console.error("Error fetching system status:", err));
  }, []);

  // Fetch dataset records
  const fetchDataset = useCallback(async (dir?: string) => {
    const targetDir = dir || options.outputDir;
    try {
      const res = await fetch(`/api/dataset?outputDir=${encodeURIComponent(targetDir)}`);
      const data = await res.json();
      if (data.exists) {
        setSamples(data.samples || []);
        setRejected(data.rejected || []);
        if (data.report) setReport(data.report);
      } else {
        // Check sample_output fallback if default output is empty
        const fallbackRes = await fetch("/api/dataset?outputDir=sample_output");
        const fallbackData = await fallbackRes.json();
        if (fallbackData.exists && fallbackData.samples?.length > 0) {
          setSamples(fallbackData.samples || []);
          setRejected(fallbackData.rejected || []);
          if (fallbackData.report) setReport(fallbackData.report);
        }
      }
    } catch (err) {
      console.error("Error loading dataset:", err);
    }
  }, [options.outputDir]);

  useEffect(() => {
    fetchDataset();
  }, [fetchDataset]);

  // Polling for build progress
  useEffect(() => {
    let timer: any;
    if (progress.isBuilding) {
      timer = setInterval(async () => {
        try {
          const res = await fetch("/api/progress");
          const data: BuildProgressState = await res.json();
          setProgress(data);

          if (!data.isBuilding && data.report) {
            setReport(data.report);
            fetchDataset();
          }
        } catch (e) {
          console.error("Progress polling error:", e);
        }
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [progress.isBuilding, fetchDataset]);

  // Load sample dataset
  const handleLoadSample = async () => {
    try {
      const res = await fetch("/api/load-sample", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        setAudioFiles(data.audioFiles);
        setTranscriptFiles(data.transcriptFiles);
      } else {
        alert(data.error || "Không thể tải dữ liệu mẫu.");
      }
    } catch (e: any) {
      alert("Lỗi tải mẫu: " + e.message);
    }
  };

  // Start build process
  const handleStartBuild = async () => {
    if (audioFiles.length === 0 || transcriptFiles.length === 0) {
      alert("Vui lòng tải lên hoặc chọn ít nhất 1 file audio và 1 file transcript!");
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
      if (data.success) {
        setProgress((prev) => ({
          ...prev,
          isBuilding: true,
          percentage: 0,
          message: "Bắt đầu tiến trình xử lý audio...",
        }));
      } else {
        alert(data.error || "Lỗi khi bắt đầu build.");
      }
    } catch (e: any) {
      alert("Lỗi kết nối: " + e.message);
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

        {activeTab === "validator" && (
          <ValidatorTab outputDir={options.outputDir} />
        )}

        {activeTab === "export" && (
          <ExportTab outputDir={options.outputDir} />
        )}

        {activeTab === "logs" && <LogsTab />}
      </main>

      <footer className="border-t border-slate-900 bg-slate-950/80 py-4 text-center text-xs text-slate-500">
        Vietnamese TTS Dataset Builder &bull; Python 3.11 &bull; FFmpeg &bull; Chuẩn LJSpeech &bull; Sẵn sàng cho VITS, XTTS v2, F5-TTS, StyleTTS 2
      </footer>
    </div>
  );
}

export default App;
