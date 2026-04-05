import tempfile
import unittest
from pathlib import Path

from voice_input import extract_wake_text, save_wav_file


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
