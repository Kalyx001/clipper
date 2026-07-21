"""Asks Claude to read the transcript (with timestamps) and pick the
segments most likely to work as standalone vertical shorts: strong hooks,
emotional peaks, humor, surprising claims, self-contained stories.
"""
import json
import re
from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, MAX_CLIP_SECONDS, MIN_CLIP_SECONDS

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You are an expert short-form video editor who has cut thousands of viral \
TikTok/Reels/Shorts clips from long-form video. You are given a timestamped transcript of a \
video. Identify the {n_min}-{n_max} best possible short clips to extract.

Each clip must:
- Be between {min_s} and {max_s} seconds long.
- Start and end at natural sentence/thought boundaries (never mid-sentence).
- Be understandable on its own, without needing context from the rest of the video.
- Have a strong hook in the first 1-3 seconds (a bold claim, question, or surprising statement).

Prioritize: emotional intensity, humor, surprising or counter-intuitive claims, concrete \
storytelling, clear educational payoff, and moments of high energy or conflict.

Respond with ONLY a JSON array (no prose, no markdown fences). Each element:
{{
  "start": <float seconds>,
  "end": <float seconds>,
  "viral_score": <integer 1-100>,
  "reason": "<one sentence on why this clip works>",
  "title": "<punchy title under 60 characters>",
  "hashtags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"]
}}
Order the array by viral_score descending."""


def _build_transcript_block(segments: list[dict]) -> str:
    lines = []
    for seg in segments:
        lines.append(f"[{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}")
    return "\n".join(lines)


def detect_viral_moments(segments: list[dict], video_duration: float) -> list[dict]:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    n_min, n_max = 3, min(20, max(3, int(video_duration // 90)))
    system = SYSTEM_PROMPT.format(
        n_min=n_min, n_max=n_max, min_s=MIN_CLIP_SECONDS, max_s=MAX_CLIP_SECONDS
    )

    transcript_block = _build_transcript_block(segments)

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=system,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Video duration: {video_duration:.1f} seconds.\n\n"
                    f"Timestamped transcript:\n{transcript_block}"
                ),
            }
        ],
    )

    raw = "".join(block.text for block in resp.content if block.type == "text").strip()
    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()

    try:
        clips = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Could not parse Claude's response as JSON: {e}\nRaw: {raw[:500]}")

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
