---
name: transcribe-media
description: Transcreve fala de arquivo local, URL (YouTube, X) ou texto/SRT/VTT. Use quando o usuário pedir transcrição, legendas, Whisper, SRT, VTT, ou apontar vídeo, áudio, opus, mp3, mp4 ou link com fala.
---

# Transcribe Media

Skill de transcrição. Não é feature da Aisha no WhatsApp.

Contrato: [project.md](project.md). A skill orquestra; cada passo é uma tool em `tools/`. Nenhuma tool melhora o bruto por conta própria.

## Regras que não quebram

1. Bruto primeiro. Whisper/legendas são a fonte da verdade.
2. Depois do bruto: **perguntar** o que fazer (bruta, melhorada, limpa, idioma, timestamps, resumo), salvo intenção já inequívoca (`quero o bruto em inglês, arquivo .srt`). “Transcreve e melhora” **ainda pergunta**.
3. Sempre **texto no chat + arquivo no disco**. Exceção só se o usuário pedir só um dos dois.
4. Sem instalar nada sem perguntar (`ffmpeg`, `yt-dlp`, pacote `openai`). Se faltar, pare e pergunte.
5. Uma chave: `OPENAI_API_KEY`. Sem ela, não invente fala. Legendas via `yt-dlp` podem seguir; Whisper / melhoria / tradução / resumo não.
6. Não treinar modelo. Não baixar Whisper local.
7. Se existir `.venv` na raiz, ative antes de rodar as tools.
8. Trabalhe na raiz desta skill. Tools imprimem JSON em stdout (`ok: true|false`).

## Tools

Rodar com `python3 tools/<nome>.py`. Diretório das tools precisa estar importável — chamar o script pelo caminho (`python3 tools/detect_source.py`) já resolve.

| Tool | Função |
|---|---|
| `detect_source.py` | Classifica arquivo / URL / texto |
| `extract_audio.py` | ffmpeg (local) ou yt-dlp+ffmpeg (URL) → mp3 16 kHz mono |
| `fetch_captions.py` | yt-dlp legendas; `captions: null` se não houver |
| `transcribe_audio.py` | Whisper API (`whisper-1`), chunk se > ~24 MB |
| `normalize_text.py` | `.txt` / `.srt` / `.vtt` → bruto |
| `cleanup_text.py` | Limpeza sem IA |
| `improve_text.py` | Melhoria com IA (`gpt-4o-mini` + `references/refine-prompt.md`) |
| `translate_text.py` | Tradução; bruto intacto |
| `summarize_text.py` | Resumo **além** da transcrição |
| `write_output.py` | Grava `transcripts/<slug>/` e devolve prévia |

## Fluxo

```
fonte → detect_source
  vídeo/áudio → extract_audio → transcribe_audio
  URL → fetch_captions → se vazio: extract_audio + transcribe_audio
  .txt/.srt/.vtt → normalize_text
→ write_output (sempre raw.txt + meta.json; raw.srt se houver timestamps)
→ prévia do BRUTO no chat + caminho
→ PERGUNTAR
→ opcionais → write_output de novo nos arquivos extras → entregar
```

### 1. Detectar

```bash
python3 tools/detect_source.py "FONTE"
```

`kind`: `video` | `audio` | `text` | `url` | `unsupported`.

Se `unsupported` ou arquivo sem áudio: diga **Não consigo transcrever isso.** e pare.

### 2. Obter o bruto

**Texto (`.txt` `.srt` `.vtt`):**

```bash
python3 tools/normalize_text.py --input "CAMINHO"
```

**URL:**

```bash
python3 tools/fetch_captions.py --url "URL"
```

Se `captions` vier preenchido, método = `captions`. Se `captions` for `null`, extraia áudio da mesma URL e mande ao Whisper.

**Vídeo/áudio (e URL sem legenda):**

```bash
python3 tools/extract_audio.py --input "FONTE" --output /tmp/transcribe-audio.mp3
python3 tools/transcribe_audio.py --input /tmp/transcribe-audio.mp3
```

`--language` no Whisper só se o usuário pediu o idioma **da fala** (não o idioma de entrega traduzida).

Slug: derive do nome do arquivo, título da URL, ou `slug` se a tool já sugerir. Use só `[a-z0-9-]`.

### 3. Gravar o bruto (sempre)

```bash
python3 tools/write_output.py \
  --slug "SLUG" \
  --raw-text "TEXTO_BRUTO" \
  --out-root transcripts \
  --meta '{"source":"...","method":"whisper|captions|text","duration":null,"detected_language":null,"requested_language":null,"tools":["detect_source","...","write_output"]}'
```

Se houver `segments`, passe `--segments-json` para gerar `raw.srt` / `raw.vtt`.

`meta.json` fica no mesmo diretório. Não apague `raw.txt` depois.

### 4. Mostrar e perguntar

No chat:

- Prévia (~80–120 palavras; a tool já devolve `preview`). Se `full_text_in_chat` for true, mande o texto inteiro.
- Caminho completo dos arquivos.
- Duração e idioma se souber.

Pergunta padrão (o usuário pode combinar opções):

> Transcrição bruta pronta (`duração`, `idioma`). Prévia: “…”
> Arquivo: `transcripts/<slug>/raw.txt`
>
> Quer a versão bruta, melhorada com IA, limpa sem IA, em outro idioma, com timestamps, ou um resumo junto?

**Não pergunte de novo** só se a primeira mensagem já fechou o entregável (variante + idioma + formato). Aí execute direto depois de gravar o bruto.

### 5. Opções

| Pedido | Tool | Arquivo |
|---|---|---|
| Bruta | já está em `raw.txt` | — |
| Limpa (sem IA) | `cleanup_text.py --input transcripts/<slug>/raw.txt` | `cleaned.txt` |
| Melhorada (IA) | `improve_text.py --input .../raw.txt` | `improved.txt` |
| Outro idioma | `translate_text.py --input ... --target-lang pt` | `raw.pt.txt` (e `improved.pt.txt` se também melhorou) |
| Timestamps | já deve ter segmentos; senão gere SRT/VTT via `write_output --segments-json` | `raw.srt` / `raw.vtt` |
| Resumo | `summarize_text.py --input ...` | `summary.txt` **além** da transcrição |
| As duas | bruto + improved | os dois textos (se for enorme: bruto no arquivo, melhorado no chat, e vice-versa se fizer mais sentido — mas os dois arquivos no disco) |

Grave extras no mesmo slug:

```bash
python3 tools/write_output.py \
  --slug "SLUG" \
  --raw-file transcripts/SLUG/raw.txt \
  --cleaned-text "..." \
  --improved-text "..." \
  --summary-text "..." \
  --extra "raw.en.txt" "..." \
  --meta '...'
```

`write_output` reescreve `raw.txt` com o mesmo bruto — não substitui por versão melhorada.

## Idioma

- Não pediu: bruto no idioma da fala.
- Pediu o mesmo da fala: Whisper com `--language`.
- Pediu outro: bruto permanece fiel; a entrega no idioma pedido é **tradução** em arquivo separado. Nunca traduzir por cima do `raw.txt`.

## Dependências

Antes da tool que precisa:

- `ffmpeg` / `ffprobe` — extract + duração + chunk Whisper
- `yt-dlp` — URLs e legendas
- `openai` (Python) — Whisper e chat
- `OPENAI_API_KEY` — Whisper, improve, translate, summarize

Se a tool devolver `ok: false` com `missing` e `install_without_asking: false`, **pergunte**. Não rode `pip` / `apt` sozinho.

Modelo de chat: `gpt-4o-mini`. Whisper: `whisper-1`.

## Fora de escopo

WhatsApp da Aisha, diarização, Whisper local, burn-in de legenda, cortar vídeo.
