#!/usr/bin/env python3
"""Limpeza determinística, sem IA: espaços, pontuação grudada, pausas óbvias."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import common

# Pausas óbvias. "um" só some como hesitação (vírgulas/reticências), nunca o artigo "um cara".
FILLER_RE = re.compile(
    r"\b(?:uh+|uhm+|hum+|hmm+|hã+|ah+|eh+|er+)\b",
    re.IGNORECASE,
)
HESITATION_UM_RE = re.compile(
    r"(?:,\s*um\s*,)|(?:\bum\s*(?:\.{2,}|…|—|--))",
    re.IGNORECASE,
)
STUCK_PUNCT_RE = re.compile(r"([,.!?;:])([^\s\d])")
SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.!?;:])")
MULTI_SPACE_RE = re.compile(r"[ \t]+")
MULTI_COMMA_RE = re.compile(r"(,\s*){2,}")
MULTI_NL_RE = re.compile(r"\n{3,}")

KEEP_WORDS = ("tipo", "né", "então", "entao")


def cleanup(text: str) -> str:
    original_keep = {word: True for word in KEEP_WORDS}
    cleaned = FILLER_RE.sub(" ", text)
    cleaned = HESITATION_UM_RE.sub(" ", cleaned)
    cleaned = STUCK_PUNCT_RE.sub(r"\1 \2", cleaned)
    cleaned = SPACE_BEFORE_PUNCT_RE.sub(r"\1", cleaned)
    cleaned = MULTI_COMMA_RE.sub(", ", cleaned)
    cleaned = MULTI_SPACE_RE.sub(" ", cleaned)
    cleaned = MULTI_NL_RE.sub("\n\n", cleaned)
    lines = [line.strip() for line in cleaned.split("\n")]
    cleaned = "\n".join(lines).strip()
    # sanity: palavras reais de estilo não podem sumir se estavam no bruto
    lowered = cleaned.lower()
    source_lower = text.lower()
    for word in original_keep:
        if word in source_lower and word not in lowered and word != "entao":
            # não reinsere; o teste garante que o algoritmo não apaga. aqui só documenta.
            pass
    return cleaned


def load_input(path: str | None, text: str | None) -> str:
    if text is not None:
        return text
    if not path:
        common.fail("Informe --input ou --text.")
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        common.fail(f"Arquivo não encontrado: {file_path}")
    return file_path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Limpa transcrição bruta sem chamar modelo.")
    parser.add_argument("--input", "-i")
    parser.add_argument("--text")
    args = parser.parse_args(argv)
    source = load_input(args.input, args.text)
    result = cleanup(source)
    common.emit_ok(text=result, method="cleanup")


if __name__ == "__main__":
    main()
