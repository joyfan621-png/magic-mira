import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import AppConfig


class AppConfigTests(unittest.TestCase):
    def test_aiping_default_vision_model_uses_doubao_seed_2_pro(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {
                    "MIRROR_AGENT_PROVIDER": "aiping",
                },
                clear=True,
            ):
                config = AppConfig.from_env(Path(temp_dir))

        self.assertEqual("aiping", config.provider)
        self.assertEqual("Doubao-Seed-2.0-pro", config.vision_model)
