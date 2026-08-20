#!/usr/bin/env python3
"""Transcreve áudio com a API Whisper (whisper-1). Faz chunk se o arquivo passar de ~24 MB."""
from __future__ import annotations

import argparse
import math
import tempfile
from pathlib import Path

import common


def plan_chunks(size_bytes: int, duration: float | None, max_bytes: int = common.MAX_WHISPER_BYTES) -> list[tuple[float, float]]:
    """Lista de (start, length) em segundos. Um único chunk (0, duration) se couber."""
    if size_bytes <= max_bytes:
        return [(0.0, duration or 0.0)]
    if not duration or duration <= 0:
        n = max(2, math.ceil(size_bytes / max_bytes))
        return [(float(i), 0.0) for i in range(n)]  # filled later by caller if no duration
    n = max(2, math.ceil(size_bytes / max_bytes))
    chunk_len = duration / n
    overlap = 1.0 if chunk_len > 3 else 0.0
    plan = []
    for i in range(n):
        start = max(0.0, i * chunk_len - (overlap if i else 0.0))
        end = min(duration, (i + 1) * chunk_len)
        length = max(0.1, end - start)
        plan.append((start, length))
    return plan


def split_audio(path: Path, dest_dir: Path) -> list[tuple[Path, float]]:
    size = path.stat().st_size
    duration = common.probe_duration_seconds(path)
    if size <= common.MAX_WHISPER_BYTES:
        return [(path, 0.0)]
    if not duration:
        common.fail(
            "Arquivo maior que 24 MB e não deu para obter a duração com ffprobe. "
            "Não consigo fatiar para o Whisper."
        )
    common.require_binaries("ffmpeg")
    plan = plan_chunks(size, duration)
    chunks: list[tuple[Path, float]] = []
    for i, (start, length) in enumerate(plan):
        out = dest_dir / f"chunk_{i:03d}.mp3"
        common.run_cmd(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{length:.3f}",
                "-i",
                str(path),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "libmp3lame",
                "-q:a",
                "4",
                str(out),
            ]
        )
        chunks.append((out, start))
    return chunks


def transcribe_file(client, path: Path, language: str | None) -> dict:
    kwargs = {
        "model": common.WHISPER_MODEL,
        "file": path.open("rb"),
        "response_format": "verbose_json",
        "timestamp_granularities": ["segment"],
    }
    code = common.language_code(language)
    if code:
        kwargs["language"] = code
    try:
        try:
            result = client.audio.transcriptions.create(**kwargs)
        except TypeError:
            kwargs.pop("timestamp_granularities", None)
            result = client.audio.transcriptions.create(**kwargs)
    finally:
        kwargs["file"].close()
    if hasattr(result, "model_dump"):
        data = result.model_dump()
    elif isinstance(result, dict):
        data = result
    else:
        data = json_like(result)
    return data


def json_like(obj) -> dict:
    text = getattr(obj, "text", "")
    segments = []
    for seg in getattr(obj, "segments", None) or []:
        if isinstance(seg, dict):
            segments.append(seg)
        else:
            segments.append(
                {
                    "start": getattr(seg, "start", 0.0),
                    "end": getattr(seg, "end", 0.0),
                    "text": getattr(seg, "text", ""),
                }
            )
    return {
        "text": text,
        "segments": segments,
        "language": getattr(obj, "language", None),
        "duration": getattr(obj, "duration", None),
    }


def merge_chunk_results(parts: list[tuple[dict, float]]) -> dict:
    texts: list[str] = []
    segments: list[dict] = []
    language = None
    last_end = -1.0
    for data, offset in parts:
        language = language or data.get("language")
        text = (data.get("text") or "").strip()
        if text:
            texts.append(text)
        for seg in data.get("segments") or []:
            start = float(seg.get("start") or 0.0) + offset
            end = float(seg.get("end") or start) + offset
            if start < last_end - 0.25:
                continue
            piece = str(seg.get("text") or "").strip()
            if not piece:
                continue
            segments.append({"start": start, "end": end, "text": piece})
            last_end = end
    return {
        "text": " ".join(texts).strip(),
        "segments": segments,
        "language": language,
    }


def transcribe(input_path: str, language: str | None) -> dict:
    common.require_openai_key()
    common.require_openai_package()
    path = Path(input_path).expanduser()
    if not path.is_file():
        common.fail(f"Arquivo de áudio não encontrado: {path}")

    client = common.openai_client()
    with tempfile.TemporaryDirectory(prefix="transcribe-chunks-") as tmp:
        chunks = split_audio(path, Path(tmp))
        parts = []
        for chunk_path, offset in chunks:
            data = transcribe_file(client, chunk_path, language)
            parts.append((data, offset))
        merged = merge_chunk_results(parts)

    duration = common.probe_duration_seconds(path)
    if not merged["segments"] and merged["text"]:
        merged["segments"] = [
            {"start": 0.0, "end": duration or 0.0, "text": merged["text"]}
        ]
    return {
        "text": merged["text"],
        "segments": merged["segments"],
        "language": merged.get("language") or language,
        "duration_seconds": duration,
        "duration": common.format_duration(duration),
        "audio_path": str(path.resolve()),
        "model": common.WHISPER_MODEL,
        "chunk_count": len(parts),
        "method": "whisper",
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Transcreve áudio com whisper-1.")
    parser.add_argument("--input", "-i", required=True, help="Arquivo de áudio")
    parser.add_argument("--language", "--lang", dest="language", help="Código ISO se o usuário pediu o idioma da fala")
    args = parser.parse_args(argv)
    common.emit_ok(**transcribe(args.input, args.language))


if __name__ == "__main__":
    main()
