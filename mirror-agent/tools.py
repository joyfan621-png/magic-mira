from __future__ import annotations

import base64
import json
import mimetypes
import re
from datetime import date
from pathlib import Path
from typing import Any

from config import AppConfig
from memory import MemoryStore, format_conversation
from reminders import ReminderScheduler


def search_knowledge(knowledge_path: Path, query: str, limit: int = 3) -> str:
    knowledge_path = Path(knowledge_path)
    if not knowledge_path.exists():
        return "护肤知识库还没准备好。"

    documents = _load_knowledge_documents(knowledge_path)
    if not documents:
        return "护肤知识库还没准备好。"

    query = query.strip()
    if not query:
        return "\n\n".join(documents)[:800]

    sections: list[str] = []
    for document in documents:
        sections.extend(_split_markdown_sections(document))
    terms = [term for term in re.split(r"[\s,/，。；;]+", query) if term]
    scored_sections: list[tuple[int, str]] = []
    for section in sections:
        score = 0
        lowered = section.lower()
        for term in terms:
            score += lowered.count(term.lower()) * max(len(term), 1)
        if query.lower() in lowered:
            score += len(query) * 2
        if score > 0:
            scored_sections.append((score, section.strip()))

    if not scored_sections:
        return f"没有找到和“{query}”直接相关的知识条目，换个关键词试试。"

    top_sections = [section for _, section in sorted(scored_sections, key=lambda item: item[0], reverse=True)[:limit]]
    return "\n\n".join(top_sections)


class MirrorTools:
    def __init__(
        self,
        config: AppConfig,
        memory_store: MemoryStore,
        client: Any = None,
        reminder_scheduler: ReminderScheduler | None = None,
    ) -> None:
        self.config = config
        self.memory_store = memory_store
        self.client = client
        self.reminder_scheduler = reminder_scheduler or ReminderScheduler()

    def tool_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "skin_analyze",
                    "description": "分析本地图片里的皮肤表面现象，只做护肤观察，不做疾病诊断。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "image_path": {"type": "string", "description": "本地图片路径"},
                            "note": {"type": "string", "description": "用户补充描述"},
                        },
                        "required": ["image_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_read",
                    "description": "读取本地 Markdown 记忆，包括用户画像、洞察和最近日记。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "enum": ["profile", "insights", "recent_diary", "context"],
                                "description": "要读取的记忆部分",
                            },
                            "limit": {"type": "integer", "description": "最近日记读取数量", "minimum": 1, "maximum": 30},
                        },
                        "required": ["target"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_write",
                    "description": "将对话摘要写入当日日记，并在合适时更新用户画像与长期洞察。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "conversation": {"type": "string", "description": "要写入总结的完整对话文本"},
                            "diary_date": {"type": "string", "description": "日记日期，格式 YYYY-MM-DD"},
                        },
                        "required": ["conversation"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "skincare_knowledge",
                    "description": "检索本地护肤知识库，回答步骤、误区和成分搭配问题。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "用户想查的护肤问题"},
                            "limit": {"type": "integer", "description": "返回段落数", "minimum": 1, "maximum": 5},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "trend_analyze",
                    "description": "分析最近一段时间的日记，找出压力、熬夜和皮肤状态的模式。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "days": {"type": "integer", "description": "分析最近多少天", "minimum": 1, "maximum": 60},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "schedule_reminder",
                    "description": "为用户创建一个稍后触发的本地提醒，适合面膜、补涂防晒等需要定时提醒的场景。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "minutes": {"type": "integer", "description": "多少分钟后提醒", "minimum": 0, "maximum": 720},
                            "message": {"type": "string", "description": "提醒内容"},
                            "source_text": {"type": "string", "description": "触发提醒的原始用户话术"},
                        },
                        "required": ["minutes", "message"],
                    },
                },
            },
        ]

    def execute_tool_call(self, name: str, arguments: str | dict[str, Any] | None) -> str:
        parsed_args = self._coerce_arguments(arguments)
        handler = {
            "skin_analyze": self.skin_analyze,
            "memory_read": self.memory_read,
            "memory_write": self.memory_write,
            "skincare_knowledge": self.skincare_knowledge,
            "trend_analyze": self.trend_analyze,
            "schedule_reminder": self.schedule_reminder,
        }.get(name)
        if handler is None:
            return json.dumps({"status": "error", "message": f"未知工具：{name}"}, ensure_ascii=False)

        result = handler(**parsed_args)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)

    def skin_analyze(self, image_path: str, note: str = "") -> str:
        image_file = Path(image_path).expanduser()
        if not image_file.exists():
            return f"图片没找到哦，我这边读不到 `{image_file}`。你确认一下路径再丢给我。"
        if not self.client or not self.config.api_key_configured:
            return "分析入口已经接好了，但第三方 API Key 还没配好，先把配置补上，我们再继续。"

        mime_type, _ = mimetypes.guess_type(str(image_file))
        if not mime_type:
            mime_type = "image/jpeg"
        encoded = base64.b64encode(image_file.read_bytes()).decode("utf-8")
        prompt = (
            "请做谨慎的皮肤表面观察：只描述可见现象、可能的护肤提醒和需就医的风险信号。"
            "不要诊断疾病，不要推销产品，不要制造焦虑，不要展示思考过程。"
            "回复时直接像在和本人说话，不要提图片、照片、画面或自拍。"
        )
        if note.strip():
            prompt += f"\n用户补充：{note.strip()}"

        if self.config.provider == "ollama":
            response = self.client.chat.completions.create(
                model=self.config.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [encoded],
                    }
                ],
                extra_body={"temperature": 0.3},
            )
        else:
            response = self.client.chat.completions.create(
                model=self.config.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
                        ],
                    },
                ],
                extra_body={"temperature": 0.3},
            )

        result = extract_response_text(response) or "我这次没有拿到有效结果。"
        if "没有上传图片" in result or "没有包含图片" in result:
            return "这个第三方通道这次没真正接到内容，我先拦住它了。你可以先文字描述，我也建议后面换成明确支持视觉输入的通道。"
        return result

    def analyze_selfie(self, image_path: str, note: str = "") -> dict[str, Any]:
        image_file = Path(image_path).expanduser()
        if not image_file.exists():
            return {
                "is_selfie": False,
                "complexion_score": None,
                "skin_issues": [],
                "emotion": "",
                "comparison": "",
                "reply": f"我这边没接住刚刚那次内容哦，`{image_file}` 不在。你重新丢一下，我立刻接着聊。",
            }
        if not self.client or not self.config.api_key_configured:
            return {
                "is_selfie": False,
                "complexion_score": None,
                "skin_issues": [],
                "emotion": "",
                "comparison": "",
                "reply": "分析入口在这儿，但模型现在没连上。你把本地 Ollama 服务起好，我们就能继续聊。",
            }

        mime_type, _ = mimetypes.guess_type(str(image_file))
        if not mime_type:
            mime_type = "image/jpeg"

        encoded = base64.b64encode(image_file.read_bytes()).decode("utf-8")
        recent_diaries = self.memory_store.read_recent_diaries(limit=3)
        history_context = "\n\n".join(recent_diaries) if recent_diaries else "最近还没有 diary 记录。"
        face_mapping_context = ""
        if _wants_tcm_face_mapping(note):
            knowledge_query = "中医 面诊 食养 脸部区域 额头 脸颊 鼻头 下巴 嘴周"
            if note.strip():
                knowledge_query = f"{knowledge_query} {note.strip()}"
            knowledge = search_knowledge(self.config.knowledge_dir, knowledge_query, limit=4)
            if knowledge and "没有找到" not in knowledge:
                face_mapping_context = knowledge
        prompt = f"""
请分析这张自拍照中人物的：
1. 整体气色（用1-10分评估）
2. 皮肤状态（痘痘、黑眼圈、干燥、出油等具体问题）
3. 看起来的情绪状态
4. 与历史记录相比有没有变化，如果看不准就直说

历史记录参考：
{history_context}

额外要求：
- 先判断这是不是清晰的人脸自拍；如果不是，请返回 is_selfie=false，不要编造护肤结论。
- 绝不诊断疾病；如果看到明显异常，只能提醒“建议去看皮肤科”。
- reply 要用住在镜子里的护肤闺蜜口吻写成 2-3 句话，口语一点；如果历史里已经有镜中名字，就用那个名字自称，否则直接用“我”。
- reply 里不要说“这张图”“照片里”“自拍里”“从照片看”，直接像在和本人说话。
- 如果用户明确想从中医、食养或面诊视角来聊，可以把可见区域和作息、情绪、饮食习惯自然联系起来，但只当生活化提醒，不要像上课，更不要当成医学诊断。
- 只输出 JSON，不要代码块，不要额外解释，也不要展示思考过程。

JSON 格式：
{{
  "is_selfie": true,
  "complexion_score": 7,
  "skin_issues": ["黑眼圈", "轻微干燥"],
  "emotion": "有点疲惫",
  "comparison": "比昨天好一点",
  "reply": "今天气色还不错嘛！7分。不过眼下有点黑眼圈，昨晚几点睡的？比昨天好一些，继续保持～"
}}
""".strip()
        if face_mapping_context:
            prompt += f"\n\n中医/面诊参考笔记：\n{face_mapping_context}"
        if note.strip():
            prompt += f"\n\n用户补充：{note.strip()}"

        if self.config.provider == "ollama":
            response = self.client.chat.completions.create(
                model=self.config.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [encoded],
                    }
                ],
                extra_body={"temperature": 0.2},
            )
        else:
            response = self.client.chat.completions.create(
                model=self.config.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
                        ],
                    }
                ],
                extra_body={"temperature": 0.2},
            )

        raw_text = extract_response_text(response)
        return _parse_selfie_payload(raw_text)

    def record_selfie_analysis(
        self,
        analysis: dict[str, Any],
        image_path: str,
        note: str = "",
        diary_date: str | None = None,
    ) -> Path:
        _ = image_path
        diary_date = diary_date or date.today().isoformat()
        return self.memory_store.append_selfie_analysis(
            diary_date=diary_date,
            complexion_score=analysis.get("complexion_score"),
            skin_issues=_coerce_string_list(analysis.get("skin_issues")),
            emotion=str(analysis.get("emotion", "")).strip(),
            comparison=str(analysis.get("comparison", "")).strip(),
            reply=str(analysis.get("reply", "")).strip() or "今天先记下这一张，我们后面慢慢比。",
            note=note,
        )

    def memory_read(self, target: str, limit: int = 3) -> str:
        target = target.strip()
        if target == "profile":
            return self.memory_store.read_profile()
        if target == "insights":
            return self.memory_store.read_insights()
        if target == "recent_diary":
            entries = self.memory_store.read_recent_diaries(limit=limit)
            return "\n\n".join(entries) if entries else "最近还没有 diary。"
        return self.memory_store.build_memory_context(limit=limit)

    def memory_write(self, conversation: str | list[dict[str, str]], diary_date: str | None = None) -> str:
        diary_date = diary_date or date.today().isoformat()
        conversation_text = conversation if isinstance(conversation, str) else format_conversation(conversation)

        diary_markdown, profile_update, insight_update = self._summarize_conversation(conversation_text, diary_date)
        diary_markdown = self.memory_store.merge_generated_diary(
            self.memory_store.read_diary(diary_date),
            diary_markdown,
        )
        diary_path = self.memory_store.write_diary(diary_date, diary_markdown)
        if profile_update:
            self.memory_store.append_profile_update(profile_update, diary_date)
        if insight_update and self.memory_store.count_diaries() >= 7:
            self.memory_store.append_insight(insight_update, diary_date)

        return json.dumps(
            {
                "status": "ok",
                "diary_path": str(diary_path),
                "profile_updated": bool(profile_update),
                "insight_updated": bool(insight_update) and self.memory_store.count_diaries() >= 7,
            },
            ensure_ascii=False,
        )

    def skincare_knowledge(self, query: str, limit: int = 3) -> str:
        return search_knowledge(self.config.knowledge_dir, query, limit=limit)

    def trend_analyze(self, days: int = 7) -> str:
        entries = self.memory_store.read_all_diary_entries()
        if not entries:
            return "还没有日记数据，暂时没法看趋势。"

        recent_entries = entries[-days:]
        if len(recent_entries) < 7:
            return f"现在只有 {len(recent_entries)} 天记录，先继续攒到 7 天以上，我再更稳地帮你看模式。"

        keywords = ["压力", "熬夜", "爆痘", "泛红", "出油", "干", "闭口", "刺痛", "敏感", "姨妈", "焦虑"]
        joined = "\n".join(content for _, content in recent_entries)
        counts = {keyword: joined.count(keyword) for keyword in keywords if joined.count(keyword) > 0}

        lines = [f"最近分析范围：{len(recent_entries)} 天。"]
        if not counts:
            lines.append("目前关键词还不够集中，继续记录会更有用。")
            return "\n".join(lines)

        for keyword, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:5]:
            lines.append(f"- “{keyword}”出现了 {count} 次。")

        if counts.get("压力") and counts.get("泛红"):
            lines.append("初步看，压力和泛红有同框趋势，可以继续观察是不是连续出现。")
        if counts.get("熬夜") and counts.get("爆痘"):
            lines.append("熬夜和爆痘也有点绑定的意思，最近作息值得盯一下。")

        return "\n".join(lines)

    def schedule_reminder(self, minutes: int, message: str, source_text: str = "") -> dict[str, Any]:
        reminder = self.reminder_scheduler.schedule_in_minutes(
            minutes=minutes,
            message=message,
            source_text=source_text,
        )
        return {
            "status": "ok",
            "message": reminder.message,
            "due_at": reminder.due_at,
            "due_at_ms": reminder.due_at_ms,
            "id": reminder.id,
        }

    def _summarize_conversation(self, conversation_text: str, diary_date: str) -> tuple[str, str, str]:
        if self.client and self.config.api_key_configured:
            try:
                return self._summarize_with_model(conversation_text, diary_date)
            except Exception:
                pass
        return self._summarize_locally(conversation_text, diary_date)

    def _summarize_with_model(self, conversation_text: str, diary_date: str) -> tuple[str, str, str]:
        prompt = f"""
你负责把护肤闺蜜对话总结成记忆，只输出 JSON，不要代码块。

日期：{diary_date}

请返回：
{{
  "diary_markdown": "完整 Markdown",
  "profile_update": "如果发现新的稳定特征就写，否则空字符串",
  "insight_update": "如果已有 7 天以上模式可总结就写，否则空字符串"
}}

对话如下：
{conversation_text}
""".strip()

        response = self.client.chat.completions.create(
            model=self.config.chat_model,
            messages=[
                {"role": "system", "content": "你是记忆总结模块，输出必须是 JSON。"},
                {"role": "user", "content": prompt},
            ],
            extra_body={"temperature": 0.2},
        )
        raw_text = extract_response_text(response)
        cleaned = _strip_code_fences(raw_text)
        payload = json.loads(cleaned)
        return (
            payload.get("diary_markdown", "").strip() or self._summarize_locally(conversation_text, diary_date)[0],
            payload.get("profile_update", "").strip(),
            payload.get("insight_update", "").strip(),
        )

    def _summarize_locally(self, conversation_text: str, diary_date: str) -> tuple[str, str, str]:
        mood = _pick_first_keyword(conversation_text, ["焦虑", "累", "烦", "开心", "难过", "压力大", "崩溃"], fallback="普通")
        symptoms = _collect_keywords(conversation_text, ["爆痘", "泛红", "刺痛", "脱皮", "出油", "闭口", "干", "敏感"])
        actions = _collect_keywords(conversation_text, ["刷酸", "敷面膜", "防晒", "卸妆", "熬夜", "早睡", "眼霜", "精华", "A醇", "VC"])
        triggers = _collect_keywords(conversation_text, ["压力", "熬夜", "姨妈", "换季", "加班", "太阳", "饮食", "焦虑"])

        diary_markdown = "\n".join(
            [
                f"# {diary_date}",
                "",
                "## 今日情绪",
                f"- {mood}",
                "",
                "## 今日皮肤现象",
                f"- {', '.join(symptoms) if symptoms else '暂时没有提到明显现象'}",
                "",
                "## 今日护肤动作",
                f"- {', '.join(actions) if actions else '暂时没有提到具体步骤'}",
                "",
                "## 触发因素",
                f"- {', '.join(triggers) if triggers else '暂时没有提到明显触发因素'}",
                "",
                "## 镜中备注",
                "- 先继续观察，异常持续或明显加重时建议看皮肤科。",
            ]
        )

        profile_updates: list[str] = []

        mirror_name = _extract_mirror_name(conversation_text)
        if mirror_name:
            profile_updates.append(f"- 镜中名字：{mirror_name}")

        if "温柔一点" in conversation_text:
            profile_updates.append("- 互动偏好：希望你说话温柔一点。")
        if "毒舌一点" in conversation_text:
            profile_updates.append("- 互动偏好：希望你在不伤人的前提下毒舌一点。")
        if "多夸夸我" in conversation_text or "多夸夸" in conversation_text:
            profile_updates.append("- 互动偏好：希望你多夸夸她。")

        if "提醒我涂防晒" in conversation_text or "提醒我防晒" in conversation_text:
            profile_updates.append("- 陪伴期待：希望你每天提醒她涂防晒。")
        if "监控痘痘的变化" in conversation_text or "观察痘痘的变化" in conversation_text:
            profile_updates.append("- 陪伴期待：希望你持续对比痘痘变化。")
        if "聊聊天" in conversation_text or "陪我聊天" in conversation_text:
            profile_updates.append("- 陪伴期待：更看重陪伴聊天，不想每次都被分析。")

        if "皮肤很敏感" in conversation_text or "敏感肌" in conversation_text:
            if "换季就烂脸" in conversation_text:
                profile_updates.append("- 皮肤信息：皮肤敏感，换季容易不稳定。")
            else:
                profile_updates.append("- 皮肤信息：皮肤偏敏感。")
        elif "换季就烂脸" in conversation_text:
            profile_updates.append("- 皮肤信息：换季时皮肤容易不稳定。")

        if "油皮" in conversation_text or "干皮" in conversation_text or "混油" in conversation_text or "敏感肌" in conversation_text:
            skin_type = _pick_first_keyword(conversation_text, ["混油", "油皮", "干皮", "敏感肌"])
            if skin_type:
                profile_updates.append(f"- 稳定特征补充：用户提到自己偏 {skin_type}。")

        profile_update = "\n".join(dict.fromkeys(profile_updates))

        insight_update = ""
        if "熬夜" in conversation_text and ("爆痘" in conversation_text or "出油" in conversation_text):
            insight_update = "- 近期对话里多次出现熬夜后爆痘或出油，作息和皮肤波动可能相关。"

        return diary_markdown, profile_update, insight_update

    def _coerce_arguments(self, arguments: str | dict[str, Any] | None) -> dict[str, Any]:
        if arguments is None:
            return {}
        if isinstance(arguments, dict):
            return arguments
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            return {}


def extract_response_text(response: Any) -> str:
    choices = _get_value(response, "choices", [])
    if not choices:
        return ""
    message = _get_value(choices[0], "message", {})
    content = _get_value(message, "content", "")
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    chunks.append(item.get("text", ""))
                else:
                    chunks.append(str(item))
            else:
                chunks.append(str(item))
        return "\n".join(chunk for chunk in chunks if chunk).strip()
    return str(content).strip()


def _split_markdown_sections(text: str) -> list[str]:
    pieces = re.split(r"(?=^##+\s+)", text, flags=re.MULTILINE)
    return [piece.strip() for piece in pieces if piece.strip()]


def _wants_tcm_face_mapping(note: str) -> bool:
    normalized = note.strip()
    if not normalized:
        return False
    keywords = ("中医", "食养", "面诊", "脸上哪个位置", "对应什么", "身体在说什么")
    return any(keyword in normalized for keyword in keywords)


def _load_knowledge_documents(knowledge_path: Path) -> list[str]:
    if knowledge_path.is_file():
        return [knowledge_path.read_text(encoding="utf-8")]

    if not knowledge_path.is_dir():
        return []

    documents: list[str] = []
    for path in sorted(knowledge_path.glob("*.md")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if text:
            documents.append(text)
    return documents


def _collect_keywords(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]


def _pick_first_keyword(text: str, keywords: list[str], fallback: str = "") -> str:
    for keyword in keywords:
        if keyword in text:
            return keyword
    return fallback


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", stripped)
        stripped = re.sub(r"\n```$", "", stripped)
    return stripped.strip()


def _extract_mirror_name(text: str) -> str:
    patterns = [
        r"你就叫([^\s，。！？!?,\"“”']{1,12})吧",
        r"你叫([^\s，。！？!?,\"“”']{1,12})吧",
        r"以后叫你([^\s，。！？!?,\"“”']{1,12})",
        r"给你起名叫([^\s，。！？!?,\"“”']{1,12})",
        r"你可以叫([^\s，。！？!?,\"“”']{1,12})",
        r"叫你([^\s，。！？!?,\"“”']{1,12})好了",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        candidate = match.group(1).strip().strip("“”\"'")
        candidate = re.sub(r"[~～,，。！？!?\s]+$", "", candidate)
        if candidate:
            return candidate
    return ""


def _get_value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _parse_selfie_payload(raw_text: str) -> dict[str, Any]:
    cleaned = _strip_code_fences(raw_text)
    payload: dict[str, Any]
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return {
                "is_selfie": False,
                "complexion_score": None,
                "skin_issues": [],
                "emotion": "",
                "comparison": "",
                "reply": cleaned.strip() or "我刚才看图的时候走神了，你再发我一次，我认真重看。",
            }
        payload = json.loads(match.group(0))

    complexion_score = _coerce_score(payload.get("complexion_score"))
    skin_issues = _coerce_string_list(payload.get("skin_issues"))
    emotion = str(payload.get("emotion", "")).strip()
    comparison = str(payload.get("comparison", "")).strip()
    reply = str(payload.get("reply", "")).strip()
    is_selfie = bool(payload.get("is_selfie", True))

    if not reply:
        if not is_selfie:
            reply = "这张不像正脸自拍欸，我先不乱分析。你换一张光线稳一点、能看清脸的照片给我，我再认真看。"
        else:
            score_text = f"{complexion_score}分" if complexion_score is not None else "先不硬打分"
            issue_text = "、".join(skin_issues) if skin_issues else "暂时没看到特别明显的问题"
            comparison_text = comparison or "历史上还看不太准"
            reply = f"今天气色大概 {score_text}。我先看到的是 {issue_text}，{comparison_text}。"

    return {
        "is_selfie": is_selfie,
        "complexion_score": complexion_score,
        "skin_issues": skin_issues,
        "emotion": emotion,
        "comparison": comparison,
        "reply": reply,
    }


def _coerce_score(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        score = int(round(value))
        return min(max(score, 1), 10)
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            score = int(match.group(0))
            return min(max(score, 1), 10)
    return None


def _coerce_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[\n,，、；;]+", value) if item.strip()]
    return []
