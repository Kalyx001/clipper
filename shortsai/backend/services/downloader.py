"""Handles getting a source video onto local disk, either by downloading
a YouTube URL (yt-dlp) or by receiving an uploaded file.
"""
import subprocess
import json
from pathlib import Path

from config import UPLOADS_DIR


def download_youtube(url: str, job_id: str) -> Path:
    """Downloads a YouTube video (best mp4 <=1080p) using yt-dlp.

    Only use this for videos you own or have explicit permission to process —
    downloading and re-publishing others' content without permission can
    violate YouTube's Terms of Service and copyright law.
    """
    out_template = str(UPLOADS_DIR / f"{job_id}.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "-o", out_template,
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr[-2000:]}")

    candidate = UPLOADS_DIR / f"{job_id}.mp4"
    if candidate.exists():
        return candidate

    # Fall back: find whatever yt-dlp produced with this job_id prefix
    matches = list(UPLOADS_DIR.glob(f"{job_id}.*"))
    if not matches:
        raise RuntimeError("yt-dlp reported success but no output file was found")
    return matches[0]


def probe_video(path: Path) -> dict:
    """Returns duration, width, height, fps using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[-1000:]}")
    info = json.loads(result.stdout)
    video_stream = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    duration = float(info["format"].get("duration", 0))
    width = int(video_stream["width"]) if video_stream else None
    height = int(video_stream["height"]) if video_stream else None
    fr = video_stream.get("avg_frame_rate", "30/1") if video_stream else "30/1"
    try:
        num, den = fr.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 30.0
    except Exception:
        fps = 30.0
    return {"duration": duration, "width": width, "height": height, "fps": fps}
