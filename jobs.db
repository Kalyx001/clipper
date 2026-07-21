"""Cuts a segment out of the source video, reframes it to 1080x1920 (9:16)
using a blurred-backdrop technique (no face-tracking dependency needed for
the MVP), optionally burns in an .ass subtitle file, and grabs a thumbnail
frame.
"""
import subprocess
from pathlib import Path
from typing import Optional


def _escape_for_filter(path: Path) -> str:
    # ffmpeg filtergraphs treat ':' and other chars specially; escape for the
    # subtitles= filter argument, which itself needs its own quoting.
    s = str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    return s


def cut_and_reframe(
    input_path: Path,
    start: float,
    end: float,
    output_path: Path,
    ass_subtitle_path: Optional[Path] = None,
    width: int = 1080,
    height: int = 1920,
) -> None:
    duration = max(0.1, end - start)

    filter_parts = [
        f"[0:v]split=2[bg][fg]",
        f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},gblur=sigma=20,eq=brightness=-0.05[bgblur]",
        f"[fg]scale={width}:-2:force_original_aspect_ratio=decrease[fgscaled]",
        f"[bgblur][fgscaled]overlay=(W-w)/2:(H-h)/2[merged]",
    ]
    final_label = "merged"
    if ass_subtitle_path is not None:
        escaped = _escape_for_filter(ass_subtitle_path)
        filter_parts.append(f"[merged]subtitles='{escaped}'[capped]")
        final_label = "capped"

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start}", "-to", f"{end}",
        "-i", str(input_path),
        "-filter_complex", filter_complex,
        "-map", f"[{final_label}]",
        "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-t", f"{duration}",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg clip render failed: {result.stderr[-2000:]}")


def generate_thumbnail(video_path: Path, output_path: Path, at_seconds: float = 0.5) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{at_seconds}",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg thumbnail failed: {result.stderr[-1000:]}")
