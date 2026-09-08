export interface AudioFileItem {
  originalName: string;
  path: string;
  sizeMb: string;
}

export interface TranscriptFileItem {
  originalName: string;
  path: string;
  sizeKb: string;
}

export interface BuildOptions {
  sampleRate: 24000 | 44100 | 48000;
  paddingBefore: number;
  paddingAfter: number;
  refineVad: boolean;
  minDuration: number;
  maxDuration: number;
  autoMergeShort: boolean;
  mergeSilenceThreshold: number;
  peakNorm: boolean;
  loudnessNorm: boolean;
  targetLufs: number;
  outputDir: string;
}

export interface BuildProgressState {
  isBuilding: boolean;
  current: number;
  total: number;
  percentage: number;
  etaSeconds: number;
  currentFile: string;
  message: string;
  error: string | null;
  report: DatasetReport | null;
  recentLogs: string[];
}

export interface DatasetSample {
  sample_index: number;
  wav_filename: string;
  text: string;
  source_audio?: string;
  start_time: number;
  end_time: number;
  actual_start: number;
  actual_end: number;
  duration: number;
  status: "accepted" | "rejected";
  rejection_reason?: string;
  quality_score: number;
  rms_db?: number;
  peak_db?: number;
  silence_ratio?: number;
  clipping_count?: number;
}

export interface RejectedSample {
  filename: string;
  text: string;
  reason: string;
  start: string;
  end: string;
  duration: string;
}

export interface DatasetReport {
  summary: {
    total_samples: number;
    accepted_samples: number;
    rejected_samples: number;
    total_duration_seconds: number;
    total_duration_formatted: string;
    average_duration_seconds: number;
    min_duration_seconds: number;
    max_duration_seconds: number;
  };
  duration_distribution: Record<string, number>;
  parameters: Record<string, any>;
  generated_at: string;
}

export interface ValidationSampleItem {
  id: number;
  filename: string;
  text: string;
  duration: number;
  sample_rate?: number;
  peak_db?: number;
  rms_db?: number;
  quality_score: number;
  status: "PERFECT" | "GOOD" | "WARNING" | "CRITICAL" | "ERROR";
  issues: string[];
}

export interface ValidationSummary {
  total_checked: number;
  average_quality_score: number;
  missing_wav_files: number;
  duplicate_transcripts: number;
  duplicate_audio_files: number;
  empty_transcripts: number;
  duration_warnings: number;
  sample_rate_mismatches: number;
  clipped_samples: number;
  high_silence_samples: number;
}

export interface ValidationResult {
  valid: boolean;
  error?: string;
  summary: ValidationSummary;
  samples: ValidationSampleItem[];
}

export interface SystemStatus {
  ffmpegOk: boolean;
  ffmpegVersion: string;
  pythonVersion: string;
  sampleAvailable: boolean;
  defaultOutputDir: string;
}
