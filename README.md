# Transcribe Media

Skill de transcrição para Cursor, Claude Code e Cloud Agent.

Contrato: [project.md](project.md). Orquestração: [SKILL.md](SKILL.md).

## O que isto é

O usuário aponta arquivo, URL ou texto com fala. A skill devolve transcrição **bruta** (arquivo + texto no chat) e **pergunta** o que fazer depois: bruta, melhorada com IA, limpa sem IA, outro idioma, timestamps, resumo.

Não é feature da Aisha no WhatsApp.

## Layout

```
SKILL.md
project.md
tools/          # um passo cada; JSON no stdout
references/refine-prompt.md
transcripts/    # saída (não versionar o conteúdo)
```

## Como usar

Na raiz do repositório (ative `.venv` se existir):

```bash
python3 tools/detect_source.py "arquivo.mp4"
python3 tools/extract_audio.py --input "arquivo.mp4" --output /tmp/a.mp3
python3 tools/transcribe_audio.py --input /tmp/a.mp3
python3 tools/write_output.py --slug exemplo --raw-text "..." --out-root transcripts
```

Tools de texto (testáveis sem Whisper):

```bash
python3 tools/normalize_text.py --input legendas.srt
python3 tools/cleanup_text.py --input transcripts/exemplo/raw.txt
```

## Dependências

A skill **não instala sozinha**. Precisa, quando a fonte exige:

- `ffmpeg` / `ffprobe`
- `yt-dlp` (URLs)
- pacote Python `openai` + `OPENAI_API_KEY` (Whisper, melhoria, tradução, resumo)

Lista Python: [requirements.txt](requirements.txt).

## Testes

Sem instalar nada além da stdlib:

```bash
python3 -m unittest discover -s tests -v
```
