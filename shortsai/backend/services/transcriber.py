"""Speech-to-text with word-level timestamps, used both for viral-moment
detection (needs a plain transcript) and for word-by-word burned captions
(needs per-word start/end times).
"""
from pathlib import Path
from faster_whisper import WhisperModel

from config import WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE

_model = None


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(
            WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE
        )
    return _model


def transcribe(video_path: Path) -> dict:
    """Returns {"text": full transcript, "words": [{"word","start","end"}, ...],
    "segments": [{"text","start","end"}, ...]}
    """
    model = get_model()
    segments, _info = model.transcribe(
        str(video_path),
        word_timestamps=True,
        vad_filter=True,  # skips silence, which also helps clip boundary quality
    )

    words = []
    seg_list = []
    full_text_parts = []
    for seg in segments:
        seg_list.append({"text": seg.text.strip(), "start": seg.start, "end": seg.end})
        full_text_parts.append(seg.text.strip())
        if seg.words:
            for w in seg.words:
                words.append({"word": w.word.strip(), "start": w.start, "end": w.end})

    return {
        "text": " ".join(full_text_parts),
        "words": words,
        "segments": seg_list,
    }
