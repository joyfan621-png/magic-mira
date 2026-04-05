import io
import tempfile
import unittest
from pathlib import Path

from reminders import ReminderScheduler
from webapp import create_app


class StubAgent:
    def __init__(self) -> None:
        self.chat_messages: list[str] = []
        self.image_calls: list[tuple[str, str]] = []
        self.voice_image_paths: list[list[str]] = []
        self.voice_camera_flags: list[bool] = []
        self.closed_with: list[str] = []

    def respond(
        self,
        user_text: str,
        image_paths: list[str] | None = None,
        camera_active: bool = False,
    ) -> str:
        self.chat_messages.append(user_text)
        if image_paths:
            self.voice_image_paths.append(image_paths)
        self.voice_camera_flags.append(camera_active)
        return f"reply:{user_text}"

    def respond_to_image(self, image_path: str, note: str = "") -> str:
        self.image_calls.append((image_path, note))
        return f"image-reply:{note}"

    def close_session(self, trigger_text: str) -> tuple[str, Path]:
        self.closed_with.append(trigger_text)
        return "bye-reply", Path("/tmp/fake-diary.md")

    def stream_respond(
        self,
        user_text: str,
        image_paths: list[str] | None = None,
        camera_active: bool = False,
    ):
        self.chat_messages.append(f"stream:{user_text}")
        if image_paths:
            self.voice_image_paths.append(image_paths)
        self.voice_camera_flags.append(camera_active)
        for chunk in ("reply:", user_text):
            yield chunk


class StubVoiceOutput:
    def __init__(self, temp_dir: Path) -> None:
        self.temp_dir = temp_dir
        self.spoken: list[str] = []

    async def generate_audio_file(self, text: str) -> Path:
        self.spoken.append(text)
        output_path = self.temp_dir / "voice-reply.mp3"
        output_path.write_bytes(b"fake-mp3")
        return output_path


class ExplodingAgent:
    def respond(self, user_text: str, image_paths: list[str] | None = None, camera_active: bool = False) -> str:
        raise RuntimeError("chat broke")

    def respond_to_image(self, image_path: str, note: str = "") -> str:
        raise RuntimeError("image broke")

    def close_session(self, trigger_text: str) -> tuple[str, Path]:
        raise RuntimeError("end broke")


class WebAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stub_agent = StubAgent()
        self.voice_temp_dir = Path(tempfile.mkdtemp(prefix="mirror-agent-voice-test-"))
        self.voice_output = StubVoiceOutput(self.voice_temp_dir)
        self.app = create_app(
            agent=self.stub_agent,
            transcribe_audio=lambda path: "看看我",
            voice_output_factory=lambda temp_dir: self.voice_output,
        )
        self.client = self.app.test_client()

    def test_index_page_renders(self) -> None:
        response = self.client.get("/")

        self.assertEqual(200, response.status_code)
        html = response.get_data(as_text=True)
        self.assertIn("镜中闺蜜", html)
        self.assertIn('data-assistant-label="我"', html)

    def test_tablet_page_renders(self) -> None:
        response = self.client.get("/tablet")

        self.assertEqual(200, response.status_code)
        html = response.get_data(as_text=True)
        self.assertIn("镜面精灵屏", html)
        self.assertIn('id="tablet-stage"', html)
        self.assertIn('id="tablet-scene-label"', html)

    def test_chat_route_returns_json_reply(self) -> None:
        response = self.client.post("/api/chat", json={"message": "今天脸有点干"})

        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual("reply:今天脸有点干", payload["reply"])
        self.assertEqual("我", payload["assistant_label"])

    def test_image_route_requires_file(self) -> None:
        response = self.client.post("/api/image", data={"note": "鼻翼有点红"})

        self.assertEqual(400, response.status_code)
        self.assertIn("请先选一张图片", response.get_json()["error"])

    def test_image_route_saves_upload_and_returns_reply(self) -> None:
        data = {
            "note": "今天有点红",
            "image": (io.BytesIO(b"fake-image-bytes"), "skin.jpg"),
        }

        response = self.client.post("/api/image", data=data, content_type="multipart/form-data")

        self.assertEqual(200, response.status_code)
        self.assertEqual("image-reply:今天有点红", response.get_json()["reply"])
        self.assertEqual("/audio/voice-reply.mp3", response.get_json()["audio_url"])
        self.assertEqual(["image-reply:今天有点红"], self.voice_output.spoken)
        saved_path, note = self.stub_agent.image_calls[0]
        self.assertEqual("今天有点红", note)
        self.assertTrue(Path(saved_path).exists())

    def test_end_route_returns_diary_path(self) -> None:
        response = self.client.post("/api/end", json={"message": "晚安"})

        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual("bye-reply", payload["reply"])
        self.assertEqual("/tmp/fake-diary.md", payload["diary_path"])

    def test_chat_route_returns_json_error_when_agent_raises(self) -> None:
        client = create_app(agent=ExplodingAgent()).test_client()

        response = client.post("/api/chat", json={"message": "今天脸有点干"})

        self.assertEqual(502, response.status_code)
        self.assertEqual("application/json", response.content_type)
        self.assertIn("chat broke", response.get_json()["error"])

    def test_image_route_returns_json_error_when_agent_raises(self) -> None:
        client = create_app(agent=ExplodingAgent()).test_client()
        data = {
            "note": "今天有点红",
            "image": (io.BytesIO(b"fake-image-bytes"), "skin.jpg"),
        }

        response = client.post("/api/image", data=data, content_type="multipart/form-data")

        self.assertEqual(502, response.status_code)
        self.assertEqual("application/json", response.content_type)
        self.assertIn("image broke", response.get_json()["error"])

    def test_voice_route_transcribes_audio_and_returns_audio_url(self) -> None:
        data = {
            "audio": (io.BytesIO(b"fake-audio-bytes"), "voice.webm"),
        }

        response = self.client.post("/api/voice-chat", data=data, content_type="multipart/form-data")

        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual("看看我", payload["transcript"])
        self.assertEqual("reply:看看我", payload["reply"])
        self.assertTrue(payload["audio_url"].startswith("/audio/"))
        self.assertEqual(["reply:看看我"], self.voice_output.spoken)

    def test_voice_route_requires_audio_file(self) -> None:
        response = self.client.post("/api/voice-chat", data={}, content_type="multipart/form-data")

        self.assertEqual(400, response.status_code)
        self.assertIn("请先录一段语音", response.get_json()["error"])

    def test_voice_route_accepts_plain_natural_speech_without_wake_word(self) -> None:
        client = create_app(
            agent=self.stub_agent,
            transcribe_audio=lambda path: "今天脸有点干",
            voice_output_factory=lambda temp_dir: self.voice_output,
        ).test_client()

        data = {
            "audio": (io.BytesIO(b"fake-audio-bytes"), "voice.webm"),
        }
        response = client.post("/api/voice-chat", data=data, content_type="multipart/form-data")

        self.assertEqual(200, response.status_code)
        self.assertEqual("今天脸有点干", response.get_json()["transcript"])
        self.assertEqual("reply:今天脸有点干", response.get_json()["reply"])

    def test_audio_file_route_serves_generated_mp3(self) -> None:
        path = self.voice_temp_dir / "voice-reply.mp3"
        path.write_bytes(b"fake-mp3")

        response = self.client.get(f"/audio/{path.name}")

        self.assertEqual(200, response.status_code)
        self.assertEqual(b"fake-mp3", response.data)

    def test_voice_stream_route_emits_transcript_and_reply_events(self) -> None:
        data = {
            "audio": (io.BytesIO(b"fake-audio-bytes"), "voice.webm"),
        }

        response = self.client.post("/api/voice-chat-stream", data=data, content_type="multipart/form-data")

        self.assertEqual(200, response.status_code)
        self.assertEqual("application/x-ndjson", response.mimetype)
        body = response.get_data(as_text=True)
        self.assertIn('"type": "transcript"', body)
        self.assertIn('"text": "看看我"', body)
        self.assertIn('"type": "reply_delta"', body)
        self.assertIn('"type": "reply_done"', body)
        self.assertIn('"/audio/voice-reply.mp3"', body)

    def test_voice_stream_route_accepts_plain_natural_speech_without_wake_word(self) -> None:
        client = create_app(
            agent=self.stub_agent,
            transcribe_audio=lambda path: "今天脸有点干",
            voice_output_factory=lambda temp_dir: self.voice_output,
        ).test_client()

        data = {
            "audio": (io.BytesIO(b"fake-audio-bytes"), "voice.webm"),
        }

        response = client.post("/api/voice-chat-stream", data=data, content_type="multipart/form-data")

        self.assertEqual(200, response.status_code)
        body = response.get_data(as_text=True)
        self.assertIn('"text": "今天脸有点干"', body)
        self.assertIn('"reply": "reply:今天脸有点干"', body)

    def test_voice_route_passes_optional_camera_frame_to_agent(self) -> None:
        data = {
            "audio": (io.BytesIO(b"fake-audio-bytes"), "voice.webm"),
            "frame": (io.BytesIO(b"fake-frame-bytes"), "frame.jpg"),
        }

        response = self.client.post("/api/voice-chat", data=data, content_type="multipart/form-data")

        self.assertEqual(200, response.status_code)
        self.assertEqual("reply:看看我", response.get_json()["reply"])
        self.assertEqual(1, len(self.stub_agent.voice_image_paths))
        saved_frame_path = self.stub_agent.voice_image_paths[0][0]
        self.assertTrue(Path(saved_frame_path).exists())

    def test_voice_route_marks_camera_active_even_when_frame_missing(self) -> None:
        data = {
            "audio": (io.BytesIO(b"fake-audio-bytes"), "voice.webm"),
            "camera_active": "true",
        }

        response = self.client.post("/api/voice-chat", data=data, content_type="multipart/form-data")

        self.assertEqual(200, response.status_code)
        self.assertTrue(self.stub_agent.voice_camera_flags[-1])

    def test_voice_stream_route_passes_optional_camera_frame_to_agent(self) -> None:
        data = {
            "audio": (io.BytesIO(b"fake-audio-bytes"), "voice.webm"),
            "frame": (io.BytesIO(b"fake-frame-bytes"), "frame.jpg"),
        }

        response = self.client.post("/api/voice-chat-stream", data=data, content_type="multipart/form-data")

        self.assertEqual(200, response.status_code)
        body = response.get_data(as_text=True)
        self.assertIn('"reply": "reply:看看我"', body)
        self.assertEqual(1, len(self.stub_agent.voice_image_paths))
        saved_frame_path = self.stub_agent.voice_image_paths[0][0]
        self.assertTrue(Path(saved_frame_path).exists())

    def test_voice_stream_route_marks_camera_active_even_when_frame_missing(self) -> None:
        data = {
            "audio": (io.BytesIO(b"fake-audio-bytes"), "voice.webm"),
            "camera_active": "true",
        }

        response = self.client.post("/api/voice-chat-stream", data=data, content_type="multipart/form-data")

        self.assertEqual(200, response.status_code)
        self.assertEqual("application/x-ndjson", response.mimetype)
        response.get_data(as_text=True)
        self.assertTrue(self.stub_agent.voice_camera_flags[-1])

    def test_due_reminders_route_returns_ready_items_with_audio(self) -> None:
        scheduler = ReminderScheduler()
        scheduler.schedule_in_minutes(
            minutes=0,
            message="面膜时间到了，记得摘掉哦。",
            source_text="我刚敷上了面膜，15分钟后提醒我摘掉。",
        )
        client = create_app(
            agent=self.stub_agent,
            transcribe_audio=lambda path: "看看我",
            voice_output_factory=lambda temp_dir: self.voice_output,
            reminder_scheduler=scheduler,
        ).test_client()

        response = client.get("/api/reminders/due")

        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual(1, len(payload["reminders"]))
        self.assertEqual("面膜时间到了，记得摘掉哦。", payload["reminders"][0]["message"])
        self.assertTrue(payload["reminders"][0]["audio_url"].startswith("/audio/"))
