"""
SQLite state manager for dataset build/resume.

The database is intentionally kept inside each output dataset.  It tracks the
source-audio fingerprint and the exact PCM cache used by every sample so a
manual regeneration can never silently cut from a different audiobook.
"""

import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional


class DatasetDatabase:
    def __init__(self, db_path: str = "dataset.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
        return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    def _init_tables(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample_index INTEGER UNIQUE,
                    wav_filename TEXT UNIQUE,
                    text TEXT NOT NULL,
                    source_audio TEXT,
                    source_key TEXT,
                    source_pcm TEXT,
                    start_time REAL,
                    end_time REAL,
                    actual_start REAL,
                    actual_end REAL,
                    duration REAL,
                    status TEXT,
                    rejection_reason TEXT,
                    quality_score REAL,
                    rms_db REAL,
                    peak_db REAL,
                    silence_ratio REAL,
                    clipping_count INTEGER,
                    created_at TEXT
                )
                """
            )

            # Lightweight migration for datasets created by older releases.
            columns = self._table_columns(conn, "samples")
            if "source_key" not in columns:
                conn.execute("ALTER TABLE samples ADD COLUMN source_key TEXT")
            if "source_pcm" not in columns:
                conn.execute("ALTER TABLE samples ADD COLUMN source_pcm TEXT")

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_source_time
                ON samples(source_audio, start_time, end_time)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_source_key_time
                ON samples(source_key, start_time, end_time)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    source_key TEXT PRIMARY KEY,
                    source_audio TEXT NOT NULL,
                    source_pcm TEXT NOT NULL,
                    build_signature TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def get_max_sample_index(self) -> int:
        with self._get_connection() as conn:
            row = conn.execute("SELECT MAX(sample_index) FROM samples").fetchone()
            return int(row[0]) if row and row[0] is not None else 0

    def get_source_state(self, source_key: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sources WHERE source_key = ?", (source_key,)
            ).fetchone()
            return dict(row) if row else None

    def set_source_state(
        self,
        source_key: str,
        source_audio: str,
        source_pcm: str,
        build_signature: str,
    ) -> None:
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sources(source_key, source_audio, source_pcm, build_signature, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_key) DO UPDATE SET
                    source_audio = excluded.source_audio,
                    source_pcm = excluded.source_pcm,
                    build_signature = excluded.build_signature,
                    updated_at = excluded.updated_at
                """,
                (source_key, source_audio, source_pcm, build_signature, now_str),
            )
            conn.commit()

    def find_processed_sample(
        self,
        source_key: str,
        start_time: float,
        end_time: float,
        *,
        legacy_source_audio: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Find the same source/timestamp segment with a small timestamp tolerance."""
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM samples
                WHERE source_key = ?
                  AND ABS(start_time - ?) < 0.05
                  AND ABS(end_time - ?) < 0.05
                LIMIT 1
                """,
                (source_key, start_time, end_time),
            ).fetchone()
            if row:
                return dict(row)

            # Compatibility with datasets created before source_key existed.
            if legacy_source_audio:
                row = conn.execute(
                    """
                    SELECT * FROM samples
                    WHERE (source_key IS NULL OR source_key = '')
                      AND source_audio = ?
                      AND ABS(start_time - ?) < 0.05
                      AND ABS(end_time - ?) < 0.05
                    LIMIT 1
                    """,
                    (legacy_source_audio, start_time, end_time),
                ).fetchone()
                if row:
                    return dict(row)
        return None

    def adopt_legacy_source(
        self, source_audio: str, source_key: str, source_pcm: str
    ) -> None:
        """Attach source identity to legacy rows without changing sample IDs."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE samples
                SET source_key = ?, source_pcm = ?
                WHERE source_audio = ? AND (source_key IS NULL OR source_key = '')
                """,
                (source_key, source_pcm, source_audio),
            )
            conn.commit()

    def get_samples_for_source(self, source_key: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM samples WHERE source_key = ? ORDER BY sample_index",
                    (source_key,),
                ).fetchall()
            ]

    def delete_samples_for_source(self, source_key: str) -> List[str]:
        """Delete DB rows for one source and return their WAV filenames for cleanup."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT wav_filename FROM samples WHERE source_key = ?", (source_key,)
            ).fetchall()
            filenames = [str(row[0]) for row in rows if row[0]]
            conn.execute("DELETE FROM samples WHERE source_key = ?", (source_key,))
            conn.commit()
            return filenames

    def upsert_sample(self, sample_data: Dict[str, Any]) -> int:
        now_str = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO samples (
                    sample_index, wav_filename, text, source_audio, source_key, source_pcm,
                    start_time, end_time, actual_start, actual_end, duration,
                    status, rejection_reason, quality_score, rms_db, peak_db,
                    silence_ratio, clipping_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(sample_index) DO UPDATE SET
                    wav_filename = excluded.wav_filename,
                    text = excluded.text,
                    source_audio = excluded.source_audio,
                    source_key = excluded.source_key,
                    source_pcm = excluded.source_pcm,
                    start_time = excluded.start_time,
                    end_time = excluded.end_time,
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
                """,
                (
                    sample_data["sample_index"],
                    sample_data["wav_filename"],
                    sample_data["text"],
                    sample_data.get("source_audio", ""),
                    sample_data.get("source_key", ""),
                    sample_data.get("source_pcm", ""),
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
                ),
            )
            conn.commit()
            return int(cursor.lastrowid or 0)

    def get_all_samples(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM samples ORDER BY sample_index ASC"
                ).fetchall()
            ]

    def get_accepted_samples(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM samples WHERE status = 'accepted' ORDER BY sample_index ASC"
                ).fetchall()
            ]

    def get_rejected_samples(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM samples WHERE status = 'rejected' ORDER BY sample_index ASC"
                ).fetchall()
            ]

    def get_sample_by_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM samples WHERE wav_filename = ?", (filename,)
            ).fetchone()
            return dict(row) if row else None

    def clear_all(self) -> None:
        with self._get_connection() as conn:
            conn.execute("DELETE FROM samples")
            conn.execute("DELETE FROM sources")
            conn.commit()
