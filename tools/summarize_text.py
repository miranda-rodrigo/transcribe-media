#!/usr/bin/env python3
"""Resumo curto além da transcrição — nunca no lugar dela."""
from __future__ import annotations

import argparse
from pathlib import Path

import common

SYSTEM = """Você resume transcrições de fala.
Escreva um resumo curto (um a três parágrafos, ou tópicos se a fala for uma reunião).
Não invente fatos. Não substitua a transcrição — isto é um extra.
Sem markdown de título. Sem preâmbulo ("aqui está o resumo").
Responda no mesmo idioma da transcrição, salvo se o usuário pedir outro.
"""


def summarize(text: str, language: str | None) -> dict:
    raw = (text or "").strip()
    if not raw:
        common.fail("Texto vazio; não há o que resumir.")
    chunks = common.chunk_text(raw)
    if len(chunks) == 1:
        user = raw
        if language:
            user = f"Idioma do resumo: {language}.\n\n{raw}"
        summary = common.chat_complete(SYSTEM, user)
    else:
        partial = []
        for i, chunk in enumerate(chunks):
            user = f"Resuma o trecho {i + 1} de {len(chunks)}:\n\n{chunk}"
            partial.append(common.chat_complete(SYSTEM, user))
        joined = "\n\n".join(partial)
        final_user = "Una estes resumos parciais num resumo curto único:\n\n" + joined
        if language:
            final_user = f"Idioma do resumo: {language}.\n\n{final_user}"
        summary = common.chat_complete(SYSTEM, final_user)
    return {
        "text": summary.strip(),
        "model": common.CHAT_MODEL,
        "chunk_count": len(chunks),
        "method": "summarize",
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Gera resumo curto; a transcrição continua obrigatória.")
    parser.add_argument("--input", "-i")
    parser.add_argument("--text")
    parser.add_argument("--language", "--lang", dest="language")
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
    common.emit_ok(**summarize(source, args.language))


if __name__ == "__main__":
    main()
