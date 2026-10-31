"""Voice-note check (V1 of the voice PRD). audio -> transcript -> sentences with times -> the SAME review pipeline as documents.

Every finding quotes a sentence of the stored English transcript (`version.content`). The original-language transcript is display-only.
Timing: the speech API returns one segment for a short clip, so each sentence gets an APPROXIMATE time, spread over the clip by character position.
That limitation is stored with the clip and shown in the console.
"""
from __future__ import annotations

import hashlib
import io
import re
import uuid
import wave
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

from niyam.config import get_settings
from niyam.db import audit
from niyam.llm import speech
from niyam.review import blobs, pipeline, service

AUDIO_TYPES = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".webm": "audio/webm", ".aac": "audio/aac", ".flac": "audio/flac"}
_SPLIT = re.compile(r"(?<=[.!?])\s+")


def sentences_with_times(english: str, segments: list[dict], duration: float) -> tuple[list[dict], str]:
    """Split the English transcript into sentences and give each a start/end time."""
    spans, last = [], 0
    for m in _SPLIT.finditer(english):
        spans.append((last, m.start()))
        last = m.end()
    spans.append((last, len(english)))
    spans = [(a, b) for a, b in spans if english[a:b].strip()]
    total = max(1, len(english))
    exact = len(segments) > 1
    out = []
    for i, (a, b) in enumerate(spans):
        if exact:                                       # several segments: take the time of the segment holding this sentence
            pos = 0
            seg = segments[-1]
            for sg in segments:
                pos += len(sg["text"]) + 1
                if a < pos:
                    seg = sg
                    break
            st, en = seg["start"], seg["end"]
        else:
            st, en = duration * a / total, duration * b / total
        out.append({"idx": i, "start": round(st, 2), "end": round(en, 2), "text": english[a:b], "start_char": a, "end_char": b})
    note = ("Times are taken from the speech API's segments." if exact else
            "Approximate: the speech API returned a single segment for this clip, so sentence times are spread by position in the transcript.")
    return out, note


def _duration(data: bytes, filename: str, reported: float) -> float:
    if filename.lower().endswith(".wav"):
        try:
            with wave.open(io.BytesIO(data)) as w:
                return round(w.getnframes() / float(w.getframerate()), 2)
        except Exception:  # noqa: BLE001
            pass
    return round(reported, 2)


def check_clip(conn: Connection, data: bytes, filename: str, *, title: str | None, owner: str, product: str, merchant: str | None, actor: str,
               synthetic: bool = False, expected: str | None = None) -> uuid.UUID:
    ext = Path(filename).suffix.lower()
    if ext not in AUDIO_TYPES:
        raise ValueError("unsupported_audio")
    tr = speech.transcribe(data, filename, AUDIO_TYPES[ext])
    if len(tr["english"]) < 8:
        raise ValueError("no_speech")
    dur = _duration(data, filename, tr["duration"])
    sents, note = sentences_with_times(tr["english"], tr["segments"], dur)
    sha = hashlib.sha256(data).hexdigest()
    path = f"voice/{sha[:16]}.audio"
    did = service._upsert_document(conn, path, {"title": title or Path(filename).stem.replace("-", " ").title() + " (voice note)", "doc_type": "voice_note",
                                                "product": product, "owner": owner, "merchant": merchant or "", "channel": "voice"}, "voice")
    media = {"duration_seconds": dur, "language": tr["language"], "language_probability": tr["language_probability"], "transcript_original": tr["original"],
             "sentences": sents, "stt": {"provider": "sarvam", "model": speech.MODEL}, "timing_note": note, "synthetic": synthetic, "filename": filename}
    if expected:
        media["expected"] = expected
    vid, _, _ = service._add_version(conn, did, tr["english"], "upload", None, actor, file_sha=sha, content_type=AUDIO_TYPES[ext], blob=data, media=media)
    pipeline.review_version(conn, vid, "upload", actor=actor)
    audit.append(conn, actor=actor, action="voice.checked", object_type="document", object_id=str(did),
                 payload={"document_id": str(did), "audio_sha256": sha, "duration_seconds": dur, "language": tr["language"], "stt_model": speech.MODEL, "synthetic": synthetic})
    return did


SAMPLES = {
    "hinglish-settlement": ("Hinglish: settlement and approval promise", "hi-IN", "Promises settlement in two hours, no KYC trouble, guaranteed approval."),
    "english-fees": ("English: fees and hidden charges", "en-IN", "Says no hidden charges on any mode, 2.25% card MDR and 0.5% UPI."),
    "compliant-note": ("English: compliant note (control)", "en-IN", "Mentions the T+2 cycle, KYC and a 3-5 working day activation. Should mostly pass."),
}


def list_samples() -> list[dict]:
    d = get_settings().library_path / "_voice"
    out = []
    for name, (title, lang, expected) in SAMPLES.items():
        p = d / f"{name}.wav"
        if not p.exists():
            continue
        out.append({"name": name, "title": title, "language": lang, "duration_seconds": _duration(p.read_bytes(), p.name, 0.0),
                    "audio_url": f"/api/v1/voice/samples/{name}/audio", "expected": expected})
    return out
