#!/usr/bin/env python3
"""Extrai áudio com ffmpeg (arquivo local) ou yt-dlp (URL)."""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import common


def download_url_audio(url: str, dest: Path) -> Path:
    common.require_binaries("yt-dlp")
    dest.parent.mkdir(parents=True, exist_ok=True)
    out_tmpl = str(dest.with_suffix(""))
    common.run_cmd(
        [
            "yt-dlp",
            "-x",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "5",
            "--no-playlist",
            "-o",
            out_tmpl + ".%(ext)s",
            url,
        ]
    )
    found = list(dest.parent.glob(dest.stem + ".*"))
    audio = [p for p in found if p.suffix.lower() in common.AUDIO_EXTS | {".mp3"}]
    if not audio:
        common.fail("yt-dlp não gerou arquivo de áudio.", url=url)
    return audio[0]


def extract(input_path: str, output_path: str | None) -> dict:
    common.require_binaries("ffmpeg", "ffprobe")
    source = input_path.strip()
    tmp_dir = None
    try:
        if common.looks_like_url(source) and not source.lower().startswith("file://"):
            tmp_dir = tempfile.TemporaryDirectory(prefix="transcribe-dl-")
            work = download_url_audio(source, Path(tmp_dir.name) / "download.mp3")
        else:
            work = Path(source).expanduser()
            if not work.is_file():
                common.fail(f"Arquivo não encontrado: {work}")

        audio = common.has_audio_stream(work)
        if audio is False:
            common.fail("Não consigo transcrever isso.", detail="Arquivo sem faixa de áudio.")

        if output_path:
            out = Path(output_path).expanduser()
        else:
            out = work.with_name(work.stem + ".extracted.mp3")
        out.parent.mkdir(parents=True, exist_ok=True)

        common.run_cmd(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(work),
                "-vn",
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
        if not out.is_file() or out.stat().st_size == 0:
            common.fail("ffmpeg não gerou o áudio extraído.")

        duration = common.probe_duration_seconds(out)
        return {
            "audio_path": str(out.resolve()),
            "source": source,
            "duration_seconds": duration,
            "duration": common.format_duration(duration),
            "size_bytes": out.stat().st_size,
        }
    finally:
        if tmp_dir is not None:
            tmp_dir.cleanup()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extrai faixa de áudio para mp3 16 kHz mono.")
    parser.add_argument("--input", "-i", required=True, help="Arquivo local ou URL")
    parser.add_argument("--output", "-o", help="Caminho do mp3 de saída")
    args = parser.parse_args(argv)
    common.emit_ok(**extract(args.input, args.output))


if __name__ == "__main__":
    main()
