from __future__ import annotations

import base64
import json
import mimetypes
import re
import shlex
from datetime import date
from pathlib import Path
from typing import Any, Iterator

from config import AppConfig
from memory import MemoryStore
from ollama_client import OllamaClient
from reminders import ReminderScheduler
from third_party_client import AiPingClient
from tools import MirrorTools
from voice_output import sanitize_speech_text


END_SESSION_KEYWORDS = ("拜拜", "晚安")
PHOTO_REQUEST_KEYWORDS = ("拍照", "看看我", "看看我的脸", "看看我脸", "看看我的皮肤")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MAX_REPLY_CHARS = 100
MAX_REPLY_SENTENCES = 5
SENTENCE_ENDINGS = "。！？!?"
DEFAULT_MASK_TIMER_MINUTES = 15
DEFAULT_MASK_REMINDER_MESSAGE = "面膜时间到了，记得摘掉并轻轻按摩一下哦。"
REMINDER_TRIGGER_KEYWORDS = ("提醒", "计时", "定时", "倒计时", "闹钟", "叫我", "到点", "记一下")
MASK_ACTIVITY_PATTERNS = (
    r"我.*(?:在|正|刚|刚刚|已经).*(?:敷|贴).{0,2}面膜",
    r"我.*(?:敷上|贴上|敷好了|贴好了).{0,2}面膜",
    r"(?:刚|刚刚|现在|已经)?(?:敷|贴)上了?.{0,2}面膜",
    r"(?:面膜).*(?:敷上|贴上|上脸)了",
)
AFFIRMATIVE_PATTERNS = (
    r"^(?:好|好呀|好的|好啊|要|要的|开始|开始吧|可以|行|嗯|嗯嗯|来吧|开吧|帮我计时|开始计时)+[啦呀啊吧哦]?$",
    r"(?:帮我|给我).*(?:计时|开始)",
)
DECLINE_PATTERNS = (
    r"^(?:不用|不用了|不要|先不用|先不要|先别|别了|不需要)[啦呀啊吧哦]?$",
    r"(?:先别|不用).*(?:计时|提醒)",
)
MASK_TIMER_OFFER_PATTERNS = (
    r"面膜.*(?:15\s*分钟|十五分钟).*(?:计时|提醒).*(?:要不要|好吗|行吗)",
    r"(?:要不要|要我|要不).*(?:15\s*分钟|十五分钟).*(?:计时|提醒)",
    r"面膜.*(?:要不要|要我|要不).*(?:计时|提醒)",
)
CHINESE_NUMBER_MAP = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
CHINESE_UNIT_MAP = {"十": 10, "百": 100}


def should_end_session(text: str) -> bool:
    normalized = text.strip()
    return any(keyword in normalized for keyword in END_SESSION_KEYWORDS)


def should_start_photo_flow(text: str) -> bool:
    normalized = text.strip()
    return any(keyword in normalized for keyword in PHOTO_REQUEST_KEYWORDS)


def coerce_image_path(text: str) -> str | None:
    candidate = text.strip()
    if not candidate:
        return None
    if (candidate.startswith('"') and candidate.endswith('"')) or (candidate.startswith("'") and candidate.endswith("'")):
        candidate = candidate[1:-1].strip()
    path = Path(candidate).expanduser()
    if not path.exists() or not path.is_file():
        return None
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        return None
    return str(path.resolve())


def parse_image_command(raw: str) -> tuple[str, str]:
    parts = shlex.split(raw)
    if len(parts) < 2:
        raise ValueError("图片命令格式是：/image <图片路径> <补充描述>")
    image_path = parts[1]
    note = " ".join(parts[2:]).strip()
    return image_path, note


def parse_reminder_request(text: str) -> dict[str, Any] | None:
    normalized = text.strip()
    minutes = _extract_minutes(normalized)
    if _is_mask_timer_request(normalized):
        return {
            "minutes": minutes or DEFAULT_MASK_TIMER_MINUTES,
            "message": DEFAULT_MASK_REMINDER_MESSAGE,
        }
    if not any(keyword in normalized for keyword in REMINDER_TRIGGER_KEYWORDS):
        return None
    if minutes is None:
        return None
    message = DEFAULT_MASK_REMINDER_MESSAGE if "面膜" in normalized else "提醒时间到了哦。"
    return {"minutes": minutes, "message": message}


def _extract_minutes(text: str) -> int | None:
    digit_match = re.search(r"(\d{1,3})\s*(?:分钟|min|mins|minute|minutes)", text, flags=re.IGNORECASE)
    if digit_match:
        return int(digit_match.group(1))

    chinese_match = re.search(r"([零一二两三四五六七八九十百]{1,6})\s*分钟", text)
    if not chinese_match:
        return None
    return _parse_chinese_number(chinese_match.group(1))


def _parse_chinese_number(token: str) -> int | None:
    total = 0
    current = 0
    digits_seen = False
    for char in token:
        if char in CHINESE_NUMBER_MAP:
            current = CHINESE_NUMBER_MAP[char]
            digits_seen = True
            continue
        unit = CHINESE_UNIT_MAP.get(char)
        if unit is None:
            return None
        if current == 0:
            current = 1
        total += current * unit
        current = 0
    if not digits_seen and total == 0:
        return None
    return total + current


def _is_mask_timer_request(text: str) -> bool:
    if "面膜" not in text:
        return False
    if any(keyword in text for keyword in REMINDER_TRIGGER_KEYWORDS):
        return True
    return any(re.search(pattern, text) for pattern in MASK_ACTIVITY_PATTERNS)


def _normalize_intent_text(text: str) -> str:
    return re.sub(r"[\s，,。！？!?~～:：；;、]+", "", text)


def _looks_like_affirmation(text: str) -> bool:
    normalized = _normalize_intent_text(text)
    return any(re.search(pattern, normalized) for pattern in AFFIRMATIVE_PATTERNS)


def _looks_like_decline(text: str) -> bool:
    normalized = _normalize_intent_text(text)
    return any(re.search(pattern, normalized) for pattern in DECLINE_PATTERNS)


def _looks_like_mask_timer_offer(text: str) -> bool:
    normalized = _normalize_intent_text(text)
    if "面膜" not in normalized:
        return False
    return any(re.search(pattern, normalized) for pattern in MASK_TIMER_OFFER_PATTERNS)


class MirrorAgent:
    def __init__(
        self,
        config: AppConfig | None = None,
        client: Any = None,
        reminder_scheduler: ReminderScheduler | None = None,
    ) -> None:
        self.config = config or AppConfig.from_env(Path(__file__).resolve().parent)
        self.memory_store = MemoryStore(self.config.project_root)
        self.memory_store.ensure_structure()
        self.soul_prompt = self._load_soul_prompt()
        self.client = client if client is not None else self._build_client()
        self.reminder_scheduler = reminder_scheduler or ReminderScheduler()
        self.tools = MirrorTools(
            self.config,
            self.memory_store,
            self.client,
            reminder_scheduler=self.reminder_scheduler,
        )
        self.history: list[dict[str, str]] = []
        self.awaiting_photo = False
        self.pending_timer_offer: dict[str, Any] | None = None
        self.last_scheduled_reminder: dict[str, str] | None = None

    def build_memory_context(self) -> str:
        return self.memory_store.build_memory_context(limit=3)

    def display_name(self) -> str:
        return self.memory_store.read_mirror_name() or "我"

    def build_system_prompt(self) -> str:
        return "\n\n".join(
            [
                self.soul_prompt.strip(),
                "## 当前 Memory 上下文",
                self.build_memory_context(),
                "## Tool 使用约束",
                "- 需要回忆历史时优先用 memory_read 或 trend_analyze。",
                "- 需要查知识库时用 skincare_knowledge。",
                "- 用户发图片路径时可以用 skin_analyze。",
                "- 当前回合如果附带了摄像头画面，可以结合画面回答，但只做皮肤表面观察，不诊断疾病。",
                "- 当前回合如果附带了画面，要像照镜子时直接看着本人说话，不要提图片、照片、自拍、上传、画面或镜头这些媒介词。",
                "- 用户说“这里”“这块”“这个痘”时，要尽量落到具体脸部区域；不够确定也先给最接近的范围，直接说你能确认到的现象和区域，不要向用户汇报自己看不清、没抓稳或需要重拍。",
                "- 如果当前回合附带了画面，而且你能明显看出用户正在敷面膜，先别展开常规分析，优先问她要不要开始15分钟计时；在用户确认前不要直接创建提醒。",
                "- 用户让你稍后提醒时，优先使用 schedule_reminder。",
                "- 日常聊天时记得适度夸夸用户，语气像住在镜子里的护肤闺蜜。",
                "- 每次回复控制在100字以内，最多5句，优先先说结论，不写小作文。",
                "- 不要输出 markdown、标题、星号、列表、代码块，直接像人与人聊天那样说话。",
                "- 对话结束后的 diary 写入由系统自动触发，你不用主动要求用户重复总结。",
            ]
        ).strip()

    def respond(
        self,
        user_text: str,
        image_paths: list[str] | None = None,
        camera_active: bool = False,
    ) -> str:
        self.last_scheduled_reminder = None
        image_path = coerce_image_path(user_text)
        if image_path:
            self.awaiting_photo = False
            return self.respond_to_image(image_path)

        pending_offer_reply = self._handle_pending_timer_offer(user_text)
        if pending_offer_reply is not None:
            return pending_offer_reply

        reminder_request = parse_reminder_request(user_text)
        if reminder_request:
            return self._schedule_local_reminder(user_text, reminder_request)

        if image_paths:
            return self._respond_with_multimodal_context(user_text, image_paths=image_paths)

        if should_start_photo_flow(user_text):
            if camera_active:
                reply = "镜头我已经打开在看啦，你先把脸稳一点、离近一点，再自然说一遍你想我看哪一块。"
                self.history.append({"role": "user", "content": user_text})
                self.history.append({"role": "assistant", "content": reply})
                return reply
            self.awaiting_photo = True
            reply = "好呀，你把脸靠近一点，别动太快，我认真看看你这轮状态。"
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": reply})
            return reply

        if not self.client:
            reply = self._offline_reply()
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": reply})
            return reply

        messages: list[dict[str, Any]] = [{"role": "system", "content": self.build_system_prompt()}]
        messages.extend(self.history[-10:])
        messages.append({"role": "user", "content": user_text})

        reply = self._limit_reply(self._chat_with_tools(messages))
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def _respond_with_multimodal_context(self, user_text: str, image_paths: list[str]) -> str:
        if not self.client:
            reply = self._offline_reply()
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": reply})
            return reply

        messages = self._build_messages(user_text, image_paths=image_paths)
        reply = self._prepare_visual_reply(self._chat_with_tools(messages, model=self.config.vision_model))
        self._capture_timer_offer(reply)
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def respond_to_image(self, image_path: str, note: str = "") -> str:
        self.last_scheduled_reminder = None
        analysis = self.tools.analyze_selfie(image_path=image_path, note=note)
        reply = self._prepare_visual_reply(
            str(analysis.get("reply", "")).strip() or "你先把脸靠近一点，我接着说你这轮状态。"
        )
        self.awaiting_photo = False
        self.tools.record_selfie_analysis(analysis=analysis, image_path=image_path, note=note)
        history_note = "我让你看看我这轮状态"
        if note.strip():
            history_note = f"{history_note}：{note.strip()}"
        self.history.append({"role": "user", "content": history_note})
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def stream_respond(
        self,
        user_text: str,
        image_paths: list[str] | None = None,
        camera_active: bool = False,
    ) -> Iterator[str]:
        self.last_scheduled_reminder = None
        image_path = coerce_image_path(user_text)
        if image_path:
            reply = self.respond_to_image(image_path)
            yield from self._chunk_text(reply)
            return

        pending_offer_reply = self._handle_pending_timer_offer(user_text)
        if pending_offer_reply is not None:
            yield from self._chunk_text(pending_offer_reply)
            return

        reminder_request = parse_reminder_request(user_text)
        if reminder_request:
            reply = self._schedule_local_reminder(user_text, reminder_request)
            yield from self._chunk_text(reply)
            return

        if image_paths:
            yield from self._stream_with_multimodal_context(user_text, image_paths=image_paths)
            return

        if should_start_photo_flow(user_text):
            if camera_active:
                reply = "镜头我已经打开在看啦，你先把脸稳一点、离近一点，再自然说一遍你想我看哪一块。"
                self.history.append({"role": "user", "content": user_text})
                self.history.append({"role": "assistant", "content": reply})
                yield from self._chunk_text(reply)
                return
            self.awaiting_photo = True
            reply = "好呀，你把脸靠近一点，别动太快，我认真看看你这轮状态。"
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": reply})
            yield from self._chunk_text(reply)
            return

        if not self.client:
            reply = self._offline_reply()
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": reply})
            yield from self._chunk_text(reply)
            return

        messages: list[dict[str, Any]] = [{"role": "system", "content": self.build_system_prompt()}]
        messages.extend(self.history[-10:])
        messages.append({"role": "user", "content": user_text})

        stream_method = getattr(getattr(self.client.chat, "completions", None), "stream", None)
        if callable(stream_method):
            parts: list[str] = []
            for chunk in stream_method(
                model=self.config.chat_model,
                messages=messages,
                extra_body={"temperature": 0.8},
            ):
                if not chunk:
                    continue
                parts.append(chunk)
                yield chunk
            reply = self._limit_reply("".join(parts).strip())
            if reply:
                self.history.append({"role": "user", "content": user_text})
                self.history.append({"role": "assistant", "content": reply})
                return

        reply = self._limit_reply(self._chat_with_tools(messages, model=self.config.vision_model))
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})
        yield from self._chunk_text(reply)

    def _stream_with_multimodal_context(self, user_text: str, image_paths: list[str]) -> Iterator[str]:
        if not self.client:
            reply = self._offline_reply()
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": reply})
            yield from self._chunk_text(reply)
            return

        messages = self._build_messages(user_text, image_paths=image_paths)
        stream_method = getattr(getattr(self.client.chat, "completions", None), "stream", None)
        if callable(stream_method):
            parts: list[str] = []
            for chunk in stream_method(
                model=self.config.vision_model,
                messages=messages,
                extra_body={"temperature": 0.4},
            ):
                if not chunk:
                    continue
                parts.append(chunk)
            reply = self._prepare_visual_reply("".join(parts).strip())
            self._capture_timer_offer(reply)
            if reply:
                self.history.append({"role": "user", "content": user_text})
                self.history.append({"role": "assistant", "content": reply})
                yield from self._chunk_text(reply)
                return

        reply = self._prepare_visual_reply(self._chat_with_tools(messages, model=self.config.vision_model))
        self._capture_timer_offer(reply)
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})
        yield from self._chunk_text(reply)

    def close_session(self, trigger_text: str) -> tuple[str, Path]:
        farewell = self.respond(trigger_text)
        result = self.tools.memory_write(conversation=self.history, diary_date=date.today().isoformat())
        payload = json.loads(result)
        return farewell, Path(payload["diary_path"])

    def _chat_with_tools(self, messages: list[dict[str, Any]], model: str | None = None) -> str:
        active_messages = list(messages)
        for _ in range(5):
            response = self.client.chat.completions.create(
                model=model or self.config.chat_model,
                messages=active_messages,
                tools=self.tools.tool_schemas(),
                extra_body={"temperature": 0.8},
            )
            assistant_message = self._extract_message(response)
            tool_calls = assistant_message.get("tool_calls", [])
            if tool_calls:
                active_messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_message.get("content", ""),
                        "tool_calls": tool_calls,
                    }
                )
                for tool_call in tool_calls:
                    function = tool_call.get("function", {})
                    tool_name = function.get("name", "")
                    tool_args = function.get("arguments", "{}")
                    result = self.tools.execute_tool_call(tool_name, tool_args)
                    active_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.get("id", tool_name),
                            "tool_name": tool_name,
                            "content": result,
                        }
                    )
                continue

            content = assistant_message.get("content", "").strip()
            if content:
                return self._limit_reply(content)

        return self._limit_reply("嗯，这次我有点卡住了。你再说一句或者换个问法，我立刻接上。")

    def _extract_message(self, response: Any) -> dict[str, Any]:
        choices = self._get_value(response, "choices", [])
        if not choices:
            return {"role": "assistant", "content": ""}
        message = self._get_value(choices[0], "message", {})
        content = self._get_value(message, "content", "")
        tool_calls = self._serialize_tool_calls(self._get_value(message, "tool_calls", []))
        return {
            "role": self._get_value(message, "role", "assistant"),
            "content": self._flatten_content(content),
            "tool_calls": tool_calls,
        }

    def _serialize_tool_calls(self, tool_calls: Any) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for tool_call in tool_calls or []:
            function = self._get_value(tool_call, "function", {})
            serialized.append(
                {
                    "id": self._get_value(tool_call, "id", self._get_value(function, "name", "tool_call")),
                    "type": self._get_value(tool_call, "type", "function"),
                    "function": {
                        "name": self._get_value(function, "name", ""),
                        "arguments": self._get_value(function, "arguments", "{}"),
                    },
                }
            )
        return serialized

    def _flatten_content(self, content: Any) -> str:
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        parts.append(item.get("text", ""))
                    else:
                        parts.append(str(item))
                else:
                    parts.append(str(item))
            return "\n".join(part for part in parts if part).strip()
        return str(content).strip()

    def _build_client(self) -> Any:
        if self.config.provider == "ollama":
            return OllamaClient(config=self.config)
        if not self.config.api_key_configured:
            return None
        return AiPingClient(config=self.config)

    def _load_soul_prompt(self) -> str:
        soul_path = self.config.soul_path
        if soul_path.exists():
            return soul_path.read_text(encoding="utf-8")
        return "你是一个住在镜子里的 AI 护肤闺蜜。"

    def _offline_reply(self) -> str:
        return self._limit_reply(
            "我已经把房间收拾好了，但第三方 API Key 还没配好。"
            "你检查一下 `config.py` 里的授权信息，或者设置 `AIPING_API_KEY`，我们就能正式开聊。"
        )

    def _build_messages(self, user_text: str, image_paths: list[str] | None = None) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": self.build_system_prompt()}]
        messages.extend(self.history[-10:])
        messages.append(self._build_user_message(user_text, image_paths=image_paths))
        return messages

    def _build_user_message(self, user_text: str, image_paths: list[str] | None = None) -> dict[str, Any]:
        content = user_text.strip() or "请结合当前画面回复我。"
        resolved_paths = self._resolve_image_paths(image_paths)
        if not resolved_paths:
            return {"role": "user", "content": content}
        enriched_content = self._build_multimodal_user_text(content, resolved_paths)

        if self.config.provider == "ollama":
            return {
                "role": "user",
                "content": enriched_content,
                "images": [self._encode_image(path) for path in resolved_paths],
            }

        return {
            "role": "user",
            "content": self._build_aiping_multimodal_content(enriched_content, resolved_paths),
        }

    def _resolve_image_paths(self, image_paths: list[str] | None) -> list[Path]:
        resolved: list[Path] = []
        for raw_path in image_paths or []:
            path = Path(raw_path).expanduser()
            if path.exists() and path.is_file():
                resolved.append(path)
        return resolved

    def _encode_image(self, image_path: Path) -> str:
        return base64.b64encode(image_path.read_bytes()).decode("utf-8")

    def _build_data_url(self, image_path: Path) -> str:
        mime_type, _ = mimetypes.guess_type(str(image_path))
        if not mime_type:
            mime_type = "image/jpeg"
        return f"data:{mime_type};base64,{self._encode_image(image_path)}"

    def _build_multimodal_user_text(self, content: str, image_paths: list[Path]) -> str:
        labels = [self._describe_image_path(path, index) for index, path in enumerate(image_paths)]
        if not labels:
            return content

        ordered = "；".join(f"{index + 1}. {label}" for index, label in enumerate(labels))
        directional_prompt = (
            "用户刚刚用了“这里”“这块”“这个痘”这类指向说法，"
            if self._has_directional_reference(content)
            else "如果用户后面用了指向说法，"
        )
        hint = (
            "\n\n当前这一轮你面前可参考的视角顺序如下："
            f"{ordered}。"
            "请把这当成照镜子时直接看着本人说话，不要提图片、照片、自拍、上传、画面或镜头。"
            f"{directional_prompt}必须优先综合完整视角和局部视角，尽量落到明确的脸部区域，"
            "例如额头、左脸颊靠鼻翼、右脸颊外侧、鼻翼、下巴这类范围。"
            "如果不能百分百确定，也先给最接近的区域。"
            "直接说你能确认到的现象、区域和轻重，不要向用户汇报看不清、没抓稳或需要重拍。"
        )
        return f"{content}{hint}"

    def _build_aiping_multimodal_content(self, content: str, image_paths: list[Path]) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = [{"type": "text", "text": content}]
        for path in image_paths:
            payload.append({"type": "image_url", "image_url": {"url": self._build_data_url(path)}})
        return payload

    def _has_directional_reference(self, content: str) -> bool:
        directional_terms = ("这里", "这块", "这个痘", "这边", "这儿", "这一块")
        return any(term in content for term in directional_terms)

    def _describe_image_path(self, image_path: Path, index: int) -> str:
        stem = image_path.stem.lower()
        labels = {
            "full-face": "完整画面",
            "full": "完整画面",
            "left-cheek": "左脸颊局部",
            "right-cheek": "右脸颊局部",
            "forehead": "额头局部",
            "nose": "鼻翼局部",
            "chin": "下巴局部",
        }
        for key, label in labels.items():
            if key in stem:
                return label
        return "局部图" if index else "当前画面"

    def _schedule_local_reminder(self, user_text: str, reminder_request: dict[str, Any]) -> str:
        payload = self.tools.schedule_reminder(
            minutes=reminder_request["minutes"],
            message=reminder_request["message"],
            source_text=user_text,
        )
        self.last_scheduled_reminder = {
            "id": str(payload["id"]),
            "message": str(payload["message"]),
            "due_at": str(payload["due_at"]),
        }
        self.pending_timer_offer = None
        reply = self._limit_reply(
            f"好呀，我已经替你记下了。{reminder_request['minutes']} 分钟后，"
            f"我会提醒你：{payload['message']}"
        )
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def consume_last_scheduled_reminder(self) -> dict[str, str] | None:
        reminder = self.last_scheduled_reminder
        self.last_scheduled_reminder = None
        return reminder

    def _handle_pending_timer_offer(self, user_text: str) -> str | None:
        if not self.pending_timer_offer:
            return None

        offer = self.pending_timer_offer
        if _looks_like_affirmation(user_text) and not _looks_like_decline(user_text):
            return self._schedule_local_reminder(
                user_text,
                {
                    "minutes": int(offer.get("minutes", DEFAULT_MASK_TIMER_MINUTES)),
                    "message": str(offer.get("message", DEFAULT_MASK_REMINDER_MESSAGE)),
                },
            )

        if _looks_like_decline(user_text):
            self.pending_timer_offer = None
            reply = "好呀，那我先不计时。你想开始的时候再叫我一声就好。"
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": reply})
            return reply

        self.pending_timer_offer = None
        return None

    def _capture_timer_offer(self, reply: str) -> None:
        if _looks_like_mask_timer_offer(reply):
            self.pending_timer_offer = {
                "kind": "mask_timer",
                "minutes": DEFAULT_MASK_TIMER_MINUTES,
                "message": DEFAULT_MASK_REMINDER_MESSAGE,
            }
            return
        self.pending_timer_offer = None

    def _reply_limit_reached(self, text: str) -> bool:
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized:
            return False
        sentence_count = sum(normalized.count(mark) for mark in SENTENCE_ENDINGS)
        if sentence_count >= MAX_REPLY_SENTENCES:
            return True
        if len(normalized) < MAX_REPLY_CHARS:
            return False
        return normalized[-1] in SENTENCE_ENDINGS

    def _limit_reply(self, text: str) -> str:
        normalized = sanitize_speech_text(str(text))
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if not normalized:
            return ""

        complete_sentences = [sentence.strip() for sentence in re.findall(r"[^。！？!?]+[。！？!?]", normalized) if sentence.strip()]
        if not complete_sentences:
            return normalized

        selected: list[str] = []
        for sentence in complete_sentences[:MAX_REPLY_SENTENCES]:
            candidate = "".join(selected) + sentence
            if len(candidate) <= MAX_REPLY_CHARS or not selected:
                selected.append(sentence)
                continue
            break

        limited = "".join(selected).strip() or complete_sentences[0].strip()
        if not limited:
            return ""
        if limited[-1] in SENTENCE_ENDINGS:
            return limited
        return f"{limited.rstrip(' ，,、；;：:')}。"

    def _prepare_visual_reply(self, text: str) -> str:
        return self._limit_reply(self._normalize_visual_reply(text))

    def _normalize_visual_reply(self, text: str) -> str:
        normalized = str(text).strip()
        if not normalized:
            return ""

        replacements = [
            (r"(?:这张|这次的)?(?:照片|图片|图|自拍|画面|镜头)里你", "你"),
            (r"(?:这张|这次的)?(?:照片|图片|图|自拍|画面|镜头)上你", "你"),
            (r"(?:这张|这次的)?(?:照片|图片|图|自拍|画面|镜头)里(?=今天|现在|最近)", "你"),
            (r"(?:这张|这次的)?(?:照片|图片|图|自拍|画面|镜头)上(?=今天|现在|最近)", "你"),
            (r"从(?:这张|这次的)?(?:照片|图片|图|自拍|画面|镜头)(?:里|上)?看(?:起来)?", "看起来"),
            (r"(?:这张|这次的)?(?:照片|图片|图|自拍|画面|镜头)里", "你"),
            (r"(?:这张|这次的)?(?:照片|图片|图|自拍|画面|镜头)上", "你"),
            (r"(?:这张|这次的)?(?:照片|图片|图|自拍|画面|镜头)(?=今天|现在|最近|看起来|状态|气色|额头|脸颊|鼻头|下巴|皮肤)", "你"),
        ]
        for pattern, replacement in replacements:
            normalized = re.sub(pattern, replacement, normalized)

        cleanup_patterns = [
            r"^(?:你)?(?:的)?(?:自拍|正脸|脸照|画面|照片|图片|镜头)?(?:有点|稍微)?(?:模糊|不够清晰|看不清|看不到|没看到|没有看到|没接住|没有接住|没抓稳|抓不稳)[，,、；; ]*(?:不过|但|只是)?[，,、；; ]*",
            r"[，,、；; ]+(?:不过|但|只是)?[^。！？!?]*(?:再发一张|发一张|发张|拍张|再拍|上传|发来|发给我|传给我|传张|路径|看得更清楚|看得清楚|更仔细地看|更仔细看看|更清晰)[^。！？!?]*",
            r"(?:如果|要是|等你|你再|请(?:你)?)[^。！？!?]*(?:再发一张|发一张|发张|拍张|再拍|上传|发来|发给我|传给我|传张|路径)[^。！？!?]*",
        ]
        for pattern in cleanup_patterns:
            normalized = re.sub(pattern, "", normalized)

        normalized = re.sub(r"你你+", "你", normalized)
        normalized = re.sub(r"看起来看起来", "看起来", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        normalized = normalized.lstrip("，,、；;：: ")
        if not normalized.strip("。！？!?，,、；;：: "):
            return "你先把脸靠近一点，我接着说你这轮状态。"
        return normalized

    def _chunk_text(self, text: str, size: int = 8) -> Iterator[str]:
        content = text.strip()
        if not content:
            return
        for index in range(0, len(content), size):
            yield content[index : index + size]

    def _get_value(self, obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)
