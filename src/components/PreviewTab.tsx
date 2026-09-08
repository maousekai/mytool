import React, { useState, useRef, useEffect } from "react";
import {
  Play,
  Pause,
  RotateCcw,
  Volume2,
  Edit3,
  CheckCircle,
  AlertTriangle,
  Search,
  Check,
  RefreshCw,
} from "lucide-react";
import { DatasetSample, RejectedSample } from "../types";

interface PreviewTabProps {
  samples: DatasetSample[];
  rejected: RejectedSample[];
  outputDir: string;
  onRefresh: () => void;
}

export const PreviewTab: React.FC<PreviewTabProps> = ({
  samples,
  rejected,
  outputDir,
  onRefresh,
}) => {
  const [selectedSample, setSelectedSample] = useState<DatasetSample | null>(
    samples.length > 0 ? samples[0] : null
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState<"all" | "accepted" | "rejected">("all");

  // Editable fields for regeneration
  const [editText, setEditText] = useState("");
  const [editStart, setEditStart] = useState<number>(0);
  const [editEnd, setEditEnd] = useState<number>(0);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [regenSuccessMsg, setRegenSuccessMsg] = useState("");

  // Audio player state
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [audioDuration, setAudioDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1.0);

  // When a sample is selected, populate edit fields
  useEffect(() => {
    if (selectedSample) {
      setEditText(selectedSample.text);
      setEditStart(selectedSample.actual_start ?? selectedSample.start_time);
      setEditEnd(selectedSample.actual_end ?? selectedSample.end_time);
      setRegenSuccessMsg("");
      setIsPlaying(false);
      setCurrentTime(0);
    }
  }, [selectedSample]);

  // Keep selectedSample valid if samples update
  useEffect(() => {
    if (samples.length > 0 && !selectedSample) {
      setSelectedSample(samples[0]);
    }
  }, [samples, selectedSample]);

  const filteredSamples = samples.filter((s) => {
    const matchesSearch =
      s.text.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.wav_filename.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter =
      filterStatus === "all" ||
      (filterStatus === "accepted" && s.status === "accepted") ||
      (filterStatus === "rejected" && s.status === "rejected");
    return matchesSearch && matchesFilter;
  });

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setCurrentTime(val);
    if (audioRef.current) {
      audioRef.current.currentTime = val;
    }
  };

  const handleRateChange = (rate: number) => {
    setPlaybackRate(rate);
    if (audioRef.current) {
      audioRef.current.playbackRate = rate;
    }
  };

  const handleRegenerate = async () => {
    if (!selectedSample) return;
    setIsRegenerating(true);
    setRegenSuccessMsg("");

    try {
      const res = await fetch("/api/regenerate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          outputDir,
          filename: selectedSample.wav_filename,
          text: editText,
          start: editStart,
          end: editEnd,
        }),
      });
      const data = await res.json();
      if (data.success && data.sample) {
        setRegenSuccessMsg(
          `Đã cắt lại thành công: ${data.sample.wav_filename} (${data.sample.duration.toFixed(2)}s)!`
        );
        onRefresh();
        // Force audio reload
        if (audioRef.current) {
          audioRef.current.load();
        }
      } else {
        alert(data.error || "Lỗi khi cắt lại sample.");
      }
    } catch (e: any) {
      alert("Lỗi kết nối: " + e.message);
    } finally {
      setIsRegenerating(false);
    }
  };

  // Simulated synthetic waveform bars based on duration and audio metrics
  const renderWaveform = () => {
    const barCount = 48;
    const progressPct = audioDuration > 0 ? (currentTime / audioDuration) * 100 : 0;

    return (
      <div className="h-24 bg-slate-950/80 rounded-xl p-3 flex items-center justify-between gap-1 border border-slate-800/80 relative overflow-hidden">
        {/* Playhead line */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-emerald-400 z-10 pointer-events-none transition-all duration-75"
          style={{ left: `${progressPct}%` }}
        ></div>

        {Array.from({ length: barCount }).map((_, i) => {
          const ratio = i / barCount;
          // Seed height pseudo-randomly for aesthetic visual waveform
          const height = Math.min(
            100,
            Math.max(
              15,
              Math.sin(i * 0.45) * 35 +
                Math.cos(i * 0.9) * 25 +
                Math.sin(i * 1.5) * 20 +
                40
            )
          );
          const isPassed = (i / barCount) * 100 <= progressPct;

          return (
            <div
              key={i}
              className={`flex-1 rounded-full transition-all duration-150 ${
                isPassed ? "bg-emerald-400" : "bg-slate-700/60 hover:bg-slate-600"
              }`}
              style={{ height: `${height}%` }}
            ></div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Interactive Table of Samples */}
        <div className="lg:col-span-7 bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Volume2 className="w-4 h-4 text-emerald-400" />
              Danh sách Samples ({filteredSamples.length})
            </h3>
            <div className="flex items-center gap-2">
              <button
                onClick={onRefresh}
                className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition text-xs flex items-center gap-1"
                title="Làm mới bảng"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Làm mới</span>
              </button>
            </div>
          </div>

          {/* Search and Filters */}
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
              <input
                type="text"
                placeholder="Tìm theo nội dung câu hoặc tên file..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-slate-950/70 border border-slate-700/70 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
              />
            </div>
            <div className="flex items-center gap-1 bg-slate-950/70 border border-slate-800 rounded-xl p-1">
              {(["all", "accepted", "rejected"] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setFilterStatus(mode)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium capitalize transition ${
                    filterStatus === mode
                      ? "bg-slate-800 text-emerald-400 font-semibold"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {mode === "all" ? "Tất cả" : mode === "accepted" ? "Hợp lệ" : "Bị loại"}
                </button>
              ))}
            </div>
          </div>

          {/* Table */}
          <div className="border border-slate-800 rounded-xl overflow-hidden">
            <div className="max-h-[460px] overflow-y-auto divide-y divide-slate-800/60">
              {filteredSamples.length === 0 ? (
                <div className="p-8 text-center text-xs text-slate-500">
                  Không tìm thấy sample nào phù hợp.
                </div>
              ) : (
                filteredSamples.map((sample) => {
                  const isSelected = selectedSample?.wav_filename === sample.wav_filename;
                  return (
                    <div
                      key={sample.wav_filename}
                      onClick={() => setSelectedSample(sample)}
                      className={`p-3 text-xs cursor-pointer transition flex items-start justify-between gap-3 ${
                        isSelected
                          ? "bg-emerald-500/10 border-l-4 border-emerald-400"
                          : "hover:bg-slate-800/40 bg-slate-900/40"
                      }`}
                    >
                      <div className="space-y-1 min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-emerald-400 font-medium">
                            {sample.wav_filename}
                          </span>
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300">
                            {sample.duration.toFixed(2)}s
                          </span>
                          <span className="text-[10px] font-mono text-slate-500">
                            [{sample.actual_start?.toFixed(2)}s - {sample.actual_end?.toFixed(2)}s]
                          </span>
                        </div>
                        <p className="text-slate-200 text-xs leading-relaxed line-clamp-2">
                          {sample.text}
                        </p>
                      </div>

                      <div className="shrink-0 text-right space-y-1">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[10px] font-medium ${
                            sample.status === "accepted"
                              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                              : "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                          }`}
                        >
                          {sample.status === "accepted" ? "ACCEPTED" : "REJECTED"}
                        </span>
                        <div className="text-[11px] text-slate-400 font-mono">
                          Score: {sample.quality_score?.toFixed(0) ?? 100}/100
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Right: Audio Player & Waveform & Regeneration */}
        <div className="lg:col-span-5 bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 space-y-5">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Edit3 className="w-4 h-4 text-emerald-400" />
              Nghe & Tinh chỉnh Mẫu
            </span>
            {selectedSample && (
              <span className="font-mono text-xs text-emerald-400">
                {selectedSample.wav_filename}
              </span>
            )}
          </h3>

          {selectedSample ? (
            <div className="space-y-4">
              {/* Waveform Visualization */}
              <div>
                <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
                  <span>Dạng sóng Audio (Waveform)</span>
                  <span className="font-mono">
                    {currentTime.toFixed(2)}s / {(audioDuration || selectedSample.duration).toFixed(2)}s
                  </span>
                </div>
                {renderWaveform()}
              </div>

              {/* HTML5 Audio Element & Custom Controls */}
              <audio
                ref={audioRef}
                src={`/api/audio/${selectedSample.wav_filename}?outputDir=${encodeURIComponent(outputDir)}`}
                onTimeUpdate={() => {
                  if (audioRef.current) {
                    setCurrentTime(audioRef.current.currentTime);
                  }
                }}
                onLoadedMetadata={() => {
                  if (audioRef.current) {
                    setAudioDuration(audioRef.current.duration);
                  }
                }}
                onEnded={() => setIsPlaying(false)}
                className="hidden"
              />

              {/* Scrubber */}
              <input
                type="range"
                min="0"
                max={audioDuration || selectedSample.duration || 10}
                step="0.05"
                value={currentTime}
                onChange={handleSeek}
                className="w-full accent-emerald-500 h-1.5 bg-slate-800 rounded-lg cursor-pointer"
              />

              {/* Player Buttons */}
              <div className="flex items-center justify-between pt-1">
                <div className="flex items-center gap-2">
                  <button
                    onClick={togglePlay}
                    className="p-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white transition shadow-md shadow-emerald-950/50"
                  >
                    {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-current" />}
                  </button>
                  <button
                    onClick={() => {
                      if (audioRef.current) {
                        audioRef.current.currentTime = 0;
                        setCurrentTime(0);
                      }
                    }}
                    className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                    title="Phát lại từ đầu"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Speed selector */}
                <div className="flex items-center gap-1 text-xs">
                  <span className="text-slate-400 mr-1">Tốc độ:</span>
                  {[0.8, 1.0, 1.2].map((rate) => (
                    <button
                      key={rate}
                      onClick={() => handleRateChange(rate)}
                      className={`px-2 py-1 rounded-lg text-xs transition ${
                        playbackRate === rate
                          ? "bg-slate-800 text-emerald-400 font-semibold"
                          : "text-slate-400 hover:text-slate-200"
                      }`}
                    >
                      {rate}x
                    </button>
                  ))}
                </div>
              </div>

              {/* Regeneration Controls */}
              <div className="pt-4 border-t border-slate-800 space-y-3">
                <h4 className="text-xs font-semibold text-slate-300">
                  Chỉnh sửa Transcript & Mốc thời gian
                </h4>

                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">
                    Nội dung câu (Text)
                  </label>
                  <textarea
                    rows={3}
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    className="w-full bg-slate-950/70 border border-slate-700 rounded-xl p-2.5 text-xs text-slate-100 focus:outline-none focus:border-emerald-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">
                      Start Time (giây)
                    </label>
                    <input
                      type="number"
                      step="0.05"
                      value={editStart}
                      onChange={(e) => setEditStart(parseFloat(e.target.value) || 0)}
                      className="w-full bg-slate-950/70 border border-slate-700 rounded-xl px-2.5 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">
                      End Time (giây)
                    </label>
                    <input
                      type="number"
                      step="0.05"
                      value={editEnd}
                      onChange={(e) => setEditEnd(parseFloat(e.target.value) || 0)}
                      className="w-full bg-slate-950/70 border border-slate-700 rounded-xl px-2.5 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                </div>

                <button
                  id="btn-regenerate-sample"
                  onClick={handleRegenerate}
                  disabled={isRegenerating}
                  className="w-full py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-emerald-500/30 text-xs font-semibold transition flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  {isRegenerating ? (
                    <span>Đang cắt lại sample...</span>
                  ) : (
                    <>
                      <Edit3 className="w-3.5 h-3.5" />
                      <span>CẮT LẠI SAMPLE (REGENERATE)</span>
                    </>
                  )}
                </button>

                {regenSuccessMsg && (
                  <div className="p-2.5 rounded-lg bg-emerald-950/50 border border-emerald-800 text-xs text-emerald-300 flex items-center gap-2">
                    <Check className="w-4 h-4 shrink-0" />
                    <span>{regenSuccessMsg}</span>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-xs text-slate-500">
              Chọn một sample từ bảng bên trái để nghe thử và chỉnh sửa.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
