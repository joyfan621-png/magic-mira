from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable


PROFILE_TEMPLATE = """# 用户画像

- 正在慢慢认识你，先从肤质、作息和常见困扰开始记。
"""


INSIGHTS_TEMPLATE = """# AI洞察

- 先继续观察，累计 7 天以上再总结稳定模式。
"""


@dataclass
class MemoryStore:
    project_root: Path

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root).resolve()
        self.memory_dir = self.project_root / "memory"
        self.diary_dir = self.memory_dir / "diary"
        self.profile_path = self.memory_dir / "profile.md"
        self.insights_path = self.memory_dir / "insights.md"

    def ensure_structure(self) -> None:
        self.diary_dir.mkdir(parents=True, exist_ok=True)
        if not self.profile_path.exists():
            self.profile_path.write_text(PROFILE_TEMPLATE, encoding="utf-8")
        if not self.insights_path.exists():
            self.insights_path.write_text(INSIGHTS_TEMPLATE, encoding="utf-8")

    def read_profile(self) -> str:
        self.ensure_structure()
        return self.profile_path.read_text(encoding="utf-8").strip()

    def read_mirror_name(self) -> str | None:
        profile = self.read_profile()
        matches = re.findall(r"镜中名字：([^\n]+)", profile)
        if not matches:
            return None
        candidate = matches[-1].strip().strip("“”\"'")
        return candidate or None

    def read_insights(self) -> str:
        self.ensure_structure()
        return self.insights_path.read_text(encoding="utf-8").strip()

    def read_recent_diaries(self, limit: int = 3) -> list[str]:
        return [content for _, content in self.read_recent_diary_entries(limit=limit)]

    def read_recent_diary_entries(self, limit: int = 3) -> list[tuple[str, str]]:
        self.ensure_structure()
        diary_paths = sorted(self.diary_dir.glob("*.md"), key=lambda item: item.stem, reverse=True)
        entries: list[tuple[str, str]] = []
        for path in diary_paths[: max(limit, 0)]:
            entries.append((path.stem, path.read_text(encoding="utf-8").strip()))
        return entries

    def read_all_diary_entries(self) -> list[tuple[str, str]]:
        self.ensure_structure()
        diary_paths = sorted(self.diary_dir.glob("*.md"), key=lambda item: item.stem)
        return [(path.stem, path.read_text(encoding="utf-8").strip()) for path in diary_paths]

    def read_diary(self, diary_date: str | date | datetime) -> str:
        self.ensure_structure()
        normalized = self._normalize_date(diary_date)
        diary_path = self.diary_dir / f"{normalized}.md"
        if not diary_path.exists():
            return ""
        return diary_path.read_text(encoding="utf-8").strip()

    def write_diary(self, diary_date: str | date | datetime, content: str) -> Path:
        self.ensure_structure()
        normalized = self._normalize_date(diary_date)
        diary_path = self.diary_dir / f"{normalized}.md"
        diary_path.write_text(content.strip() + "\n", encoding="utf-8")
        return diary_path

    def append_selfie_analysis(
        self,
        diary_date: str | date | datetime,
        complexion_score: int | None,
        skin_issues: list[str],
        emotion: str,
        comparison: str,
        reply: str,
        note: str = "",
    ) -> Path:
        self.ensure_structure()
        normalized = self._normalize_date(diary_date)
        diary_path = self.diary_dir / f"{normalized}.md"
        existing = self.read_diary(normalized)
        if existing:
            content = existing.rstrip()
        else:
            content = f"# {normalized}"

        stamp = datetime.now().strftime("%H:%M")
        issue_text = "、".join(item for item in skin_issues if item) or "暂时没抓到特别明显的问题"
        lines = [
            content,
            "",
            f"## 自拍分析 {stamp}",
            "",
            f"- 气色评分：{complexion_score}/10" if complexion_score is not None else "- 气色评分：这次先不硬打分",
            f"- 皮肤状态：{issue_text}",
            f"- 情绪状态：{emotion or '这次还看不太准'}",
            f"- 与历史对比：{comparison or '历史上还看不准，先继续攒几次。'}",
        ]
        if note.strip():
            lines.append(f"- 用户补充：{note.strip()}")
        lines.append(f"- {self.read_mirror_name() or '我'}：{reply.strip()}")
        lines.append("")
        diary_path.write_text("\n".join(lines), encoding="utf-8")
        return diary_path

    def count_diaries(self) -> int:
        self.ensure_structure()
        return len(list(self.diary_dir.glob("*.md")))

    def append_profile_update(self, update: str, diary_date: str | date | datetime) -> None:
        update = update.strip()
        if not update:
            return
        self.ensure_structure()
        existing = self.read_profile()
        stamped = self._append_timestamped_section(existing, self._normalize_date(diary_date), update)
        self.profile_path.write_text(stamped, encoding="utf-8")

    def append_insight(self, insight: str, diary_date: str | date | datetime) -> None:
        insight = insight.strip()
        if not insight:
            return
        self.ensure_structure()
        existing = self.read_insights()
        stamped = self._append_timestamped_section(existing, self._normalize_date(diary_date), insight)
        self.insights_path.write_text(stamped, encoding="utf-8")

    def build_memory_context(self, limit: int = 3) -> str:
        self.ensure_structure()
        parts = [
            "## 用户画像",
            self.read_profile(),
            "",
            "## AI洞察",
            self.read_insights(),
            "",
            "## 最近 3 天日记",
        ]
        recent_entries = self.read_recent_diary_entries(limit=limit)
        if not recent_entries:
            parts.append("- 还没有日记记录。")
        else:
            for diary_date, content in recent_entries:
                parts.append(f"### {diary_date}")
                parts.append(content)
                parts.append("")
        return "\n".join(parts).strip()

    def merge_generated_diary(self, existing_content: str, generated_content: str) -> str:
        existing = existing_content.strip()
        generated = generated_content.strip()
        if not existing:
            return generated

        preserved_sections = [
            section.strip()
            for section in re.split(r"(?=^##\s+)", existing, flags=re.MULTILINE)
            if section.strip().startswith("## 自拍分析")
        ]
        if not preserved_sections:
            return generated

        merged = generated
        for section in preserved_sections:
            if section not in merged:
                merged = f"{merged.rstrip()}\n\n{section}"
        return merged.strip()

    def _normalize_date(self, value: str | date | datetime) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value).strip()

    def _append_timestamped_section(self, existing: str, stamp: str, body: str) -> str:
        if body in existing:
            return existing.strip() + "\n"
        lines = [existing.rstrip(), "", f"## {stamp}", "", body.strip(), ""]
        return "\n".join(line for line in lines if line is not None)


def format_conversation(history: Iterable[dict[str, str]]) -> str:
    lines: list[str] = []
    for item in history:
        role = item.get("role", "unknown")
        content = item.get("content", "").strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    return "\n".join(lines)
