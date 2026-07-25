"""Asks an LLM (via Groq's free API) to read the transcript (with timestamps)
and pick the segments most likely to work as standalone vertical shorts:
strong hooks, emotional peaks, humor, surprising claims, self-contained
stories.

Groq (https://console.groq.com) hosts open models like Llama for free API
access with no credit card required -- a good fit if you don't want any
per-request cost. Quality on nuanced judgment calls is a step below Claude,
but solid for this kind of transcript scoring task.
"""
import json
import re
import requests

from config import GROQ_API_KEY, MAX_CLIP_SECONDS, MIN_CLIP_SECONDS

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT_TEMPLATE = """You are an expert short-form video editor who has cut thousands of viral \
TikTok/Reels/Shorts clips from long-form video. You are given a timestamped transcript of a \
video. Identify the {n_min}-{n_max} best possible short clips to extract.

Each clip must:
- Be between {min_s} and {max_s} seconds long.
- Start and end at natural sentence/thought boundaries (never mid-sentence).
- Be understandable on its own, without needing context from the rest of the video.
- Have a strong hook in the first 1-3 seconds (a bold claim, question, or surprising statement).

Prioritize: emotional intensity, humor, surprising or counter-intuitive claims, concrete \
storytelling, clear educational payoff, and moments of high energy or conflict.

Respond with ONLY a JSON object of the form {{"clips": [...]}} (no prose, no markdown fences). \
Each element of "clips" must look like:
{{
  "start": <float seconds>,
  "end": <float seconds>,
  "viral_score": <integer 1-100>,
  "reason": "<one sentence on why this clip works>",
  "title": "<punchy title under 60 characters>",
  "hashtags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"]
}}
Order "clips" by viral_score descending."""


def _build_transcript_block(segments: list[dict]) -> str:
    lines = []
    for seg in segments:
        lines.append(f"[{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}")
    return "\n".join(lines)


def detect_viral_moments(segments: list[dict], video_duration: float) -> list[dict]:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set")

    n_min, n_max = 3, min(20, max(3, int(video_duration // 90)))
    system = SYSTEM_PROMPT_TEMPLATE.format(
        n_min=n_min, n_max=n_max, min_s=MIN_CLIP_SECONDS, max_s=MAX_CLIP_SECONDS
    )
    transcript_block = _build_transcript_block(segments)

    resp = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "temperature": 0.4,
            "max_tokens": 4000,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        f"Video duration: {video_duration:.1f} seconds.\n\n"
                        f"Timestamped transcript:\n{transcript_block}"
                    ),
                },
            ],
        },
        timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:500]}")

    raw = resp.json()["choices"][0]["message"]["content"].strip()
    raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()

    try:
        parsed = json.loads(raw)
        clips = parsed["clips"] if isinstance(parsed, dict) else parsed
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise RuntimeError(f"Could not parse the model's response as JSON: {e}\nRaw: {raw[:500]}")

    cleaned = []
    for c in clips:
        start = max(0.0, float(c["start"]))
        end = min(video_duration, float(c["end"]))
        if end - start < 2:
            continue
        if end - start > MAX_CLIP_SECONDS:
            end = start + MAX_CLIP_SECONDS
        cleaned.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "viral_score": int(c.get("viral_score", 50)),
            "reason": c.get("reason", ""),
            "title": c.get("title", "Untitled clip"),
            "hashtags": c.get("hashtags", []),
        })
    return cleaned
