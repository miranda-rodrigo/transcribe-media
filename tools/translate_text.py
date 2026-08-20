#!/usr/bin/env python3
"""Traduz transcrição para o idioma pedido. Não sobrescreve o bruto."""
from __future__ import annotations

import argparse
from pathlib import Path

import common

SYSTEM = """Você traduz transcrições de fala.
Preserve o sentido, o tom e a extensão. Não resuma. Não acrescente explicação.
Não use markdown. Devolva somente a tradução.
O idioma de destino vem na mensagem do usuário.
"""


def translate(text: str, target_lang: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        common.fail("Texto vazio; não há o que traduzir.")
    code = common.language_code(target_lang)
    if not code:
        common.fail("Informe o idioma de destino.")
    chunks = common.chunk_text(raw)
    pieces = []
    for i, chunk in enumerate(chunks):
        user = (
            f"Traduza o trecho a seguir para o idioma `{code}` ({target_lang}).\n"
            f"Parte {i + 1} de {len(chunks)}.\n\n{chunk}"
        )
        pieces.append(common.chat_complete(SYSTEM, user))
    return {
        "text": "\n\n".join(pieces).strip(),
        "target_language": code,
        "target_language_raw": target_lang,
        "model": common.CHAT_MODEL,
        "chunk_count": len(chunks),
        "method": "translate",
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Traduz transcrição; o bruto original permanece.")
    parser.add_argument("--input", "-i")
    parser.add_argument("--text")
    parser.add_argument("--target-lang", "--lang", dest="target_lang", required=True)
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
    common.emit_ok(**translate(source, args.target_lang))


if __name__ == "__main__":
    main()
