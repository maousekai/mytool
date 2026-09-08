"""
SQLite Database manager for resume capability and state tracking.
Ensures interrupted builds can resume without reprocessing existing samples.
"""

import os
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime


class DatasetDatabase:
    def __init__(self, db_path: str = "dataset.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample_index INTEGER UNIQUE,
                    wav_filename TEXT UNIQUE,
                    text TEXT NOT NULL,
                    source_audio TEXT,
                    start_time REAL,
                    end_time REAL,
                    actual_start REAL,
                    actual_end REAL,
                    duration REAL,
                    status TEXT, -- 'accepted', 'rejected', 'pending'
                    rejection_reason TEXT,
                    quality_score REAL,
                    rms_db REAL,
                    peak_db REAL,
                    silence_ratio REAL,
                    clipping_count INTEGER,
                    created_at TEXT
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_source_time
                ON samples(source_audio, start_time, end_time)
            """)
            conn.commit()

    def get_max_sample_index(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(sample_index) FROM samples")
            row = cursor.fetchone()
            return row[0] if row and row[0] is not None else 0

    def find_processed_sample(self, source_audio: str, start_time: float, end_time: float) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM samples
                WHERE source_audio = ?
                  AND ABS(start_time - ?) < 0.05
                  AND ABS(end_time - ?) < 0.05
                LIMIT 1
            """, (source_audio, start_time, end_time))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def upsert_sample(self, sample_data: Dict[str, Any]) -> int:
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO samples (
                    sample_index, wav_filename, text, source_audio,
                    start_time, end_time, actual_start, actual_end, duration,
                    status, rejection_reason, quality_score, rms_db, peak_db,
                    silence_ratio, clipping_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sample_index) DO UPDATE SET
                    text = excluded.text,
                    actual_start = excluded.actual_start,
                    actual_end = excluded.actual_end,
                    duration = excluded.duration,
                    status = excluded.status,
                    rejection_reason = excluded.rejection_reason,
                    quality_score = excluded.quality_score,
                    rms_db = excluded.rms_db,
                    peak_db = excluded.peak_db,
                    silence_ratio = excluded.silence_ratio,
                    clipping_count = excluded.clipping_count,
                    created_at = excluded.created_at
            """, (
                sample_data["sample_index"],
                sample_data["wav_filename"],
                sample_data["text"],
                sample_data.get("source_audio", ""),
                sample_data.get("start_time", 0.0),
                sample_data.get("end_time", 0.0),
                sample_data.get("actual_start", 0.0),
                sample_data.get("actual_end", 0.0),
                sample_data.get("duration", 0.0),
                sample_data.get("status", "accepted"),
                sample_data.get("rejection_reason", ""),
                sample_data.get("quality_score", 100.0),
                sample_data.get("rms_db", 0.0),
                sample_data.get("peak_db", 0.0),
                sample_data.get("silence_ratio", 0.0),
                sample_data.get("clipping_count", 0),
                now_str,
            ))
            conn.commit()
            return cursor.lastrowid or 0

    def get_all_samples(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM samples ORDER BY sample_index ASC")
            return [dict(r) for r in cursor.fetchall()]

    def get_accepted_samples(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM samples WHERE status = 'accepted' ORDER BY sample_index ASC")
            return [dict(r) for r in cursor.fetchall()]

    def get_rejected_samples(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM samples WHERE status = 'rejected' ORDER BY sample_index ASC")
            return [dict(r) for r in cursor.fetchall()]

    def get_sample_by_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM samples WHERE wav_filename = ?", (filename,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def clear_all(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM samples")
            conn.commit()
