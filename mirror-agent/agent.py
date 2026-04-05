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
    if "提醒" not in normalized:
        return None
    match = re.search(r"(\d{1,3})\s*分钟", normalized)
    if not match:
        return None
    minutes = int(match.group(1))
    message = "面膜时间到了，记得摘掉哦。" if "面膜" in normalized else "提醒时间到了哦。"
    return {"minutes": minutes, "message": message}


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
        image_path = coerce_image_path(user_text)
        if image_path:
            self.awaiting_photo = False
            return self.respond_to_image(image_path)

        if image_paths:
            return self._respond_with_multimodal_context(user_text, image_paths=image_paths)

        reminder_request = parse_reminder_request(user_text)
        if reminder_request:
            return self._schedule_local_reminder(user_text, reminder_request)

        if should_start_photo_flow(user_text):
            if camera_active:
                reply = "镜头我已经打开在看啦，只是这一轮画面没抓稳。你先别急，保持别动太快，再自然说一遍，我继续看。"
                self.history.append({"role": "user", "content": user_text})
                self.history.append({"role": "assistant", "content": reply})
                return reply
            self.awaiting_photo = True
            reply = "好嘞，发张照片过来～ 你也可以直接把本地自拍路径贴给我。"
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
        reply = self._prepare_visual_reply(self._chat_with_tools(messages))
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def respond_to_image(self, image_path: str, note: str = "") -> str:
        analysis = self.tools.analyze_selfie(image_path=image_path, note=note)
        reply = self._prepare_visual_reply(
            str(analysis.get("reply", "")).strip() or "我这次没拿到稳稳的结果。你再来一次，我接着看。"
        )
        self.awaiting_photo = False
        self.tools.record_selfie_analysis(analysis=analysis, image_path=image_path, note=note)
        self.history.append({"role": "user", "content": f"[图片] {image_path} {note}".strip()})
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def stream_respond(
        self,
        user_text: str,
        image_paths: list[str] | None = None,
        camera_active: bool = False,
    ) -> Iterator[str]:
        image_path = coerce_image_path(user_text)
        if image_path:
            reply = self.respond_to_image(image_path)
            yield from self._chunk_text(reply)
            return

        if image_paths:
            yield from self._stream_with_multimodal_context(user_text, image_paths=image_paths)
            return

        reminder_request = parse_reminder_request(user_text)
        if reminder_request:
            reply = self._schedule_local_reminder(user_text, reminder_request)
            yield from self._chunk_text(reply)
            return

        if should_start_photo_flow(user_text):
            if camera_active:
                reply = "镜头我已经打开在看啦，只是这一轮画面没抓稳。你先别急，保持别动太快，再自然说一遍，我继续看。"
                self.history.append({"role": "user", "content": user_text})
                self.history.append({"role": "assistant", "content": reply})
                yield from self._chunk_text(reply)
                return
            self.awaiting_photo = True
            reply = "好嘞，发张照片过来～ 你也可以直接把本地自拍路径贴给我。"
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
            if reply:
                self.history.append({"role": "user", "content": user_text})
                self.history.append({"role": "assistant", "content": reply})
                yield from self._chunk_text(reply)
                return

        reply = self._prepare_visual_reply(self._chat_with_tools(messages, model=self.config.vision_model))
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

        if self.config.provider == "ollama":
            return {
                "role": "user",
                "content": content,
                "images": [self._encode_image(path) for path in resolved_paths],
            }

        return {
            "role": "user",
            "content": self._build_aiping_multimodal_content(content, resolved_paths),
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

    def _build_aiping_multimodal_content(self, content: str, image_paths: list[Path]) -> list[dict[str, Any]]:
        labels = [self._describe_image_path(path, index) for index, path in enumerate(image_paths)]
        hint = ""
        if labels:
            ordered = "；".join(f"{index + 1}. {label}" for index, label in enumerate(labels))
            hint = (
                "\n\n附带画面顺序如下："
                f"{ordered}。如果用户说“这里”或“这块”，请优先结合这些局部图判断具体部位，"
                "并在回答里明确说出你观察到的区域。"
            )

        payload: list[dict[str, Any]] = [{"type": "text", "text": f"{content}{hint}"}]
        for path in image_paths:
            payload.append({"type": "image_url", "image_url": {"url": self._build_data_url(path)}})
        return payload

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
        reply = self._limit_reply(
            f"好呀，我已经替你记下了。{reminder_request['minutes']} 分钟后，"
            f"我会提醒你：{payload['message']}"
        )
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})
        return reply

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

        normalized = re.sub(r"你你+", "你", normalized)
        normalized = re.sub(r"看起来看起来", "看起来", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
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
