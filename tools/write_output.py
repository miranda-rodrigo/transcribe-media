#!/usr/bin/env python3
"""Grava transcripts/<slug>/ e devolve prévia + caminhos para o chat."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import common


def build_meta(meta: dict | None, slug: str, out_dir: Path, extra: dict) -> dict:
    payload = dict(meta or {})
    payload.setdefault("slug", slug)
    payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    payload.setdefault("dir", str(out_dir))
    payload.update({k: v for k, v in extra.items() if v is not None})
    return payload


def write_output(
    *,
    slug: str,
    raw_text: str,
    out_root: str,
    meta: dict | None,
    raw_srt: str | None = None,
    raw_vtt: str | None = None,
    cleaned_text: str | None = None,
    improved_text: str | None = None,
    summary_text: str | None = None,
    extras: list[tuple[str, str]] | None = None,
    segments: list[dict] | None = None,
    preview_words: int = 100,
) -> dict:
    if not (raw_text or "").strip():
        common.fail("raw.txt é obrigatório; texto bruto vazio.")
    safe_slug = common.slugify(slug)
    root = Path(out_root).expanduser()
    out_dir = root / safe_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {}

    raw_path = out_dir / "raw.txt"
    raw_path.write_text(raw_text.strip() + "\n", encoding="utf-8")
    files["raw"] = str(raw_path.resolve())

    srt_body = raw_srt
    if not srt_body and segments:
        srt_body = common.segments_to_srt(segments)
    if srt_body and srt_body.strip():
        path = out_dir / "raw.srt"
        path.write_text(srt_body if srt_body.endswith("\n") else srt_body + "\n", encoding="utf-8")
        files["raw_srt"] = str(path.resolve())

    vtt_body = raw_vtt
    if not vtt_body and segments:
        vtt_body = common.segments_to_vtt(segments)
    if vtt_body and vtt_body.strip():
        path = out_dir / "raw.vtt"
        path.write_text(vtt_body if vtt_body.endswith("\n") else vtt_body + "\n", encoding="utf-8")
        files["raw_vtt"] = str(path.resolve())

    optional = {
        "cleaned": (cleaned_text, "cleaned.txt"),
        "improved": (improved_text, "improved.txt"),
        "summary": (summary_text, "summary.txt"),
    }
    for key, (body, name) in optional.items():
        if body and body.strip():
            path = out_dir / name
            path.write_text(body.strip() + "\n", encoding="utf-8")
            files[key] = str(path.resolve())

    for filename, body in extras or []:
        name = Path(filename).name
        if not name or name in {".", ".."}:
            continue
        path = out_dir / name
        path.write_text((body or "").strip() + "\n", encoding="utf-8")
        files[name] = str(path.resolve())

    preview, word_count, full = common.preview_text(raw_text, max_words=preview_words)
    meta_payload = build_meta(
        meta,
        safe_slug,
        out_dir.resolve(),
        {
            "files": files,
            "word_count": word_count,
        },
    )
    meta_path = out_dir / "meta.json"
    meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files["meta"] = str(meta_path.resolve())
    meta_payload["files"] = files
    meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "dir": str(out_dir.resolve()),
        "slug": safe_slug,
        "files": files,
        "preview": preview,
        "word_count": word_count,
        "full_text_in_chat": full,
        "raw_text": raw_text.strip() if full else None,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Grava transcripts/<slug>/ e devolve prévia para o chat.")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--raw-text")
    parser.add_argument("--raw-file")
    parser.add_argument("--raw-srt")
    parser.add_argument("--raw-vtt")
    parser.add_argument("--cleaned-text")
    parser.add_argument("--improved-text")
    parser.add_argument("--summary-text")
    parser.add_argument("--segments-json", help="JSON da lista de segmentos [{start,end,text}]")
    parser.add_argument("--extra", action="append", nargs=2, metavar=("FILENAME", "TEXT"))
    parser.add_argument("--meta", help="JSON com origem, método, duração, idioma, tools")
    parser.add_argument("--out-root", default="transcripts")
    parser.add_argument("--preview-words", type=int, default=100)
    args = parser.parse_args(argv)

    if args.raw_text is not None:
        raw = args.raw_text
    elif args.raw_file:
        path = Path(args.raw_file).expanduser()
        if not path.is_file():
            common.fail(f"Arquivo não encontrado: {path}")
        raw = path.read_text(encoding="utf-8")
    else:
        common.fail("Informe --raw-text ou --raw-file.")

    segments = common.parse_json_maybe(args.segments_json)
    meta = common.parse_json_maybe(args.meta)
    extras = [(name, text) for name, text in (args.extra or [])]

    common.emit_ok(
        **write_output(
            slug=args.slug,
            raw_text=raw,
            out_root=args.out_root,
            meta=meta if isinstance(meta, dict) else None,
            raw_srt=args.raw_srt,
            raw_vtt=args.raw_vtt,
            cleaned_text=args.cleaned_text,
            improved_text=args.improved_text,
            summary_text=args.summary_text,
            extras=extras,
            segments=segments if isinstance(segments, list) else None,
            preview_words=args.preview_words,
        )
    )


if __name__ == "__main__":
    main()
