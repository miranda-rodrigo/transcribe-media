#!/usr/bin/env python3
"""Normaliza .txt / .srt / .vtt em texto bruto (+ segmentos se houver timestamps)."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import common

TS_RE = re.compile(
    r"(?:(\d{2}):)?(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(?:(\d{2}):)?(\d{2}):(\d{2})[.,](\d{3})"
)
TAG_RE = re.compile(r"</?[^>]+>")
VTT_META_RE = re.compile(r"^(WEBVTT|NOTE|STYLE|REGION)\b", re.I)


def ts_to_seconds(h: str | None, m: str, s: str, ms: str) -> float:
    hours = int(h or 0)
    return hours * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def strip_tags(text: str) -> str:
    text = TAG_RE.sub("", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"[ \t]+", " ", text).strip()


def parse_cues(content: str) -> list[dict]:
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cues: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or VTT_META_RE.match(line) or line.startswith("NOTE "):
            i += 1
            continue
        match = TS_RE.search(line)
        if not match:
            i += 1
            continue
        start = ts_to_seconds(match.group(1), match.group(2), match.group(3), match.group(4))
        end = ts_to_seconds(match.group(5), match.group(6), match.group(7), match.group(8))
        i += 1
        text_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            piece = lines[i].strip()
            if TS_RE.search(piece) or (piece.isdigit() and not text_lines):
                break
            text_lines.append(strip_tags(piece))
            i += 1
        text = " ".join(t for t in text_lines if t).strip()
        if text:
            cues.append({"start": start, "end": end, "text": text})
    return cues


def cues_to_text(cues: list[dict]) -> str:
    return " ".join(c["text"] for c in cues).strip()


def normalize_content(content: str, extension: str) -> dict:
    ext = extension.lower()
    if not ext.startswith("."):
        ext = f".{ext}"
    if ext in {".srt", ".vtt"}:
        segments = parse_cues(content)
        text = cues_to_text(segments)
        duration = segments[-1]["end"] if segments else None
        return {
            "text": text,
            "segments": segments,
            "duration_seconds": duration,
            "method": "text",
            "has_timestamps": bool(segments),
        }
    text = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    return {
        "text": text,
        "segments": [],
        "duration_seconds": None,
        "method": "text",
        "has_timestamps": False,
    }


def normalize_path(path: str | Path) -> dict:
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        common.fail(f"Arquivo não encontrado: {file_path}")
    ext = file_path.suffix.lower()
    if ext not in common.TEXT_EXTS:
        common.fail(
            "normalize_text só aceita .txt, .srt ou .vtt.",
            extension=ext or None,
        )
    content = file_path.read_text(encoding="utf-8", errors="replace")
    data = normalize_content(content, ext)
    data["source"] = str(file_path.resolve())
    data["extension"] = ext
    return data


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Converte txt/srt/vtt em texto bruto.")
    parser.add_argument("--input", "-i", required=True)
    args = parser.parse_args(argv)
    common.emit_ok(**normalize_path(args.input))


if __name__ == "__main__":
    main()
