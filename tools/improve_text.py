#!/usr/bin/env python3
"""Melhoria editorial com IA. Não resume. Não altera o bruto no disco."""
from __future__ import annotations

import argparse
from pathlib import Path

import common


def load_prompt(prompt_file: str | None) -> str:
    path = Path(prompt_file) if prompt_file else common.repo_root() / "references" / "refine-prompt.md"
    if not path.is_file():
        common.fail(f"Prompt editorial não encontrado: {path}")
    return path.read_text(encoding="utf-8")


def improve(text: str, prompt_file: str | None) -> dict:
    raw = (text or "").strip()
    if not raw:
        common.fail("Texto bruto vazio; não há o que melhorar.")
    system = load_prompt(prompt_file)
    chunks = common.chunk_text(raw)
    pieces = []
    for i, chunk in enumerate(chunks):
        user = chunk
        if len(chunks) > 1:
            user = (
                f"Parte {i + 1} de {len(chunks)} da transcrição bruta. "
                "Edite só este trecho, sem resumir.\n\n"
                f"{chunk}"
            )
        pieces.append(common.chat_complete(system, user, temperature=0.2))
    improved = "\n\n".join(pieces).strip()
    return {
        "text": improved,
        "model": common.CHAT_MODEL,
        "chunk_count": len(chunks),
        "method": "improve",
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Edita o bruto com um chat model barato/rápido.")
    parser.add_argument("--input", "-i")
    parser.add_argument("--text")
    parser.add_argument("--prompt-file", default=None)
    args = parser.parse_args(argv)
    if args.text is not None:
        source = args.text
    elif args.input:
        path = Path(args.input).expanduser()
        if not path.is_file():
            common.fail(f"Arquivo não encontrado: {path}")
        source = path.read_text(encoding="utf-8")
    else:
        common.fail("Informe --input ou --text.")
    common.emit_ok(**improve(source, args.prompt_file))


if __name__ == "__main__":
    main()
