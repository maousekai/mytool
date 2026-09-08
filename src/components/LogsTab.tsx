import React, { useState, useEffect } from "react";
import { Terminal, RefreshCw, Copy, Check } from "lucide-react";

export const LogsTab: React.FC = () => {
  const [logs, setLogs] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchLogs = async () => {
    setIsLoading(true);
    try {
      const res = await fetch("/api/logs");
      const data = await res.json();
      if (data.logs) {
        setLogs(data.logs);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(() => {
      if (autoRefresh) {
        fetchLogs();
      }
    }, 4000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const copyLogs = () => {
    navigator.clipboard.writeText(logs.join("\n"));
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  return (
    <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Terminal className="w-5 h-5 text-emerald-400" />
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Nhật ký xử lý hệ thống (logs/app.log)
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer mr-2">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-slate-700 text-emerald-500 bg-slate-950"
            />
            <span>Tự động cập nhật</span>
          </label>
          <button
            onClick={fetchLogs}
            disabled={isLoading}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs transition"
            title="Tải lại logs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </button>
          <button
            onClick={copyLogs}
            className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs flex items-center gap-1 transition"
          >
            {isCopied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{isCopied ? "Đã chép" : "Sao chép"}</span>
          </button>
        </div>
      </div>

      <div className="p-4 rounded-xl bg-slate-950 font-mono text-xs text-slate-300 h-96 overflow-y-auto border border-slate-800/80 leading-relaxed whitespace-pre-wrap">
        {logs.length === 0 ? (
          <span className="text-slate-600">Đang chờ bản ghi nhật ký...</span>
        ) : (
          logs.map((line, idx) => (
            <div
              key={idx}
              className={
                line.includes("[ERROR]")
                  ? "text-rose-400 font-semibold"
                  : line.includes("[WARNING]")
                  ? "text-amber-400"
                  : line.includes("[INFO]")
                  ? "text-emerald-400/90"
                  : "text-slate-400"
              }
            >
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
