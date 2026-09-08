import express from "express";
import path from "path";
import fs from "fs";
import { spawn, spawnSync, execFileSync, execSync } from "child_process";
import multer from "multer";
import { createServer as createViteServer } from "vite";

const app = express();
const PORT = 3000;

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

interface PythonInvocation {
  command: string;
  prefixArgs: string[];
  version: string;
}

function resolvePython(): PythonInvocation | null {
  const candidates: Array<{ command: string; prefixArgs: string[] }> = [
    { command: "python3", prefixArgs: [] },
    { command: "python", prefixArgs: [] },
    { command: "py", prefixArgs: ["-3"] },
  ];

  for (const candidate of candidates) {
    try {
      const result = spawnSync(
        candidate.command,
        [...candidate.prefixArgs, "--version"],
        { encoding: "utf-8", timeout: 3000, shell: false }
      );
      if (result.status === 0) {
        const version = `${result.stdout || ""}${result.stderr || ""}`.trim();
        return { ...candidate, version };
      }
    } catch {
      // Try the next launcher.
    }
  }
  return null;
}

function runPythonSync(args: string[], timeout = 15000): string {
  const python = resolvePython();
  if (!python) {
    throw new Error("Không tìm thấy Python 3. Hãy cài Python 3.10/3.11 và thêm vào PATH.");
  }
  return execFileSync(
    python.command,
    [...python.prefixArgs, ...args],
    { encoding: "utf-8", timeout, cwd: process.cwd(), windowsHide: true }
  );
}

function resolveOutputDir(outputDir: string): string {
  return path.isAbsolute(outputDir) ? path.normalize(outputDir) : path.join(process.cwd(), outputDir);
}

// Storage for uploaded files
const uploadDir = path.join(process.cwd(), "uploads");
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => {
    cb(null, uploadDir);
  },
  filename: (_req, file, cb) => {
    const safeName = Date.now() + "_" + file.originalname.replace(/[^a-zA-Z0-9._-]/g, "_");
    cb(null, safeName);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: 500 * 1024 * 1024 },
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
};

app.get("/api/system-status", (_req, res) => {
  let ffmpegOk = false;
  let ffmpegVersion = "";
  try {
    const out = execSync("ffmpeg -version", { encoding: "utf-8", timeout: 3000 });
    ffmpegOk = true;
    ffmpegVersion = out.split("\n")[0];
  } catch {
    ffmpegVersion = "Chưa cài đặt hoặc không tìm thấy";
  }

  const python = resolvePython();
  const sampleAvailable = fs.existsSync(path.join(process.cwd(), "sample_data", "audiobook_chapter_01.mp3"));

  res.json({
    ffmpegOk,
    ffmpegVersion,
    pythonVersion: python?.version || "Không tìm thấy Python 3",
    pythonCommand: python ? [python.command, ...python.prefixArgs].join(" ") : null,
    sampleAvailable,
    defaultOutputDir: "output_dataset",
  });
});

app.post(
  "/api/upload",
  upload.fields([
    { name: "audios", maxCount: 20 },
    { name: "transcript", maxCount: 5 },
  ]),
  (req, res) => {
    try {
      const files = req.files as { [fieldname: string]: Express.Multer.File[] };
      const audioFiles = (files["audios"] || []).map((f) => ({
        originalName: f.originalname,
        path: f.path,
        sizeMb: (f.size / (1024 * 1024)).toFixed(2),
      }));
      const transcriptFiles = (files["transcript"] || []).map((f) => ({
        originalName: f.originalname,
        path: f.path,
        sizeKb: (f.size / 1024).toFixed(1),
      }));

      res.json({ success: true, audioFiles, transcriptFiles });
    } catch (e: any) {
      res.status(500).json({ error: e.message });
    }
  }
);

app.post("/api/load-sample", (_req, res) => {
  const sampleAudio = path.join(process.cwd(), "sample_data", "audiobook_chapter_01.mp3");
  const sampleTranscript = path.join(process.cwd(), "sample_data", "transcript.json");

  if (!fs.existsSync(sampleAudio) || !fs.existsSync(sampleTranscript)) {
    res.status(404).json({ error: "Sample data files not found on server." });
    return;
  }

  res.json({
    success: true,
    audioFiles: [{
      originalName: "audiobook_chapter_01.mp3",
      path: sampleAudio,
      sizeMb: (fs.statSync(sampleAudio).size / (1024 * 1024)).toFixed(2),
    }],
    transcriptFiles: [{
      originalName: "transcript.json",
      path: sampleTranscript,
      sizeKb: (fs.statSync(sampleTranscript).size / 1024).toFixed(1),
    }],
  });
});

app.post("/api/build", (req, res) => {
  if (activeBuildState.isBuilding) {
    res.status(400).json({ error: "Một tiến trình build đang chạy. Vui lòng chờ hoàn thành!" });
    return;
  }

  const {
    audioFiles = [],
    transcriptFiles = [],
    outputDir = "output_dataset",
    sampleRate = 24000,
    paddingBefore = 0.15,
    paddingAfter = 0.20,
    refineVad = false,
    minDuration = 2.0,
    maxDuration = 12.0,
    autoMergeShort = true,
    mergeSilenceThreshold = 0.80,
    peakNorm = false,
    loudnessNorm = false,
    targetLufs = -20.0,
  } = req.body;

  if (!audioFiles.length || !transcriptFiles.length) {
    res.status(400).json({ error: "Vui lòng cung cấp ít nhất 1 file audio và 1 file transcript!" });
    return;
  }

  const python = resolvePython();
  if (!python) {
    res.status(500).json({ error: "Không tìm thấy Python 3 trên hệ thống." });
    return;
  }

  activeBuildState = {
    isBuilding: true,
    current: 0,
    total: 0,
    percentage: 0,
    etaSeconds: 0,
    currentFile: path.basename(audioFiles[0]),
    message: "Khởi tạo tiến trình Python...",
    error: null,
    report: null,
    recentLogs: [`Bắt đầu tiến trình tạo dataset TTS bằng ${python.command}.`],
  };

  const args = [
    path.join(process.cwd(), "tools", "run_dataset_cli.py"),
    "build",
    "--output-dir", outputDir,
    "--audio-files", audioFiles.join(","),
    "--transcript-files", transcriptFiles.join(","),
    "--sample-rate", String(sampleRate),
    "--padding-before", String(paddingBefore),
    "--padding-after", String(paddingAfter),
    "--min-duration", String(minDuration),
    "--max-duration", String(maxDuration),
    "--merge-silence-threshold", String(mergeSilenceThreshold),
    "--target-lufs", String(targetLufs),
  ];

  if (refineVad) args.push("--refine-vad");
  if (autoMergeShort) args.push("--auto-merge-short");
  if (peakNorm) args.push("--peak-norm");
  if (loudnessNorm) args.push("--loudness-norm");

  const pyProcess = spawn(
    python.command,
    [...python.prefixArgs, ...args],
    { cwd: process.cwd(), shell: false, windowsHide: true }
  );

  pyProcess.stdout.on("data", (data: Buffer) => {
    const lines = data.toString().split("\n");
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const event = JSON.parse(line.trim());
        if (event.type === "progress") {
          activeBuildState.current = event.current;
          activeBuildState.total = event.total;
          activeBuildState.percentage = event.percentage;
          activeBuildState.etaSeconds = event.eta_seconds;
          activeBuildState.currentFile = event.current_file;
          activeBuildState.message = event.message;
          activeBuildState.recentLogs.push(`[${event.percentage}%] ${event.message}`);
          if (activeBuildState.recentLogs.length > 50) activeBuildState.recentLogs.shift();
        } else if (event.type === "completed") {
          activeBuildState.report = event.report;
          activeBuildState.percentage = 100;
          activeBuildState.message = "Hoàn thành xử lý toàn bộ Dataset!";
          activeBuildState.isBuilding = false;
        }
      } catch {
        activeBuildState.recentLogs.push(line.trim());
      }
    }
  });

  pyProcess.stderr.on("data", (data: Buffer) => {
    const text = data.toString().trim();
    if (text) activeBuildState.recentLogs.push(`[STDERR] ${text}`);
  });

  pyProcess.on("error", (err) => {
    activeBuildState.isBuilding = false;
    activeBuildState.error = err.message;
    activeBuildState.message = "Không thể khởi động tiến trình Python.";
  });

  pyProcess.on("close", (code) => {
    activeBuildState.isBuilding = false;
    if (code !== 0 && !activeBuildState.report) {
      activeBuildState.error = `Tiến trình Python kết thúc với mã lỗi ${code}`;
      activeBuildState.message = "Có lỗi xảy ra trong quá trình xử lý.";
    }
  });

  res.json({ success: true, message: "Tiến trình build đã được khởi động." });
});

app.get("/api/progress", (_req, res) => {
  res.json(activeBuildState);
});

app.get("/api/dataset", (req, res) => {
  const outputDir = (req.query.outputDir as string) || "output_dataset";
  const absOutputDir = resolveOutputDir(outputDir);

  const reportPath = path.join(absOutputDir, "dataset_report.json");
  const metadataJsonPath = path.join(absOutputDir, "metadata.json");
  const rejectedCsvPath = path.join(absOutputDir, "rejected.csv");

  let report = null;
  if (fs.existsSync(reportPath)) {
    try { report = JSON.parse(fs.readFileSync(reportPath, "utf-8")); } catch {}
  }

  let samples: any[] = [];
  if (fs.existsSync(metadataJsonPath)) {
    try { samples = JSON.parse(fs.readFileSync(metadataJsonPath, "utf-8")); } catch {}
  }

  let rejected: any[] = [];
  if (fs.existsSync(rejectedCsvPath)) {
    try {
      const content = fs.readFileSync(rejectedCsvPath, "utf-8");
      const lines = content.trim().split("\n");
      if (lines.length > 1) {
        for (let i = 1; i < lines.length; i++) {
          const parts = lines[i].split(",");
          if (parts.length >= 6) {
            rejected.push({ filename: parts[0], text: parts[1], reason: parts[2], start: parts[3], end: parts[4], duration: parts[5] });
          }
        }
      }
    } catch {}
  }

  res.json({ exists: fs.existsSync(absOutputDir), outputDir, report, samples, rejected });
});

app.get("/api/audio/:filename", (req, res) => {
  const filename = path.basename(req.params.filename);
  const outputDir = (req.query.outputDir as string) || "output_dataset";
  const absOutputDir = resolveOutputDir(outputDir);
  const wavPath = path.join(absOutputDir, "wavs", filename);

  if (!fs.existsSync(wavPath)) {
    res.status(404).send("Audio sample not found in the selected dataset");
    return;
  }

  res.setHeader("Content-Type", "audio/wav");
  fs.createReadStream(wavPath).pipe(res);
});

app.post("/api/regenerate", (req, res) => {
  const { outputDir = "output_dataset", filename, text, start, end } = req.body;
  if (!filename || text === undefined || start === undefined || end === undefined) {
    res.status(400).json({ error: "Missing required regeneration parameters." });
    return;
  }

  const args = [
    path.join(process.cwd(), "tools", "run_dataset_cli.py"),
    "regenerate",
    "--output-dir", outputDir,
    "--filename", path.basename(filename),
    "--text", String(text),
    "--start", String(start),
    "--end", String(end),
  ];

  try {
    const out = runPythonSync(args, 10000);
    const parsed = JSON.parse(out.trim().split("\n").pop() || "{}");
    res.json({ success: true, sample: parsed.sample });
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/api/validate", (req, res) => {
  const { outputDir = "output_dataset", sampleRate = 24000, minDuration = 2.0, maxDuration = 12.0 } = req.body;
  const args = [
    path.join(process.cwd(), "tools", "run_dataset_cli.py"),
    "validate",
    "--output-dir", outputDir,
    "--sample-rate", String(sampleRate),
    "--min-duration", String(minDuration),
    "--max-duration", String(maxDuration),
  ];

  try {
    const out = runPythonSync(args, 15000);
    const parsed = JSON.parse(out.trim().split("\n").pop() || "{}");
    res.json(parsed.result);
  } catch (e: any) {
    res.status(500).json({ valid: false, error: e.message });
  }
});

app.get("/api/export-dataset", (req, res) => {
  const outputDir = (req.query.outputDir as string) || "output_dataset";
  const absOutputDir = resolveOutputDir(outputDir);
  const zipTarget = path.join(absOutputDir, "dataset.zip");

  try {
    if (!fs.existsSync(absOutputDir)) {
      res.status(404).json({ error: `Dataset directory not found: ${absOutputDir}` });
      return;
    }

    runPythonSync([
      path.join(process.cwd(), "tools", "run_dataset_cli.py"),
      "export",
      "--output-dir", absOutputDir,
    ], 120000);

    if (!fs.existsSync(zipTarget)) {
      res.status(500).json({ error: "Exporter completed but dataset.zip was not created." });
      return;
    }

    const fd = fs.openSync(zipTarget, "r");
    const magic = Buffer.alloc(4);
    fs.readSync(fd, magic, 0, 4, 0);
    fs.closeSync(fd);
    if (!magic.equals(Buffer.from([0x50, 0x4b, 0x03, 0x04]))) {
      res.status(500).json({ error: "Generated file failed ZIP signature validation." });
      return;
    }

    res.setHeader("Content-Type", "application/zip");
    res.setHeader("Content-Disposition", 'attachment; filename="dataset.zip"');
    res.download(zipTarget, "dataset.zip", (err) => {
      if (err && !res.headersSent) {
        res.status(500).json({ error: err.message });
      }
    });
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
});

app.get("/api/export-python-pkg", (_req, res) => {
  const pkgPath = path.join(process.cwd(), "public", "tts_dataset_builder.zip");
  if (fs.existsSync(pkgPath)) {
    res.download(pkgPath, "Vietnamese_TTS_Dataset_Builder_Windows.zip");
    return;
  }
  res.status(404).send("Python package archive not found");
});

app.get("/api/logs", (_req, res) => {
  const logPath = path.join(process.cwd(), "logs", "app.log");
  if (!fs.existsSync(logPath)) {
    res.json({ logs: ["Chưa có file log."] });
    return;
  }
  try {
    const content = fs.readFileSync(logPath, "utf-8");
    const lines = content.trim().split("\n").slice(-150);
    res.json({ logs: lines });
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
});

async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({ server: { middlewareMode: true }, appType: "spa" });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (_req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Vietnamese TTS Dataset Builder Server running on http://localhost:${PORT}`);
  });
}

startServer();
