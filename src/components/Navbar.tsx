import React from "react";
import { Mic, Waves, ShieldCheck, Download, Terminal, CheckCircle2, AlertTriangle, FileAudio } from "lucide-react";
import { SystemStatus } from "../types";

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  systemStatus: SystemStatus | null;
  onLoadSample: () => void;
  isBuilding: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  systemStatus,
  onLoadSample,
  isBuilding,
}) => {
  return (
    <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-50 text-slate-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Title */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 flex items-center justify-center text-slate-950 font-bold shadow-lg shadow-emerald-500/20">
              <Mic className="w-5 h-5 text-slate-950" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-base tracking-tight text-white">
                  Vietnamese TTS Dataset Builder
                </span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-medium">
                  Local v1.0
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">
                Cắt audio audiobook dài theo mốc thời gian transcript thành dataset chuẩn fine-tune TTS
              </p>
            </div>
          </div>

          {/* Quick Actions & Status */}
          <div className="flex items-center gap-3">
            <button
              id="btn-load-sample-header"
              onClick={onLoadSample}
              disabled={isBuilding}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition disabled:opacity-50"
              title="Tải ngay audio audiobook tiếng Việt và transcript mẫu có sẵn"
            >
              <FileAudio className="w-3.5 h-3.5 text-emerald-400" />
              <span>Tải mẫu Audiobook</span>
            </button>

            <a
              id="btn-download-win-pkg"
              href="/api/export-python-pkg"
              download
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition shadow-sm"
              title="Tải trọn bộ mã nguồn Python + run_windows.bat để chạy local trên máy tính"
            >
              <Download className="w-3.5 h-3.5" />
              <span className="hidden md:inline">Tải trọn bộ Windows (.ZIP)</span>
            </a>

            {/* System FFmpeg indicator */}
            <div
              className={`hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border ${
                systemStatus?.ffmpegOk
                  ? "bg-emerald-950/60 border-emerald-800 text-emerald-300"
                  : "bg-amber-950/60 border-amber-800 text-amber-300"
              }`}
            >
              {systemStatus?.ffmpegOk ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  <span>FFmpeg Sẵn sàng</span>
                </>
              ) : (
                <>
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                  <span>Thiếu FFmpeg</span>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <nav className="flex space-x-1 border-t border-slate-800/80 pt-1 pb-2">
          {[
            { id: "builder", label: "Tạo Dataset", icon: Mic },
            { id: "preview", label: "Nghe & Sửa mẫu", icon: Waves },
            { id: "validator", label: "Kiểm định chất lượng", icon: ShieldCheck },
            { id: "export", label: "Xuất dữ liệu & Windows App", icon: Download },
            { id: "logs", label: "Nhật ký (Logs)", icon: Terminal },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                id={`nav-tab-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all ${
                  isActive
                    ? "bg-emerald-600/15 text-emerald-400 border border-emerald-500/30"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? "text-emerald-400" : "text-slate-400"}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
};
