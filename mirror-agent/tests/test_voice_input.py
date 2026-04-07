import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from voice_input import VoiceInput, extract_wake_text, save_wav_file, transcribe_audio_file


class VoiceInputHelpersTests(unittest.TestCase):
    def test_extract_wake_text_returns_prompt_after_wake_word(self) -> None:
        self.assertEqual("看看我", extract_wake_text("小镜 看看我"))
        self.assertEqual("今天脸有点干", extract_wake_text("诶小镜今天脸有点干"))

    def test_extract_wake_text_returns_raw_text_when_wake_word_disabled(self) -> None:
        self.assertEqual("今天脸有点干", extract_wake_text("今天脸有点干", wake_word=""))

    def test_extract_wake_text_returns_none_without_wake_word(self) -> None:
        self.assertIsNone(extract_wake_text("今天脸有点干"))

    def test_extract_wake_text_returns_empty_string_when_only_wake_word(self) -> None:
        self.assertEqual("", extract_wake_text("小镜"))

    def test_save_wav_file_writes_wave_container(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "sample.wav"

            path = save_wav_file(output_path, [b"\x00\x00" * 160], sample_rate=16000, channels=1, sample_width=2)

            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 44)

    def test_transcribe_audio_file_defaults_to_small_whisper_model(self) -> None:
        captured_model_names: list[str] = []

        class StubModel:
            def transcribe(self, audio_path: str, language: str = "") -> dict[str, str]:
                return {"text": audio_path}

        def loader(model_name: str) -> StubModel:
            captured_model_names.append(model_name)
            return StubModel()

        transcript = transcribe_audio_file("/tmp/sample.wav", whisper_loader=loader)

        self.assertEqual("/tmp/sample.wav", transcript)
        self.assertEqual(["small"], captured_model_names)

    def test_voice_input_defaults_to_small_whisper_model(self) -> None:
        voice_input = VoiceInput()

        self.assertEqual("small", voice_input.whisper_model_name)

    def test_whisper_model_can_be_overridden_via_environment(self) -> None:
        captured_model_names: list[str] = []

        class StubModel:
            def transcribe(self, audio_path: str, language: str = "") -> dict[str, str]:
                return {"text": audio_path}

        def loader(model_name: str) -> StubModel:
            captured_model_names.append(model_name)
            return StubModel()

        with patch.dict(os.environ, {"MIRROR_AGENT_WHISPER_MODEL": "medium"}, clear=False):
            voice_input = VoiceInput()
            transcript = transcribe_audio_file("/tmp/sample.wav", whisper_loader=loader)

        self.assertEqual("medium", voice_input.whisper_model_name)
        self.assertEqual("/tmp/sample.wav", transcript)
        self.assertEqual(["medium"], captured_model_names)
