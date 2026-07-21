"""Builds an .ass subtitle file that shows one word at a time, popping in
sync with speech -- the classic TikTok / CapCut word-by-word caption look --
from faster-whisper's word-level timestamps.
"""
from pathlib import Path

STYLE_PRESETS = {
    "tiktok": dict(font="Arial Black", size=110, primary="&H00FFFFFF", highlight="&H0000D7FF",
                   outline="&H00000000", outline_w=6, shadow=2, margin_v=380, bold=True),
    "minimal": dict(font="Helvetica", size=70, primary="&H00FFFFFF", highlight="&H00FFFFFF",
                    outline="&H00000000", outline_w=2, shadow=0, margin_v=250, bold=False),
    "bold": dict(font="Impact", size=130, primary="&H0000FFFF", highlight="&H000000FF",
                 outline="&H00000000", outline_w=8, shadow=3, margin_v=400, bold=True),
}


def _fmt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _header(preset: dict) -> str:
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,{preset['font']},{preset['size']},{preset['primary']},{preset['highlight']},{preset['outline']},&H00000000,{-1 if preset['bold'] else 0},0,0,0,100,100,0,0,1,{preset['outline_w']},{preset['shadow']},2,60,60,{preset['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def generate_ass(
    words: list[dict],
    clip_start: float,
    clip_end: float,
    output_path: Path,
    style: str = "tiktok",
) -> Path:
    preset = STYLE_PRESETS.get(style, STYLE_PRESETS["tiktok"])
    lines = [_header(preset)]

    relevant = [w for w in words if w["end"] > clip_start and w["start"] < clip_end]

    for w in relevant:
        start = max(w["start"], clip_start) - clip_start
        end = max(w["end"], w["start"] + 0.15) - clip_start
        end = min(end, clip_end - clip_start)
        text = w["word"].strip().upper().replace("{", "").replace("}", "")
        if not text:
            continue
        # simple pop-in scale animation via \t transform on font scale
        anim = r"{\fscx80\fscy80\t(0,80,\fscx105\fscy105)\t(80,150,\fscx100\fscy100)}"
        lines.append(
            f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},Word,,0,0,0,,{anim}{text}"
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
