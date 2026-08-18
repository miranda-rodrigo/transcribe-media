#!/usr/bin/env python3
"""Classifica a fonte: arquivo de vídeo/áudio/texto, URL, ou não suportado."""
from __future__ import annotations

import argparse
from pathlib import Path

import common


def classify(source: str) -> dict:
    raw = (source or "").strip()
    if not raw:
        common.fail("Informe um arquivo, URL ou caminho.")

    if common.looks_like_url(raw):
        if raw.lower().startswith("file://"):
            path = Path(raw[7:])
            return classify_path(path, original=raw)
        return {
            "kind": "url",
            "source": raw,
            "exists": None,
            "extension": None,
        }

    path = Path(raw).expanduser()
    return classify_path(path, original=raw)


def classify_path(path: Path, original: str) -> dict:
    ext = path.suffix.lower()
    exists = path.is_file()
    payload = {
        "kind": "unsupported",
        "source": str(path) if exists or path.suffix else original,
        "path": str(path.resolve()) if exists else str(path),
        "exists": exists,
        "extension": ext or None,
    }

    if ext in common.UNSUPPORTED_EXTS:
        payload["reason"] = "Não consigo transcrever isso."
        return payload

    if ext in common.TEXT_EXTS:
        if not exists:
            common.fail(f"Arquivo não encontrado: {path}", path=str(path), kind="text")
        payload["kind"] = "text"
        return payload

    if ext in common.VIDEO_EXTS or ext in common.AUDIO_EXTS:
        if not exists:
            common.fail(f"Arquivo não encontrado: {path}", path=str(path), kind="media")
        kind = "video" if ext in common.VIDEO_EXTS - {".webm"} else "audio"
        if ext == ".webm":
            has_video = common.has_video_stream(path)
            kind = "video" if has_video else "audio"
        elif ext in common.VIDEO_EXTS:
            kind = "video"
        audio = common.has_audio_stream(path)
        if audio is False:
            payload["kind"] = "unsupported"
            payload["reason"] = "Não consigo transcrever isso."
            payload["detail"] = "Arquivo sem faixa de áudio."
            return payload
        payload["kind"] = kind
        payload["duration_seconds"] = common.probe_duration_seconds(path)
        payload["duration"] = common.format_duration(payload["duration_seconds"])
        return payload

    if exists:
        audio = common.has_audio_stream(path)
        if audio:
            has_video = common.has_video_stream(path)
            payload["kind"] = "video" if has_video else "audio"
            payload["duration_seconds"] = common.probe_duration_seconds(path)
            payload["duration"] = common.format_duration(payload["duration_seconds"])
            return payload
        payload["reason"] = "Não consigo transcrever isso."
        return payload

    payload["reason"] = "Não consigo transcrever isso."
    payload["detail"] = "Fonte não é URL, nem arquivo de áudio/vídeo/texto reconhecido."
    return payload


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Classifica arquivo local, URL ou texto já transcrito."
    )
    parser.add_argument("source", help="Caminho local ou URL")
    args = parser.parse_args(argv)
    common.emit_ok(**classify(args.source))


if __name__ == "__main__":
    main()
