import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAYGROUND_DIR = PROJECT_ROOT / "playgrounds" / "mirror-animation-playground"


class MirrorAnimationPlaygroundTests(unittest.TestCase):
    def test_playground_files_exist(self) -> None:
        self.assertTrue((PLAYGROUND_DIR / "index.html").exists())
        self.assertTrue((PLAYGROUND_DIR / "style.css").exists())
        self.assertTrue((PLAYGROUND_DIR / "app.js").exists())

    def test_html_contains_gallery_and_selection_summary(self) -> None:
        html = (PLAYGROUND_DIR / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="gallery"', html)
        self.assertIn('id="selection-summary"', html)

    def test_script_defines_fifteen_animations_and_selection_state(self) -> None:
        script = (PLAYGROUND_DIR / "app.js").read_text(encoding="utf-8")

        self.assertEqual(15, len(re.findall(r'id:\s*"', script)))
        self.assertIn("selectedAnimationIds", script)
        self.assertIn("renderSelectionSummary()", script)


if __name__ == "__main__":
    unittest.main()
