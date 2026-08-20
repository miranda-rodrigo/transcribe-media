#!/usr/bin/env python3
"""Helpers compartilhados das tools de transcribe-media."""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any

WHISPER_MODEL = "whisper-1"
CHAT_MODEL = "gpt-4o-mini"
MAX_WHISPER_BYTES = 24 * 1024 * 1024

VIDEO_EXTS = {".mp4", ".webm", ".mkv", ".mov", ".avi"}
AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".ogg", ".opus", ".webm", ".aac", ".flac"}
TEXT_EXTS = {".txt", ".srt", ".vtt"}
UNSUPPORTED_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
    ".rar",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def emit_ok(**kwargs: Any) -> None:
    emit({"ok": True, **kwargs})


def fail(message: str, code: int = 1, **kwargs: Any) -> None:
    emit({"ok": False, "error": message, **kwargs})
    raise SystemExit(code)


def which(name: str) -> str | None:
    return shutil.which(name)


def require_binaries(*names: str) -> None:
    missing = [name for name in names if which(name) is None]
    if missing:
        listed = ", ".join(f"`{name}`" for name in missing)
        fail(
            f"Falta {listed}. Posso instalar?",
            missing=missing,
            install_without_asking=False,
        )


def require_openai_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        fail(
            "Falta OPENAI_API_KEY. Sem a chave eu não invento transcrição. "
            "Legendas via yt-dlp podem funcionar; Whisper, melhoria, tradução e resumo não."
        )
    return key


def require_openai_package() -> None:
    try:
        import openai  # noqa: F401
    except ImportError:
        fail(
            "Falta o pacote Python `openai`. Posso instalar?",
            missing=["openai"],
            install_without_asking=False,
        )


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def slugify(text: str, max_len: int = 60) -> str:
    text = strip_accents(str(text or "").strip().lower())
    text = re.sub(r"https?://", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    if not text:
        text = "transcript"
    return text[:max_len].rstrip("-")


def looks_like_url(value: str) -> bool:
    value = (value or "").strip()
    if re.match(r"^(https?|file)://", value, re.I):
        return True
    if re.match(
        r"^(www\.)?(youtube\.com|youtu\.be|x\.com|twitter\.com|tiktok\.com|vimeo\.com)\b",
        value,
        re.I,
    ):
        return True
    return False


def run_cmd(
    args: list[str],
    *,
    cwd: str | Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        fail(
            f"Comando falhou: {' '.join(args)}",
            cmd=args,
            returncode=result.returncode,
            detail=detail[-4000:] if detail else None,
        )
    return result


def probe_duration_seconds(path: str | Path) -> float | None:
    if which("ffprobe") is None:
        return None
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    raw = (result.stdout or "").strip().splitlines()
    if not raw:
        return None
    try:
        value = float(raw[0])
    except ValueError:
        return None
    if math.isnan(value) or math.isinf(value) or value < 0:
        return None
    return value


def has_audio_stream(path: str | Path) -> bool | None:
    if which("ffprobe") is None:
        return None
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return bool((result.stdout or "").strip())


def has_video_stream(path: str | Path) -> bool | None:
    if which("ffprobe") is None:
        return None
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return bool((result.stdout or "").strip())


def format_duration(seconds: float | None) -> str | None:
    if seconds is None:
        return None
    total = int(round(seconds))
    if total < 60:
        return f"{total} s"
    minutes = total // 60
    rest = total % 60
    if minutes < 60:
        return f"{minutes} min" if rest < 15 else f"{minutes} min {rest} s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours} h {minutes} min"


def format_timestamp(seconds: float, *, vtt: bool = False) -> str:
    if seconds < 0:
        seconds = 0.0
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    sep = "." if vtt else ","
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{millis:03d}"


def segments_to_srt(segments: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        start = format_timestamp(float(seg["start"]))
        end = format_timestamp(float(seg["end"]))
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip() + ("\n" if lines else "")


def segments_to_vtt(segments: list[dict[str, Any]]) -> str:
    lines = ["WEBVTT", ""]
    for seg in segments:
        start = format_timestamp(float(seg["start"]), vtt=True)
        end = format_timestamp(float(seg["end"]), vtt=True)
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")
    body = "\n".join(lines).strip()
    return body + "\n"


def preview_text(text: str, max_words: int = 100) -> tuple[str, int, bool]:
    words = [w for w in (text or "").split() if w]
    count = len(words)
    if count <= max_words:
        return (text or "").strip(), count, True
    preview = " ".join(words[:max_words]).strip()
    if not preview.endswith((".", "…", "?", "!")):
        preview += "…"
    return preview, count, False


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def openai_client():
    require_openai_key()
    require_openai_package()
    from openai import OpenAI

    return OpenAI()


def chat_complete(system: str, user: str, *, temperature: float = 0.2) -> str:
    client = openai_client()
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = response.choices[0].message.content
    if not content or not content.strip():
        fail("O modelo devolveu resposta vazia.")
    return content.strip()


def chunk_text(text: str, max_chars: int = 12000) -> list[str]:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return [text] if text else []
    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            parts.append(remaining)
            break
        window = remaining[:max_chars]
        split_at = max(window.rfind("\n\n"), window.rfind("\n"), window.rfind(". "))
        if split_at < max_chars * 0.4:
            split_at = max_chars
        else:
            split_at += 1
        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    return [p for p in parts if p]


def parse_json_maybe(value: str | None) -> Any:
    if value is None or value == "":
        return None
    return json.loads(value)


def language_code(value: str | None) -> str | None:
    if not value:
        return None
    raw = strip_accents(value.strip().lower())
    aliases = {
        "pt": "pt",
        "pt-br": "pt",
        "portugues": "pt",
        "portuguese": "pt",
        "en": "en",
        "ingles": "en",
        "english": "en",
        "es": "es",
        "espanhol": "es",
        "spanish": "es",
        "fr": "fr",
        "frances": "fr",
        "french": "fr",
        "de": "de",
        "alemao": "de",
        "german": "de",
        "it": "it",
        "italiano": "it",
        "italian": "it",
        "ja": "ja",
        "japones": "ja",
        "japanese": "ja",
        "zh": "zh",
        "chines": "zh",
        "chinese": "zh",
    }
    if raw in aliases:
        return aliases[raw]
    if re.fullmatch(r"[a-z]{2}(-[a-z]{2})?", raw):
        return raw.split("-")[0]
    return raw[:8]
