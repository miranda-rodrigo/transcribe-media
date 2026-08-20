#!/usr/bin/env python3
"""Baixa legendas com yt-dlp (YouTube, X, etc.). Não transcreve."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import common
import normalize_text


def dump_info(url: str) -> dict:
    result = common.run_cmd(
        ["yt-dlp", "--dump-json", "--no-playlist", "--skip-download", url]
    )
    try:
        return json.loads(result.stdout.splitlines()[0])
    except (json.JSONDecodeError, IndexError):
        common.fail("yt-dlp não devolveu metadados JSON.", url=url)


def pick_sub_langs(info: dict, requested: str | None) -> str:
    wanted = []
    code = common.language_code(requested)
    if code:
        wanted.extend([f"{code}.*", code])
    original = (info.get("language") or info.get("original_language") or "").strip()
    if original:
        wanted.append(original)
    wanted.extend(["pt.*", "pt", "en.*", "en", "best"])
    # unique, keep order
    seen = set()
    ordered = []
    for item in wanted:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ",".join(ordered)


def download_subs(url: str, dest_dir: Path, langs: str, auto: bool) -> None:
    args = [
        "yt-dlp",
        "--skip-download",
        "--no-playlist",
        "--sub-langs",
        langs,
        "--sub-format",
        "vtt/srt/best",
        "--convert-subs",
        "vtt",
        "-P",
        str(dest_dir),
        "-o",
        "media",
        url,
    ]
    if auto:
        args.insert(3, "--write-auto-subs")
    else:
        args.insert(3, "--write-subs")
    common.run_cmd(args, check=False)


def find_caption_files(dest_dir: Path) -> list[Path]:
    files = []
    for pattern in ("*.vtt", "*.srt"):
        files.extend(sorted(dest_dir.rglob(pattern)))
    return files


def fetch(url: str, language: str | None) -> dict:
    common.require_binaries("yt-dlp")
    if not common.looks_like_url(url):
        common.fail("fetch_captions espera uma URL.", source=url)

    info = dump_info(url)
    title = info.get("title") or info.get("id") or "media"
    duration = info.get("duration")
    langs = pick_sub_langs(info, language)

    with tempfile.TemporaryDirectory(prefix="transcribe-subs-") as tmp:
        dest = Path(tmp)
        download_subs(url, dest, langs, auto=False)
        files = find_caption_files(dest)
        used_auto = False
        if not files:
            download_subs(url, dest, langs, auto=True)
            files = find_caption_files(dest)
            used_auto = True
        if not files:
            return {
                "captions": None,
                "text": None,
                "segments": [],
                "source": url,
                "title": title,
                "duration_seconds": float(duration) if duration else None,
                "duration": common.format_duration(float(duration) if duration else None),
                "language": info.get("language"),
                "auto": False,
                "reason": "sem legendas",
            }

        chosen = files[0]
        parsed = normalize_text.normalize_path(chosen)
        return {
            "captions": parsed["text"],
            "text": parsed["text"],
            "segments": parsed["segments"],
            "source": url,
            "title": title,
            "caption_file": chosen.name,
            "duration_seconds": float(duration) if duration else parsed.get("duration_seconds"),
            "duration": common.format_duration(
                float(duration) if duration else parsed.get("duration_seconds")
            ),
            "language": parsed.get("language") or info.get("language"),
            "auto": used_auto,
            "method": "captions",
        }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Tenta legendas via yt-dlp; se vazio, captions=null.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--language", "--lang", dest="language", help="Idioma preferido das legendas")
    args = parser.parse_args(argv)
    common.emit_ok(**fetch(args.url, args.language))


if __name__ == "__main__":
    main()
