from pathlib import Path

import db
from config import OUTPUTS_DIR
from services import downloader, transcriber, viral_detector, clipper, captions


def run_pipeline(job_id: str, source_type: str, source_path_or_url: str, caption_style: str = "tiktok"):
    job_out_dir = OUTPUTS_DIR / job_id
    job_out_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Acquire source video
        db.update_job(job_id, status="downloading", progress=5, message="Fetching video")
        if source_type == "youtube":
            video_path = downloader.download_youtube(source_path_or_url, job_id)
        else:
            video_path = Path(source_path_or_url)

        info = downloader.probe_video(video_path)
        duration = info["duration"]

        # 2. Transcribe with word-level timestamps
        db.update_job(job_id, status="transcribing", progress=25, message="Transcribing audio")
        transcript = transcriber.transcribe(video_path)

        # 3. Find viral moments
        db.update_job(job_id, status="analyzing", progress=50, message="Finding viral moments")
        moments = viral_detector.detect_viral_moments(transcript["segments"], duration)
        if not moments:
            raise RuntimeError("No viable clips were found in this video")

        # 4. Cut, reframe, and caption each clip
        db.update_job(job_id, status="clipping", progress=60, message=f"Rendering {len(moments)} clips")
        total = len(moments)
        for i, m in enumerate(moments):
            clip_id = db.add_clip(
                job_id,
                start_s=m["start"], end_s=m["end"], viral_score=m["viral_score"],
                reason=m["reason"], title=m["title"], hashtags=m["hashtags"],
                caption_style=caption_style,
            )

            ass_path = job_out_dir / f"{clip_id}.ass"
            captions.generate_ass(transcript["words"], m["start"], m["end"], ass_path, style=caption_style)

            clip_video_path = job_out_dir / f"{clip_id}.mp4"
            clipper.cut_and_reframe(video_path, m["start"], m["end"], clip_video_path, ass_subtitle_path=ass_path)

            thumb_path = job_out_dir / f"{clip_id}_thumb.jpg"
            clipper.generate_thumbnail(clip_video_path, thumb_path, at_seconds=0.4)

            db.update_clip(clip_id, video_path=str(clip_video_path), thumb_path=str(thumb_path))

            progress = 60 + int(35 * (i + 1) / total)
            db.update_job(job_id, progress=progress, message=f"Rendered clip {i + 1}/{total}")

        db.update_job(job_id, status="done", progress=100, message="All clips ready")

    except Exception as e:
        db.update_job(job_id, status="failed", progress=0, message="Failed", error=str(e))
