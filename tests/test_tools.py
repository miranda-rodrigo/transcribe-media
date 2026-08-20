from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
FIXTURES = ROOT / "tests" / "fixtures"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import common  # noqa: E402
import cleanup_text  # noqa: E402
import detect_source  # noqa: E402
import extract_audio  # noqa: E402
import normalize_text  # noqa: E402
import transcribe_audio  # noqa: E402
import write_output  # noqa: E402


class DetectSourceTests(unittest.TestCase):
    def test_youtube_url(self):
        data = detect_source.classify("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(data["kind"], "url")

    def test_x_url(self):
        data = detect_source.classify("https://x.com/user/status/123")
        self.assertEqual(data["kind"], "url")

    def test_text_file(self):
        data = detect_source.classify(str(FIXTURES / "sample.txt"))
        self.assertEqual(data["kind"], "text")
        self.assertEqual(data["extension"], ".txt")

    def test_image_unsupported(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
            handle.write(b"not-an-image")
            path = handle.name
        try:
            data = detect_source.classify(path)
            self.assertEqual(data["kind"], "unsupported")
            self.assertEqual(data["reason"], "Não consigo transcrever isso.")
        finally:
            os.unlink(path)

    def test_missing_media_fails(self):
        with self.assertRaises(SystemExit):
            detect_source.classify("/tmp/does-not-exist-transcribe.mp3")

    def test_cli_json(self):
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            detect_source.main([str(FIXTURES / "sample.srt")])
        payload = json.loads(buf.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["kind"], "text")


class NormalizeTests(unittest.TestCase):
    def test_srt(self):
        data = normalize_text.normalize_path(FIXTURES / "sample.srt")
        self.assertIn("Olá, mundo.", data["text"])
        self.assertTrue(data["has_timestamps"])
        self.assertEqual(len(data["segments"]), 2)
        self.assertAlmostEqual(data["segments"][0]["start"], 0.0)
        self.assertAlmostEqual(data["segments"][1]["end"], 5.0)

    def test_vtt_strips_tags(self):
        data = normalize_text.normalize_path(FIXTURES / "sample.vtt")
        self.assertIn("Olá, mundo.", data["text"])
        self.assertNotIn("<c>", data["text"])
        self.assertTrue(data["has_timestamps"])

    def test_txt(self):
        data = normalize_text.normalize_path(FIXTURES / "sample.txt")
        self.assertEqual(data["text"], "Olá, mundo. Uh, eu acho que sim.")
        self.assertFalse(data["has_timestamps"])
        self.assertEqual(data["method"], "text")


class CleanupTests(unittest.TestCase):
    def test_removes_uh_hmm(self):
        text = cleanup_text.cleanup("eu, uh, acho, hmm, que sim")
        self.assertNotIn("uh", text.lower().split())
        self.assertNotIn("hmm", text.lower().split())
        self.assertIn("acho", text)
        self.assertIn("que sim", text)

    def test_keeps_tipo_ne_entao(self):
        source = "então, tipo, né, o cara falou"
        text = cleanup_text.cleanup(source)
        self.assertIn("tipo", text)
        self.assertIn("né", text)
        self.assertIn("então", text)

    def test_keeps_article_um(self):
        text = cleanup_text.cleanup("um cara chegou cedo")
        self.assertIn("um cara", text)

    def test_removes_hesitation_um(self):
        text = cleanup_text.cleanup("eu, um, acho que sim")
        self.assertNotRegex(text.lower(), r",\s*um\s*,")
        self.assertIn("acho", text)

    def test_stuck_punctuation(self):
        text = cleanup_text.cleanup("olá,mundo!tudo bem")
        self.assertIn("olá, mundo", text)
        self.assertIn("mundo! tudo", text)

    def test_does_not_break_decimal(self):
        text = cleanup_text.cleanup("são 3.14 metros")
        self.assertIn("3.14", text)


class WriteOutputTests(unittest.TestCase):
    def test_writes_raw_and_meta(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_output.write_output(
                slug="Entrevista João!",
                raw_text="Olá mundo " * 10,
                out_root=tmp,
                meta={"source": "x.mp3", "method": "text", "tools": ["write_output"]},
            )
            self.assertEqual(result["slug"], "entrevista-joao")
            raw = Path(result["files"]["raw"])
            meta = Path(result["files"]["meta"])
            self.assertTrue(raw.is_file())
            self.assertTrue(meta.is_file())
            self.assertTrue(result["full_text_in_chat"])
            payload = json.loads(meta.read_text(encoding="utf-8"))
            self.assertEqual(payload["method"], "text")
            self.assertEqual(payload["source"], "x.mp3")

    def test_keeps_raw_when_improved(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = "texto bruto original"
            write_output.write_output(
                slug="demo",
                raw_text=raw,
                out_root=tmp,
                meta={"method": "whisper"},
                improved_text="texto melhorado",
                cleaned_text="texto limpo",
                summary_text="resumo curto",
            )
            folder = Path(tmp) / "demo"
            self.assertEqual(folder.joinpath("raw.txt").read_text(encoding="utf-8").strip(), raw)
            self.assertIn("melhorado", folder.joinpath("improved.txt").read_text(encoding="utf-8"))
            self.assertTrue(folder.joinpath("cleaned.txt").is_file())
            self.assertTrue(folder.joinpath("summary.txt").is_file())

    def test_segments_write_srt(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_output.write_output(
                slug="cues",
                raw_text="Olá",
                out_root=tmp,
                meta=None,
                segments=[{"start": 0, "end": 1.5, "text": "Olá"}],
            )
            self.assertIn("raw_srt", result["files"])
            body = Path(result["files"]["raw_srt"]).read_text(encoding="utf-8")
            self.assertIn("00:00:00,000 --> 00:00:01,500", body)

    def test_preview_truncates(self):
        words = " ".join(f"w{i}" for i in range(200))
        with tempfile.TemporaryDirectory() as tmp:
            result = write_output.write_output(
                slug="long",
                raw_text=words,
                out_root=tmp,
                meta=None,
                preview_words=100,
            )
            self.assertFalse(result["full_text_in_chat"])
            self.assertEqual(result["word_count"], 200)
            self.assertIsNone(result["raw_text"])


class ExtractAudioTests(unittest.TestCase):
    @unittest.skipIf(common.which("ffmpeg") is None, "ffmpeg ausente")
    def test_extract_silent_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "silence.wav"
            mp3 = Path(tmp) / "out.mp3"
            common.run_cmd(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=16000:cl=mono",
                    "-t",
                    "1",
                    str(wav),
                ]
            )
            classified = detect_source.classify(str(wav))
            self.assertEqual(classified["kind"], "audio")
            result = extract_audio.extract(str(wav), str(mp3))
            self.assertTrue(Path(result["audio_path"]).is_file())
            self.assertGreater(result["size_bytes"], 0)
            self.assertGreater(result["duration_seconds"] or 0, 0.5)


class TranscribePlanTests(unittest.TestCase):
    def test_small_file_is_single_chunk(self):
        plan = transcribe_audio.plan_chunks(1024, 12.0)
        self.assertEqual(plan, [(0.0, 12.0)])

    def test_large_file_splits(self):
        plan = transcribe_audio.plan_chunks(50 * 1024 * 1024, 120.0)
        self.assertGreaterEqual(len(plan), 2)
        self.assertEqual(plan[0][0], 0.0)


class KeyGuardTests(unittest.TestCase):
    def test_missing_key_fails_explicitly(self):
        previous = os.environ.pop("OPENAI_API_KEY", None)
        try:
            with self.assertRaises(SystemExit):
                common.require_openai_key()
        finally:
            if previous is not None:
                os.environ["OPENAI_API_KEY"] = previous


class CommonTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(common.slugify("Entrevista João 2024"), "entrevista-joao-2024")

    def test_plan_language_aliases(self):
        self.assertEqual(common.language_code("português"), "pt")
        self.assertEqual(common.language_code("English"), "en")

    def test_srt_roundtrip_timestamp(self):
        self.assertEqual(common.format_timestamp(65.5), "00:01:05,500")
        self.assertEqual(common.format_timestamp(65.5, vtt=True), "00:01:05.500")

    def test_repo_layout(self):
        self.assertTrue((ROOT / "SKILL.md").is_file())
        self.assertTrue((TOOLS / "cleanup_text.py").is_file())
        self.assertTrue((ROOT / "references" / "refine-prompt.md").is_file())

    def test_chat_model_is_luna(self):
        self.assertEqual(common.CHAT_MODEL, "gpt-5.6-luna")
        self.assertEqual(common.REASONING_EFFORT, "none")

    def test_chat_chunks_stay_under_long_context_surcharge(self):
        self.assertGreaterEqual(common.CHAT_CHUNK_CHARS, 100_000)
        self.assertLess(common.CHAT_CHUNK_CHARS, 1_000_000)


if __name__ == "__main__":
    unittest.main()
