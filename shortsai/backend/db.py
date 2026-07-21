import sqlite3
import json
import time
import uuid
from contextlib import contextmanager
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,           -- queued, downloading, transcribing, analyzing, clipping, captioning, done, failed
    progress INTEGER DEFAULT 0,     -- 0-100
    message TEXT DEFAULT '',
    source_type TEXT,               -- 'youtube' or 'upload'
    source_ref TEXT,                -- url or filename
    created_at REAL,
    updated_at REAL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS clips (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    start_s REAL,
    end_s REAL,
    viral_score REAL,
    reason TEXT,
    title TEXT,
    hashtags TEXT,        -- json list
    caption_style TEXT DEFAULT 'tiktok',
    video_path TEXT,
    thumb_path TEXT,
    youtube_video_id TEXT,
    youtube_status TEXT DEFAULT 'none'  -- none, uploading, uploaded, failed
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def create_job(source_type: str, source_ref: str) -> str:
    job_id = str(uuid.uuid4())
    now = time.time()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO jobs (id, status, progress, message, source_type, source_ref, created_at, updated_at) "
            "VALUES (?, 'queued', 0, 'Queued', ?, ?, ?, ?)",
            (job_id, source_type, source_ref, now, now),
        )
    return job_id


def update_job(job_id: str, **fields):
    fields["updated_at"] = time.time()
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [job_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE jobs SET {cols} WHERE id = ?", vals)


def get_job(job_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def list_jobs(limit: int = 50):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def add_clip(job_id: str, **fields) -> str:
    clip_id = str(uuid.uuid4())
    fields["id"] = clip_id
    fields["job_id"] = job_id
    if "hashtags" in fields and isinstance(fields["hashtags"], list):
        fields["hashtags"] = json.dumps(fields["hashtags"])
    cols = ", ".join(fields.keys())
    placeholders = ", ".join("?" for _ in fields)
    with get_conn() as conn:
        conn.execute(f"INSERT INTO clips ({cols}) VALUES ({placeholders})", list(fields.values()))
    return clip_id


def update_clip(clip_id: str, **fields):
    if "hashtags" in fields and isinstance(fields["hashtags"], list):
        fields["hashtags"] = json.dumps(fields["hashtags"])
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [clip_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE clips SET {cols} WHERE id = ?", vals)


def get_clip(clip_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM clips WHERE id = ?", (clip_id,)).fetchone()
        return dict(row) if row else None


def list_clips_for_job(job_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM clips WHERE job_id = ? ORDER BY viral_score DESC", (job_id,)
        ).fetchall()
        return [dict(r) for r in rows]
