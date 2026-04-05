import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voice_output import VoiceOutput, sanitize_speech_text


class FakeCommunicate:
    def __init__(self, text: str, voice: str) -> None:
        self.text = text
        self.voice = voice

    async def save(self, output_path: str) -> None:
        Path(output_path).write_bytes(b"fake-mp3")


class VoiceOutputTests(unittest.TestCase):
    def test_sanitize_speech_text_removes_markdown_and_headings(self) -> None:
        raw = "## 今日观察\n**你今天状态不错**\n- 左脸颊这边有一点泛红\n- 先别担心，慢慢来"

        cleaned = sanitize_speech_text(raw)

        self.assertNotIn("##", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("- ", cleaned)
        self.assertIn("你今天状态不错", cleaned)
        self.assertIn("左脸颊这边有一点泛红", cleaned)

    def test_speak_generates_audio_and_invokes_player(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = VoiceOutput(
                voice="zh-CN-XiaoyiNeural",
                temp_dir=Path(temp_dir),
                communicate_factory=FakeCommunicate,
                player_command=["echo"],
            )

            with patch("subprocess.run") as run_mock:
                output.speak("你好呀")

            run_mock.assert_called_once()
            command = run_mock.call_args.args[0]
            self.assertEqual("echo", command[0])
            self.assertTrue(str(command[1]).endswith(".mp3"))

    def test_async_generate_file_uses_requested_voice(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = VoiceOutput(
                voice="zh-CN-XiaoyiNeural",
                temp_dir=Path(temp_dir),
                communicate_factory=FakeCommunicate,
                player_command=["echo"],
            )

            result = asyncio.run(output.generate_audio_file("晚安啦"))

            self.assertTrue(result.exists())
            self.assertEqual(b"fake-mp3", result.read_bytes())

    def test_generate_audio_file_passes_sanitized_text_to_tts(self) -> None:
        captured: list[str] = []

        class RecordingCommunicate(FakeCommunicate):
            def __init__(self, text: str, voice: str) -> None:
                super().__init__(text, voice)
                captured.append(text)

        with tempfile.TemporaryDirectory() as temp_dir:
            output = VoiceOutput(
                voice="zh-CN-XiaoyiNeural",
                temp_dir=Path(temp_dir),
                communicate_factory=RecordingCommunicate,
                player_command=["echo"],
            )

            asyncio.run(output.generate_audio_file("## 小结\n**你今天很好看**\n- 先别焦虑"))

            self.assertEqual(1, len(captured))
            self.assertNotIn("##", captured[0])
            self.assertNotIn("**", captured[0])
            self.assertNotIn("- ", captured[0])
            self.assertIn("你今天很好看", captured[0])
