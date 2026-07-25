"""Fallback clip segmentation for when transcription/AI analysis can't
produce moments (weak transcription model, non-speech audio, API hiccup,
etc). Instead of failing the whole job, cut the video into clean chunks by
snapping to natural pauses in the audio (silence), so cuts land between
sentences/words rather than mid-word wherever possible.
"""
import re
import subprocess
from pathlib import Path


def detect_silences(video_path: Path, noise_db: str = "-30dB", min_duration: float = 0.3) -> list[tuple[float, float]]:
    """Returns list of (silence_start, silence_end) in seconds using ffmpeg's silencedetect."""
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-af", f"silencedetect=noise={noise_db}:d={min_duration}",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    log = result.stderr

    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", log)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", log)]
    return list(zip(starts, ends))


def _nearest_silence_point(target: float, silences: list[tuple[float, float]], tolerance: float = 4.0) -> float | None:
    """Finds a silence midpoint within `tolerance` seconds of `target`, if any."""
    best = None
    best_dist = tolerance
    for s, e in silences:
        mid = (s + e) / 2
        dist = abs(mid - target)
        if dist < best_dist:
            best = mid
            best_dist = dist
    return best


def suggest_clips(
    video_duration: float,
    silences: list[tuple[float, float]],
    target_len: float = 20.0,
    min_len: float = 8.0,
    max_len: float = 30.0,
    max_clips: int = 10,
) -> list[dict]:
    """Walks through the video in ~target_len chunks, snapping each cut to
    the nearest detected silence when one is nearby, so clips tend to start
    and end between words/sentences instead of mid-word.
    """
    clips = []
    cursor = 0.0
    while cursor < video_duration - min_len and len(clips) < max_clips:
        raw_end = min(cursor + target_len, video_duration)
        snapped = _nearest_silence_point(raw_end, silences)
        end = snapped if snapped is not None else raw_end
        end = min(end, video_duration)
        end = max(end, cursor + min_len)
        if end - cursor > max_len:
            end = cursor + max_len

        clips.append({
            "start": round(cursor, 2),
            "end": round(end, 2),
            "viral_score": 50,
            "reason": "Auto-segmented (no usable transcript/AI analysis for this section).",
            "title": "Untitled clip",
            "hashtags": [],
        })
        cursor = end
    return clips
