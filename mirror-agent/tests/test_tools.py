import tempfile
import unittest
from pathlib import Path

from config import AppConfig
from memory import MemoryStore
from reminders import ReminderScheduler
from tools import MirrorTools
from tools import search_knowledge


class KnowledgeSearchTests(unittest.TestCase):
    def test_search_knowledge_returns_matching_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            knowledge_path = Path(temp_dir) / "skincare.md"
            knowledge_path.write_text(
                "# 护肤知识\n\n## 眼霜误区\n眼霜不是越多越好，米粒大小就够。\n\n## 晨间步骤\n先洁面再防晒。\n",
                encoding="utf-8",
            )

            result = search_knowledge(knowledge_path, "眼霜")

            self.assertIn("眼霜误区", result)
            self.assertIn("米粒大小", result)

    def test_search_knowledge_handles_missing_query(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            knowledge_path = Path(temp_dir) / "skincare.md"
            knowledge_path.write_text("# 护肤知识\n\n## 清洁\n温和清洁。\n", encoding="utf-8")

            result = search_knowledge(knowledge_path, "刷酸")

            self.assertIn("没有找到", result)

    def test_search_knowledge_scans_all_markdown_files_in_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            knowledge_dir = Path(temp_dir) / "knowledge"
            knowledge_dir.mkdir()
            (knowledge_dir / "skincare.md").write_text("# 护肤知识\n\n## 清洁\n温和清洁。\n", encoding="utf-8")
            (knowledge_dir / "face-mapping.md").write_text(
                "# 小镜的看脸笔记\n\n## 脸上的天气预报\n### 下巴\n下巴长痘常见和生理周期波动有关。\n",
                encoding="utf-8",
            )

            result = search_knowledge(knowledge_dir, "下巴")

            self.assertIn("下巴", result)
            self.assertIn("生理周期", result)

    def test_skincare_knowledge_tool_uses_whole_knowledge_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n\n## 防晒\n白天要防晒。\n", encoding="utf-8")
            (project_root / "knowledge" / "face-mapping.md").write_text(
                "# 小镜的看脸笔记\n\n## 脸上的天气预报\n### 额头\n额头冒痘常见和压力大、没睡好有关。\n",
                encoding="utf-8",
            )

            tools = MirrorTools(
                config=AppConfig(project_root=project_root, api_key=""),
                memory_store=MemoryStore(project_root),
                client=None,
            )

            result = tools.skincare_knowledge("额头")

            self.assertIn("额头", result)
            self.assertIn("压力大", result)

    def test_memory_write_captures_mirror_name_preferences_and_sensitive_skin_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            tools = MirrorTools(
                config=AppConfig(project_root=project_root, api_key=""),
                memory_store=MemoryStore(project_root),
                client=None,
            )

            tools.memory_write(
                conversation=(
                    "user: 你就叫小镜吧\n"
                    "assistant: 好呀，我记住了。\n"
                    "user: 以后你温柔一点，再每天提醒我涂防晒。"
                    "我皮肤很敏感，换季就烂脸。\n"
                ),
                diary_date="2026-04-05",
            )

            profile = (project_root / "memory" / "profile.md").read_text(encoding="utf-8")

            self.assertIn("镜中名字：小镜", profile)
            self.assertIn("互动偏好：希望你说话温柔一点", profile)
            self.assertIn("陪伴期待：希望你每天提醒她涂防晒", profile)
            self.assertIn("皮肤信息：皮肤敏感，换季容易不稳定", profile)

    def test_tool_schemas_include_schedule_reminder_and_execute_returns_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "memory" / "diary").mkdir(parents=True)
            (project_root / "knowledge").mkdir(parents=True)
            (project_root / "knowledge" / "skincare.md").write_text("# 护肤知识\n", encoding="utf-8")

            scheduler = ReminderScheduler()
            tools = MirrorTools(
                config=AppConfig(project_root=project_root, api_key=""),
                memory_store=MemoryStore(project_root),
                client=None,
                reminder_scheduler=scheduler,
            )

            names = [schema["function"]["name"] for schema in tools.tool_schemas()]
            self.assertIn("schedule_reminder", names)

            result = tools.execute_tool_call(
                "schedule_reminder",
                {"minutes": 15, "message": "面膜时间到了，记得摘掉哦。"},
            )

            self.assertIn("面膜时间到了", result)
