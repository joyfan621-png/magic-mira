import tempfile
import unittest
from datetime import date
from pathlib import Path

from memory import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        self.store = MemoryStore(self.project_root)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_ensure_structure_creates_expected_files(self) -> None:
        self.store.ensure_structure()

        self.assertTrue((self.project_root / "memory" / "profile.md").exists())
        self.assertTrue((self.project_root / "memory" / "insights.md").exists())
        self.assertTrue((self.project_root / "memory" / "diary").exists())

    def test_recent_diaries_only_returns_latest_days(self) -> None:
        self.store.ensure_structure()
        for day in ("2026-04-01", "2026-04-02", "2026-04-03", "2026-04-04"):
            self.store.write_diary(day, f"# {day}\n\ncontent for {day}\n")

        recent = self.store.read_recent_diaries(limit=3)
        combined = "\n".join(recent)

        self.assertEqual(3, len(recent))
        self.assertIn("2026-04-04", combined)
        self.assertIn("2026-04-03", combined)
        self.assertIn("2026-04-02", combined)
        self.assertNotIn("2026-04-01", combined)

    def test_write_diary_persists_markdown(self) -> None:
        self.store.ensure_structure()

        diary_path = self.store.write_diary(date(2026, 4, 4), "# 今日记录\n\n脸颊有点干。\n")

        self.assertTrue(diary_path.exists())
        self.assertIn("脸颊有点干", diary_path.read_text(encoding="utf-8"))

    def test_append_selfie_analysis_adds_structured_section(self) -> None:
        self.store.ensure_structure()

        diary_path = self.store.append_selfie_analysis(
            "2026-04-04",
            complexion_score=7,
            skin_issues=["黑眼圈", "轻微干燥"],
            emotion="有点疲惫",
            comparison="比昨天好一点",
            reply="今天气色还不错嘛！7分。",
        )

        content = diary_path.read_text(encoding="utf-8")
        self.assertIn("## 自拍分析", content)
        self.assertIn("气色评分：7/10", content)
        self.assertIn("黑眼圈、轻微干燥", content)

    def test_merge_generated_diary_preserves_selfie_sections(self) -> None:
        existing = """# 2026-04-04

## 今日情绪
- 累

## 自拍分析 20:30
- 气色评分：7/10
- 皮肤状态：黑眼圈
"""
        generated = """# 2026-04-04

## 今日情绪
- 普通
"""

        merged = self.store.merge_generated_diary(existing, generated)

        self.assertIn("## 自拍分析 20:30", merged)
        self.assertIn("## 今日情绪", merged)
