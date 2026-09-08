import express from "express";
import path from "path";
import fs from "fs";
import { spawn, spawnSync, execFileSync } from "child_process";
import multer from "multer";
import { createServer as createViteServer } from "vite";

const app = express();
const PORT = Number(process.env.PORT || 3000);
const ROOT = process.cwd();
const uploadDir = path.join(ROOT, "uploads");
const sampleDir = path.join(ROOT, "sample_data");
const generatedDir = path.join(ROOT, ".generated");
fs.mkdirSync(uploadDir, { recursive: true });
fs.mkdirSync(generatedDir, { recursive: true });

app.use(express.json({ limit: "2mb" }));
app.use(express.urlencoded({ extended: true, limit: "2mb" }));

interface PythonInvocation {
  command: string;
  prefixArgs: string[];
  version: string;
}

function resolvePython(): PythonInvocation | null {
  const candidates = [
    { command: "python3", prefixArgs: [] as string[] },
    { command: "python", prefixArgs: [] as string[] },
    { command: "py", prefixArgs: ["-3"] },
  ];
  for (const candidate of candidates) {
    try {
      const result = spawnSync(candidate.command, [...candidate.prefixArgs, "--version"], {
        encoding: "utf-8",
        timeout: 3000,
        shell: false,
        windowsHide: true,
      });
      if (result.status === 0) {
        return {
          ...candidate,
          version: `${result.stdout || ""}${result.stderr || ""}`.trim(),
        };
      }
    } catch {}
  }
  return null;
}

function runPythonSync(args: string[], timeout = 15000): string {
  const python = resolvePython();
  if (!python) throw new Error("Không tìm thấy Python 3. Hãy cài Python 3.10/3.11 và thêm vào PATH.");
  return execFileSync(python.command, [...python.prefixArgs, ...args], {
    encoding: "utf-8",
    timeout,
    cwd: ROOT,
    windowsHide: true,
    maxBuffer: 10 * 1024 * 1024,
  });
}

function isInside(parent: string, child: string): boolean {
  const rel = path.relative(path.resolve(parent), path.resolve(child));
  return rel === "" || (!rel.startsWith("..") && !path.isAbsolute(rel));
}

function resolveOutputDir(value: unknown): string {
  const raw = String(value || "output_dataset").trim();
  if (!raw) throw new Error("outputDir cannot be empty");
  const resolved = path.resolve(ROOT, raw);
  if (path.isAbsolute(raw) && process.env.ALLOW_ABSOLUTE_OUTPUT_DIRS !== "1") {
    throw new Error("Absolute output paths are disabled on the web server");
  }
  if (!path.isAbsolute(raw) && !isInside(ROOT, resolved)) {
    throw new Error("outputDir must stay inside the application directory");
  }
  return resolved;
}

function resolveInputPath(value: unknown): string {
  const resolved = path.resolve(ROOT, String(value || ""));
  const allowed = isInside(uploadDir, resolved) || isInside(sampleDir, resolved);
  if (!allowed || !fs.existsSync(resolved) || !fs.statSync(resolved).isFile()) {
    throw new Error(`Input file is not an uploaded/sample file: ${path.basename(resolved)}`);
  }
  return resolved;
}

function parseJsonLastLine(output: string): any {
  const lines = output.split(/\r?\n/).map((x) => x.trim()).filter(Boolean);
  for (let i = lines.length - 1; i >= 0; i--) {
    try { return JSON.parse(lines[i]); } catch {}
  }
  throw new Error("Python command returned no JSON result");
}

function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let value = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (quoted && line[i + 1] === '"') { value += '"'; i++; }
      else quoted = !quoted;
    } else if (ch === "," && !quoted) {
      out.push(value); value = "";
    } else value += ch;
  }
  out.push(value);
  return out;
}

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, uploadDir),
  filename: (_req, file, cb) => {
    const safe = file.originalname.replace(/[^a-zA-Z0-9._-]/g, "_").slice(-180);
    cb(null, `${Date.now()}_${Math.random().toString(36).slice(2, 8)}_${safe}`);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: Number(process.env.MAX_UPLOAD_BYTES || 2 * 1024 * 1024 * 1024) },
});

interface BuildProgress {
  isBuilding: boolean;
  current: number;
  total: number;
  percentage: number;
  etaSeconds: number;
  currentFile: string;
  message: string;
  error: string | null;
  report: any | null;
  recentLogs: string[];
}

let activeBuildState: BuildProgress = {
  isBuilding: false, current: 0, total: 0, percentage: 0, etaSeconds: 0,
  currentFile: "", message: "Sẵn sàng", error: null, report: null, recentLogs: [],
};

function appendBuildLog(text: string) {
  activeBuildState.recentLogs.push(text);
  if (activeBuildState.recentLogs.length > 100) activeBuildState.recentLogs.shift();
}

app.get("/api/system-status", (_req, res) => {
  let ffmpegOk = false;
  let ffmpegVersion = "";
  try {
    const check = spawnSync("ffmpeg", ["-version"], { encoding: "utf-8", timeout: 3000, shell: false });
    ffmpegOk = check.status === 0;
    ffmpegVersion = ffmpegOk ? String(check.stdout || "").split(/\r?\n/)[0] : "Chưa cài đặt hoặc không tìm thấy";
  } catch { ffmpegVersion = "Chưa cài đặt hoặc không tìm thấy"; }
  const python = resolvePython();
  res.json({
    ffmpegOk,
    ffmpegVersion,
    pythonVersion: python?.version || "Không tìm thấy Python 3",
    pythonCommand: python ? [python.command, ...python.prefixArgs].join(" ") : null,
    sampleAvailable: fs.existsSync(path.join(sampleDir, "audiobook_chapter_01.mp3")),
    defaultOutputDir: "output_dataset",
  });
});

app.post("/api/upload", upload.fields([
  { name: "audios", maxCount: 20 },
  { name: "transcript", maxCount: 20 },
]), (req, res) => {
  try {
    const files = req.files as { [fieldname: string]: Express.Multer.File[] };
    const audioFiles = (files?.audios || []).map((f) => ({
      originalName: f.originalname, path: f.path,
      sizeMb: (f.size / (1024 * 1024)).toFixed(2),
    }));
    const transcriptFiles = (files?.transcript || []).map((f) => ({
      originalName: f.originalname, path: f.path,
      sizeKb: (f.size / 1024).toFixed(1),
    }));
    res.json({ success: true, audioFiles, transcriptFiles });
  } catch (e: any) { res.status(500).json({ error: e.message }); }
});

app.post("/api/load-sample", (_req, res) => {
  const audio = path.join(sampleDir, "audiobook_chapter_01.mp3");
  const transcript = path.join(sampleDir, "transcript.json");
  if (!fs.existsSync(audio) || !fs.existsSync(transcript)) {
    res.status(404).json({ error: "Sample data files not found on server." }); return;
  }
  res.json({
    success: true,
    audioFiles: [{ originalName: path.basename(audio), path: audio, sizeMb: (fs.statSync(audio).size / 1048576).toFixed(2) }],
    transcriptFiles: [{ originalName: path.basename(transcript), path: transcript, sizeKb: (fs.statSync(transcript).size / 1024).toFixed(1) }],
  });
});

app.post("/api/build", (req, res) => {
  if (activeBuildState.isBuilding) {
    res.status(409).json({ error: "Một tiến trình build đang chạy. Vui lòng chờ hoàn thành!" }); return;
  }
  try {
    const audioFiles = Array.isArray(req.body.audioFiles) ? req.body.audioFiles.map(resolveInputPath) : [];
    const transcriptFiles = Array.isArray(req.body.transcriptFiles) ? req.body.transcriptFiles.map(resolveInputPath) : [];
    if (!audioFiles.length || audioFiles.length !== transcriptFiles.length) {
      res.status(400).json({ error: "Mỗi file audio phải có đúng một transcript tương ứng (số lượng phải bằng nhau)." }); return;
    }
    const outputDir = resolveOutputDir(req.body.outputDir || "output_dataset");
    const sampleRate = Number(req.body.sampleRate ?? 24000);
    const paddingBefore = Number(req.body.paddingBefore ?? 0.15);
    const paddingAfter = Number(req.body.paddingAfter ?? 0.20);
    const minDuration = Number(req.body.minDuration ?? 2.0);
    const maxDuration = Number(req.body.maxDuration ?? 12.0);
    const mergeSilenceThreshold = Number(req.body.mergeSilenceThreshold ?? 0.8);
    const targetLufs = Number(req.body.targetLufs ?? -20);
    if (![24000, 44100, 48000].includes(sampleRate) || !Number.isFinite(paddingBefore) || !Number.isFinite(paddingAfter)
        || minDuration <= 0 || maxDuration <= minDuration) {
      res.status(400).json({ error: "Thông số build không hợp lệ." }); return;
    }
    const python = resolvePython();
    if (!python) { res.status(500).json({ error: "Không tìm thấy Python 3 trên hệ thống." }); return; }

    activeBuildState = {
      isBuilding: true, current: 0, total: 0, percentage: 0, etaSeconds: 0,
      currentFile: path.basename(audioFiles[0]), message: "Khởi tạo tiến trình Python...",
      error: null, report: null, recentLogs: [`Bắt đầu bằng ${python.command}`],
    };

    const args = [
      path.join(ROOT, "tools", "run_dataset_cli.py"), "build",
      "--output-dir", outputDir,
      "--audio-files", ...audioFiles,
      "--transcript-files", ...transcriptFiles,
      "--sample-rate", String(sampleRate),
      "--padding-before", String(paddingBefore), "--padding-after", String(paddingAfter),
      "--min-duration", String(minDuration), "--max-duration", String(maxDuration),
      "--merge-silence-threshold", String(mergeSilenceThreshold), "--target-lufs", String(targetLufs),
    ];
    if (req.body.refineVad) args.push("--refine-vad");
    if (req.body.autoMergeShort) args.push("--auto-merge-short");
    if (req.body.peakNorm) args.push("--peak-norm");
    if (req.body.loudnessNorm) args.push("--loudness-norm");

    const child = spawn(python.command, [...python.prefixArgs, ...args], {
      cwd: ROOT, shell: false, windowsHide: true,
    });
    let stdoutBuffer = "";
    child.stdout.on("data", (data: Buffer) => {
      stdoutBuffer += data.toString();
      const lines = stdoutBuffer.split(/\r?\n/);
      stdoutBuffer = lines.pop() || "";
      for (const raw of lines) {
        const line = raw.trim(); if (!line) continue;
        try {
          const event = JSON.parse(line);
          if (event.type === "progress") {
            activeBuildState.current = event.current; activeBuildState.total = event.total;
            activeBuildState.percentage = event.percentage; activeBuildState.etaSeconds = event.eta_seconds;
            activeBuildState.currentFile = event.current_file; activeBuildState.message = event.message;
            appendBuildLog(`[${event.percentage}%] ${event.message}`);
          } else if (event.type === "completed") {
            activeBuildState.report = event.report; activeBuildState.percentage = 100;
            activeBuildState.message = "Hoàn thành xử lý toàn bộ Dataset!";
          } else if (event.type === "error") {
            activeBuildState.error = event.error; appendBuildLog(`[ERROR] ${event.error}`);
          }
        } catch { appendBuildLog(line); }
      }
    });
    child.stderr.on("data", (data: Buffer) => appendBuildLog(`[STDERR] ${data.toString().trim()}`));
    child.on("error", (err) => {
      activeBuildState.isBuilding = false; activeBuildState.error = err.message;
      activeBuildState.message = "Không thể khởi động tiến trình Python.";
    });
    child.on("close", (code) => {
      activeBuildState.isBuilding = false;
      if (code !== 0) {
        activeBuildState.error ||= `Tiến trình Python kết thúc với mã lỗi ${code}`;
        activeBuildState.message = "Có lỗi xảy ra trong quá trình xử lý.";
      } else if (!activeBuildState.report) {
        activeBuildState.error = "Python kết thúc nhưng không trả báo cáo hoàn thành.";
        activeBuildState.message = "Build chưa xác nhận hoàn thành.";
      }
    });
    res.json({ success: true, message: "Tiến trình build đã được khởi động.", outputDir });
  } catch (e: any) { res.status(400).json({ error: e.message }); }
});

app.get("/api/progress", (_req, res) => res.json(activeBuildState));

app.get("/api/dataset", (req, res) => {
  try {
    const abs = resolveOutputDir(req.query.outputDir || "output_dataset");
    const reportPath = path.join(abs, "dataset_report.json");
    const metadataPath = path.join(abs, "metadata.json");
    const rejectedPath = path.join(abs, "rejected.csv");
    let report: any = null; let samples: any[] = []; let rejected: any[] = [];
    if (fs.existsSync(reportPath)) { try { report = JSON.parse(fs.readFileSync(reportPath, "utf-8")); } catch {} }
    if (fs.existsSync(metadataPath)) { try { samples = JSON.parse(fs.readFileSync(metadataPath, "utf-8")); } catch {} }
    if (fs.existsSync(rejectedPath)) {
      const lines = fs.readFileSync(rejectedPath, "utf-8").split(/\r?\n/).filter(Boolean);
      for (const line of lines.slice(1)) {
        const p = parseCsvLine(line);
        if (p.length >= 6) rejected.push({ filename: p[0], text: p[1], reason: p[2], start: p[3], end: p[4], duration: p[5] });
      }
    }
    res.json({ exists: fs.existsSync(abs), outputDir: abs, report, samples, rejected });
  } catch (e: any) { res.status(400).json({ exists: false, error: e.message, samples: [], rejected: [] }); }
});

app.get("/api/audio/:filename", (req, res) => {
  try {
    const abs = resolveOutputDir(req.query.outputDir || "output_dataset");
    const filename = path.basename(req.params.filename);
    if (!/^\d+\.wav$/i.test(filename)) { res.status(400).send("Invalid WAV filename"); return; }
    const wav = path.join(abs, "wavs", filename);
    if (!fs.existsSync(wav)) { res.status(404).send("Audio sample not found"); return; }
    const size = fs.statSync(wav).size;
    res.setHeader("Accept-Ranges", "bytes");
    res.setHeader("Content-Type", "audio/wav");
    res.setHeader("Cache-Control", "no-store");
    const range = req.headers.range;
    if (range) {
      const match = /^bytes=(\d*)-(\d*)$/.exec(range);
      if (!match) { res.status(416).setHeader("Content-Range", `bytes */${size}`).end(); return; }
      const start = match[1] ? Number(match[1]) : 0;
      const end = match[2] ? Math.min(Number(match[2]), size - 1) : size - 1;
      if (!Number.isFinite(start) || !Number.isFinite(end) || start > end || start >= size) {
        res.status(416).setHeader("Content-Range", `bytes */${size}`).end(); return;
      }
      res.status(206);
      res.setHeader("Content-Range", `bytes ${start}-${end}/${size}`);
      res.setHeader("Content-Length", String(end - start + 1));
      fs.createReadStream(wav, { start, end }).pipe(res);
    } else {
      res.setHeader("Content-Length", String(size));
      fs.createReadStream(wav).pipe(res);
    }
  } catch (e: any) { res.status(400).send(e.message); }
});

app.post("/api/regenerate", (req, res) => {
  try {
    const outputDir = resolveOutputDir(req.body.outputDir || "output_dataset");
    const filename = path.basename(String(req.body.filename || ""));
    const text = String(req.body.text || "").trim();
    const start = Number(req.body.start); const end = Number(req.body.end);
    if (!/^\d+\.wav$/i.test(filename) || !text || text.length > 20000 || !Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start) {
      res.status(400).json({ error: "Invalid regeneration parameters." }); return;
    }
    const out = runPythonSync([
      path.join(ROOT, "tools", "run_dataset_cli.py"), "regenerate",
      "--output-dir", outputDir, "--filename", filename, "--text", text,
      "--start", String(start), "--end", String(end),
    ], 30000);
    const parsed = parseJsonLastLine(out);
    if (parsed.type === "error") throw new Error(parsed.error);
    res.json({ success: true, sample: parsed.sample });
  } catch (e: any) { res.status(500).json({ error: e.message }); }
});

app.post("/api/validate", (req, res) => {
  try {
    const outputDir = resolveOutputDir(req.body.outputDir || "output_dataset");
    const sampleRate = Number(req.body.sampleRate ?? 24000);
    const minDuration = Number(req.body.minDuration ?? 2); const maxDuration = Number(req.body.maxDuration ?? 12);
    const out = runPythonSync([
      path.join(ROOT, "tools", "run_dataset_cli.py"), "validate",
      "--output-dir", outputDir, "--sample-rate", String(sampleRate),
      "--min-duration", String(minDuration), "--max-duration", String(maxDuration),
    ], 120000);
    const parsed = parseJsonLastLine(out);
    if (parsed.type === "error") throw new Error(parsed.error);
    res.json(parsed.result);
  } catch (e: any) { res.status(500).json({ valid: false, error: e.message, summary: {}, samples: [] }); }
});

app.get("/api/export-dataset", (req, res) => {
  try {
    const outputDir = resolveOutputDir(req.query.outputDir || "output_dataset");
    if (!fs.existsSync(outputDir)) { res.status(404).json({ error: "Dataset directory not found" }); return; }
    const out = runPythonSync([path.join(ROOT, "tools", "run_dataset_cli.py"), "export", "--output-dir", outputDir], 10 * 60 * 1000);
    const result = parseJsonLastLine(out);
    if (!result.valid || !fs.existsSync(result.zip_path)) throw new Error(result.error || "ZIP export failed verification");
    res.download(result.zip_path, "dataset.zip");
  } catch (e: any) { res.status(500).json({ error: e.message }); }
});

app.get("/api/export-python-pkg", (_req, res) => {
  try {
    const target = path.join(generatedDir, "Vietnamese_TTS_Dataset_Builder_Windows.zip");
    const out = runPythonSync([
      path.join(ROOT, "tools", "run_dataset_cli.py"), "package",
      "--source-dir", path.join(ROOT, "tts_dataset_builder"), "--output-zip", target,
    ], 120000);
    const result = parseJsonLastLine(out);
    if (!result.valid || !fs.existsSync(target)) throw new Error("Windows package failed verification");
    res.download(target, "Vietnamese_TTS_Dataset_Builder_Windows.zip");
  } catch (e: any) { res.status(500).json({ error: e.message }); }
});

app.get("/api/logs", (_req, res) => {
  const logPath = path.join(ROOT, "logs", "app.log");
  if (!fs.existsSync(logPath)) { res.json({ logs: ["Chưa có file log."] }); return; }
  try {
    const lines = fs.readFileSync(logPath, "utf-8").split(/\r?\n/).slice(-150);
    res.json({ logs: lines });
  } catch (e: any) { res.status(500).json({ error: e.message }); }
});

async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({ server: { middlewareMode: true }, appType: "spa" });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(ROOT, "dist");
    app.use(express.static(distPath));
    app.get("*", (_req, res) => res.sendFile(path.join(distPath, "index.html")));
  }
  app.listen(PORT, "0.0.0.0", () => console.log(`Vietnamese TTS Dataset Builder Server running on http://localhost:${PORT}`));
}

startServer();
