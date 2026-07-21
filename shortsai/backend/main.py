import json
import shutil
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import db
from config import UPLOADS_DIR, FRONTEND_DIR, YOUTUBE_COOKIES_PATH
from pipeline import run_pipeline
from services import youtube_uploader

db.init_db()

app = FastAPI(title="ShortsAI Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Job submission ----------

@app.post("/api/jobs/youtube")
def submit_youtube(url: str = Form(...), caption_style: str = Form("tiktok")):
    job_id = db.create_job(source_type="youtube", source_ref=url)
    thread = threading.Thread(target=run_pipeline, args=(job_id, "youtube", url, caption_style), daemon=True)
    thread.start()
    return {"job_id": job_id}


@app.post("/api/jobs/upload")
def submit_upload(file: UploadFile = File(...), caption_style: str = Form("tiktok")):
    job_id = str(uuid.uuid4())
    ext = Path(file.filename or "video.mp4").suffix or ".mp4"
    dest = UPLOADS_DIR / f"{job_id}{ext}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    real_job_id = db.create_job(source_type="upload", source_ref=file.filename or dest.name)
    thread = threading.Thread(
        target=run_pipeline, args=(real_job_id, "upload", str(dest), caption_style), daemon=True
    )
    thread.start()
    return {"job_id": real_job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    clips = db.list_clips_for_job(job_id)
    for c in clips:
        if c.get("hashtags"):
            try:
                c["hashtags"] = json.loads(c["hashtags"])
            except (json.JSONDecodeError, TypeError):
                c["hashtags"] = []
    job["clips"] = clips
    return job


@app.get("/api/jobs")
def list_jobs():
    return db.list_jobs()


# ---------- Serving generated media ----------

@app.get("/api/clips/{clip_id}/video")
def get_clip_video(clip_id: str):
    clip = db.get_clip(clip_id)
    if not clip or not clip.get("video_path") or not Path(clip["video_path"]).exists():
        raise HTTPException(404, "Clip video not found")
    return FileResponse(clip["video_path"], media_type="video/mp4", filename=f"{clip_id}.mp4")


@app.get("/api/clips/{clip_id}/thumb")
def get_clip_thumb(clip_id: str):
    clip = db.get_clip(clip_id)
    if not clip or not clip.get("thumb_path") or not Path(clip["thumb_path"]).exists():
        raise HTTPException(404, "Thumbnail not found")
    return FileResponse(clip["thumb_path"], media_type="image/jpeg")


# ---------- YouTube connect + publish ----------

@app.get("/api/youtube/status")
def youtube_status():
    return {"connected": youtube_uploader.is_connected()}


@app.get("/api/youtube/connect")
def youtube_connect():
    url = youtube_uploader.get_auth_url()
    return RedirectResponse(url)


@app.get("/api/youtube/oauth2callback")
async def youtube_oauth_callback(request: Request):
    try:
        youtube_uploader.handle_oauth_callback(str(request.url))
    except Exception as e:
        raise HTTPException(400, f"YouTube auth failed: {e}")
    # Send the user back to the app once connected.
    return RedirectResponse("/?youtube=connected")


@app.post("/api/clips/{clip_id}/publish")
def publish_clip(clip_id: str, privacy_status: str = Form("private")):
    clip = db.get_clip(clip_id)
    if not clip or not clip.get("video_path"):
        raise HTTPException(404, "Clip not found")
    if not youtube_uploader.is_connected():
        raise HTTPException(400, "YouTube is not connected yet")

    db.update_clip(clip_id, youtube_status="uploading")
    try:
        hashtags = json.loads(clip["hashtags"]) if clip.get("hashtags") else []
        description = (clip.get("reason") or "") + "\n\n" + " ".join(f"#{h.lstrip('#')}" for h in hashtags)
        video_id = youtube_uploader.upload_video(
            Path(clip["video_path"]),
            title=clip["title"] or "Untitled",
            description=description,
            tags=hashtags,
            privacy_status=privacy_status,
        )
        db.update_clip(clip_id, youtube_status="uploaded", youtube_video_id=video_id)
        return {"youtube_video_id": video_id}
    except Exception as e:
        db.update_clip(clip_id, youtube_status="failed")
        raise HTTPException(500, str(e))


# ---------- YouTube cookies (works around "sign in to confirm you're not a bot") ----------

@app.get("/api/settings/youtube-cookies")
def youtube_cookies_status():
    return {"present": YOUTUBE_COOKIES_PATH.exists()}


@app.post("/api/settings/youtube-cookies")
async def upload_youtube_cookies(file: UploadFile = File(...)):
    contents = await file.read()
    text = contents.decode("utf-8", errors="ignore")
    if "youtube.com" not in text and "# Netscape" not in text:
        raise HTTPException(400, "That doesn't look like a Netscape-format cookies.txt file")
    YOUTUBE_COOKIES_PATH.write_bytes(contents)
    return {"status": "saved"}


@app.delete("/api/settings/youtube-cookies")
def delete_youtube_cookies():
    if YOUTUBE_COOKIES_PATH.exists():
        YOUTUBE_COOKIES_PATH.unlink()
    return {"status": "deleted"}


# ---------- Frontend ----------

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
