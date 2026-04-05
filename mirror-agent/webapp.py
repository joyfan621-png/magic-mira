from __future__ import annotations

import asyncio
import json
import re
import tempfile
from copy import deepcopy
from pathlib import Path
from threading import Lock
from typing import Any, Callable

from agent import MirrorAgent
from ollama_client import OllamaAPIError
from reminders import ReminderScheduler
from third_party_client import ThirdPartyAPIError
from voice_input import extract_wake_text, transcribe_audio_file
from voice_output import VoiceOutput

try:
    from flask import Flask, Response, jsonify, render_template, request, send_from_directory, stream_with_context
except ImportError as exc:  # pragma: no cover - depends on environment
    raise ImportError(
        "Flask is required for the web UI. Run `python3 -m pip install -r requirements.txt` first."
    ) from exc


class TabletStateStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._state: dict[str, Any] = {
            "scene": "idle",
            "reminder": None,
            "lastTriggeredReminder": None,
        }

    def read(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._state)

    def update(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            next_state = deepcopy(self._state)
            for key, value in updates.items():
                if isinstance(next_state.get(key), dict) and isinstance(value, dict):
                    next_state[key] = {**next_state[key], **value}
                else:
                    next_state[key] = value
            self._state = next_state
            return deepcopy(self._state)


def create_app(
    agent: MirrorAgent | Any | None = None,
    transcribe_audio: Callable[[Path], str] | None = None,
    voice_output_factory: Callable[[Path], Any] | None = None,
    reminder_scheduler: ReminderScheduler | None = None,
) -> Flask:
    app = Flask(__name__)
    app.config["UPLOAD_FOLDER"] = tempfile.mkdtemp(prefix="mirror-agent-upload-")
    app.config["VOICE_OUTPUT_FOLDER"] = tempfile.mkdtemp(prefix="mirror-agent-voice-")
    app.reminder_scheduler = reminder_scheduler or ReminderScheduler()  # type: ignore[attr-defined]
    app.agent = agent or MirrorAgent(reminder_scheduler=app.reminder_scheduler)  # type: ignore[attr-defined]
    app.tablet_state_store = TabletStateStore()  # type: ignore[attr-defined]
    app.transcribe_audio = transcribe_audio or transcribe_audio_file  # type: ignore[attr-defined]
    default_voice_factory = voice_output_factory or (lambda temp_dir: VoiceOutput(temp_dir=temp_dir))
    app.voice_output = default_voice_factory(Path(app.config["VOICE_OUTPUT_FOLDER"]))  # type: ignore[attr-defined]
    app.config["VOICE_OUTPUT_FOLDER"] = str(
        getattr(app.voice_output, "temp_dir", app.config["VOICE_OUTPUT_FOLDER"])
    )

    def json_error(message: str, status_code: int = 500) -> Any:
        return jsonify({"error": message}), status_code

    def normalize_voice_prompt(transcript: str) -> str:
        normalized = str(transcript).strip()
        if not normalized:
            return ""
        wake_prompt = extract_wake_text(normalized)
        if wake_prompt is None:
            return normalized
        return wake_prompt.strip()

    def synthesize_audio_url(reply: str) -> str:
        audio_path = asyncio.run(app.voice_output.generate_audio_file(reply))  # type: ignore[attr-defined]
        return f"/audio/{Path(audio_path).name}"

    def current_assistant_label() -> str:
        getter = getattr(app.agent, "display_name", None)  # type: ignore[attr-defined]
        if callable(getter):
            label = str(getter()).strip()
            if label:
                return label
        return "我"

    def consume_scheduled_reminder() -> dict[str, str] | None:
        consumer = getattr(app.agent, "consume_last_scheduled_reminder", None)  # type: ignore[attr-defined]
        if not callable(consumer):
            return None
        payload = consumer()
        if not payload:
            return None
        return {
            "id": str(payload.get("id", "")).strip(),
            "message": str(payload.get("message", "")).strip(),
            "due_at": str(payload.get("due_at", "")).strip(),
        }

    def build_interaction_payload(user_text: str, reply: str) -> dict[str, str]:
        joined = f"{user_text}\n{reply}"
        if any(keyword in joined for keyword in ("夸", "真好看", "漂亮", "可爱", "真棒", "好乖")):
            return {"ui_effect": "sparkle"}
        if any(keyword in joined for keyword in ("抱抱", "别担心", "没关系", "辛苦", "心疼")):
            return {"ui_effect": "heart"}
        if any(keyword in joined for keyword in ("痘", "泛红", "鼻翼", "脸颊", "下巴")):
            return {"ui_effect": "focus"}
        if "面膜" in joined:
            return {"ui_effect": "glow"}
        return {"ui_effect": "ripple"}

    def _safe_prefix(filename: str, fallback: str) -> str:
        stem = Path(filename or "").stem
        cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", stem).strip("-").lower()
        return cleaned or fallback

    def save_upload(file_storage: Any, default_suffix: str, fallback_prefix: str = "upload") -> Path | None:
        if file_storage is None or not getattr(file_storage, "filename", ""):
            return None

        suffix = Path(file_storage.filename).suffix or default_suffix
        prefix = _safe_prefix(getattr(file_storage, "filename", ""), fallback_prefix)
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
            prefix=f"{prefix}-",
            dir=app.config["UPLOAD_FOLDER"],
        ) as temp_file:
            file_storage.save(temp_file)
            return Path(temp_file.name)

    def collect_frame_image_paths() -> list[str] | None:
        image_paths: list[str] = []
        frame_path = save_upload(request.files.get("frame"), ".jpg", fallback_prefix="full-face")
        if frame_path is not None:
            image_paths.append(str(frame_path))

        for index, region in enumerate(request.files.getlist("frame_regions"), start=1):
            region_path = save_upload(region, ".jpg", fallback_prefix=f"region-{index}")
            if region_path is not None:
                image_paths.append(str(region_path))

        return image_paths or None

    def is_camera_active() -> bool:
        return request.form.get("camera_active", "").strip().lower() in {"1", "true", "yes", "on"}

    @app.get("/")
    def index() -> str:
        return render_template("index.html", assistant_label=current_assistant_label())

    @app.get("/tablet")
    def tablet() -> str:
        return render_template("tablet.html")

    @app.get("/api/tablet-state")
    def tablet_state() -> Any:
        return jsonify(app.tablet_state_store.read())  # type: ignore[attr-defined]

    @app.post("/api/tablet-state")
    def update_tablet_state() -> Any:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "平板状态更新格式不对。"}), 400
        return jsonify(app.tablet_state_store.update(payload))  # type: ignore[attr-defined]

    @app.post("/api/chat")
    def chat() -> Any:
        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message", "")).strip()
        if not message:
            return jsonify({"error": "先说一句嘛，我才知道该怎么接你。"}), 400

        try:
            reply = app.agent.respond(message)  # type: ignore[attr-defined]
            scheduled_reminder = consume_scheduled_reminder()
        except (ThirdPartyAPIError, OllamaAPIError) as exc:
            return json_error(str(exc), 502)
        except Exception as exc:
            return json_error(f"聊天时出了点岔子：{exc}", 502)
        response_payload = {
            "reply": reply,
            "assistant_label": current_assistant_label(),
            **build_interaction_payload(message, reply),
        }
        if scheduled_reminder:
            response_payload["scheduled_reminder"] = scheduled_reminder
        return jsonify(response_payload)

    @app.post("/api/image")
    def image_chat() -> Any:
        image = request.files.get("image")
        note = request.form.get("note", "").strip()
        if image is None or not image.filename:
            return jsonify({"error": "请先选一张图片再发我看。"}), 400

        temp_path = save_upload(image, ".jpg", fallback_prefix="uploaded-image")
        assert temp_path is not None

        try:
            reply = app.agent.respond_to_image(str(temp_path), note)  # type: ignore[attr-defined]
            audio_url = synthesize_audio_url(reply)
            scheduled_reminder = consume_scheduled_reminder()
        except (ThirdPartyAPIError, OllamaAPIError) as exc:
            return json_error(str(exc), 502)
        except Exception as exc:
            return json_error(f"图片分析时出了点岔子：{exc}", 502)
        response_payload = {
            "reply": reply,
            "image_path": str(temp_path),
            "audio_url": audio_url,
            "assistant_label": current_assistant_label(),
            **build_interaction_payload(note, reply),
        }
        if scheduled_reminder:
            response_payload["scheduled_reminder"] = scheduled_reminder
        return jsonify(response_payload)

    @app.post("/api/voice-chat")
    def voice_chat() -> Any:
        audio = request.files.get("audio")
        if audio is None or not audio.filename:
            return jsonify({"error": "请先录一段语音，我才听得到你。"}), 400

        temp_path = save_upload(audio, ".webm", fallback_prefix="voice-round")
        assert temp_path is not None
        image_paths = collect_frame_image_paths()
        camera_active = is_camera_active()

        try:
            transcript = app.transcribe_audio(temp_path)  # type: ignore[attr-defined]
            prompt = normalize_voice_prompt(transcript)
            if not prompt:
                return jsonify({"error": "这句我还没听清，你再自然说一遍就好。"}), 400

            reply = app.agent.respond(prompt, image_paths=image_paths, camera_active=camera_active)  # type: ignore[attr-defined]
            audio_url = synthesize_audio_url(reply)
            scheduled_reminder = consume_scheduled_reminder()
        except (ThirdPartyAPIError, OllamaAPIError) as exc:
            return json_error(str(exc), 502)
        except Exception as exc:
            return json_error(f"语音对话时出了点岔子：{exc}", 502)

        response_payload = {
            "transcript": prompt,
            "reply": reply,
            "audio_url": audio_url,
            "assistant_label": current_assistant_label(),
            **build_interaction_payload(prompt, reply),
        }
        if scheduled_reminder:
            response_payload["scheduled_reminder"] = scheduled_reminder
        return jsonify(response_payload)

    @app.post("/api/voice-chat-stream")
    def voice_chat_stream() -> Any:
        audio = request.files.get("audio")
        if audio is None or not audio.filename:
            return jsonify({"error": "请先录一段语音，我才听得到你。"}), 400

        temp_path = save_upload(audio, ".webm", fallback_prefix="voice-round")
        assert temp_path is not None
        image_paths = collect_frame_image_paths()
        camera_active = is_camera_active()

        try:
            transcript = app.transcribe_audio(temp_path)  # type: ignore[attr-defined]
            prompt = normalize_voice_prompt(transcript)
            if not prompt:
                return jsonify({"error": "这句我还没听清，你再自然说一遍就好。"}), 400
        except (ThirdPartyAPIError, OllamaAPIError) as exc:
            return json_error(str(exc), 502)
        except Exception as exc:
            return json_error(f"语音对话时出了点岔子：{exc}", 502)

        def generate() -> Any:
            yield json.dumps(
                {"type": "transcript", "text": prompt, "assistant_label": current_assistant_label()},
                ensure_ascii=False,
            ) + "\n"

            try:
                reply_parts: list[str] = []
                for chunk in app.agent.stream_respond(  # type: ignore[attr-defined]
                    prompt,
                    image_paths=image_paths,
                    camera_active=camera_active,
                ):
                    if not chunk:
                        continue
                    reply_parts.append(chunk)
                    yield json.dumps(
                        {
                            "type": "reply_delta",
                            "delta": chunk,
                            "text": "".join(reply_parts),
                            "assistant_label": current_assistant_label(),
                        },
                        ensure_ascii=False,
                    ) + "\n"

                reply = "".join(reply_parts).strip()
                audio_url = synthesize_audio_url(reply)
                scheduled_reminder = consume_scheduled_reminder()
                yield json.dumps(
                    {
                        "type": "reply_done",
                        "reply": reply,
                        "audio_url": audio_url,
                        "assistant_label": current_assistant_label(),
                        "scheduled_reminder": scheduled_reminder,
                        **build_interaction_payload(prompt, reply),
                    },
                    ensure_ascii=False,
                ) + "\n"
            except (ThirdPartyAPIError, OllamaAPIError) as exc:
                yield json.dumps({"type": "error", "error": str(exc)}, ensure_ascii=False) + "\n"
            except Exception as exc:
                yield json.dumps({"type": "error", "error": f"语音对话时出了点岔子：{exc}"}, ensure_ascii=False) + "\n"

        return Response(stream_with_context(generate()), mimetype="application/x-ndjson")

    @app.get("/audio/<path:filename>")
    def audio_file(filename: str) -> Any:
        return send_from_directory(app.config["VOICE_OUTPUT_FOLDER"], filename, mimetype="audio/mpeg")

    @app.get("/api/reminders/due")
    def due_reminders() -> Any:
        reminders = []
        for reminder in app.reminder_scheduler.pop_due():  # type: ignore[attr-defined]
            reminders.append(
                {
                    "id": reminder.id,
                    "message": reminder.message,
                    "due_at": reminder.due_at,
                    "audio_url": synthesize_audio_url(reminder.message),
                    "assistant_label": current_assistant_label(),
                    "ui_effect": "glow" if "面膜" in reminder.message else "sparkle",
                }
            )
        return jsonify({"reminders": reminders, "assistant_label": current_assistant_label()})

    @app.post("/api/end")
    def end_session() -> Any:
        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message", "晚安")).strip() or "晚安"
        try:
            reply, diary_path = app.agent.close_session(message)  # type: ignore[attr-defined]
        except (ThirdPartyAPIError, OllamaAPIError) as exc:
            return json_error(str(exc), 502)
        except Exception as exc:
            return json_error(f"结束会话时出了点岔子：{exc}", 502)
        return jsonify({"reply": reply, "diary_path": str(diary_path), "assistant_label": current_assistant_label()})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=False)
