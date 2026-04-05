import tempfile
import unittest
from pathlib import Path

from config import AppConfig
from ollama_client import OllamaAPIError, OllamaClient


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.ok = True
        self.status_code = 200
        self.text = '{"message":{"content":"ok"}}'

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def post(self, url: str, headers: dict, json: dict, timeout: int) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return FakeResponse(
            {
                "message": {
                    "role": "assistant",
                    "content": "ok",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "memory_read",
                                "arguments": {"target": "context"},
                            }
                        }
                    ],
                }
            }
        )


class FakeErrorResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text
        self.ok = False

    def json(self) -> dict:
        return {"error": "model not loaded"}


class FakeErrorSession:
    def post(self, url: str, headers: dict, json: dict, timeout: int) -> FakeErrorResponse:
        return FakeErrorResponse(503, '{"error":"model not loaded"}')


class OllamaClientTests(unittest.TestCase):
    def test_create_posts_to_local_chat_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = AppConfig(
                project_root=Path(temp_dir),
                provider="ollama",
                api_key="",
                chat_model="gemma4:e2b",
                vision_model="gemma4:e2b",
                base_url="http://127.0.0.1:11434",
            )
            fake_session = FakeSession()
            client = OllamaClient(config=config, session=fake_session)

            response = client.chat.completions.create(
                model=config.chat_model,
                messages=[
                    {"role": "user", "content": "hi"},
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "memory_read",
                                    "arguments": '{"target":"context"}',
                                },
                            }
                        ],
                    },
                    {"role": "tool", "tool_name": "memory_read", "content": "ok"},
                ],
                tools=[{"type": "function", "function": {"name": "memory_read"}}],
                extra_body={"temperature": 0.5},
            )

            self.assertEqual("ok", response["choices"][0]["message"]["content"])
            self.assertEqual("memory_read", response["choices"][0]["message"]["tool_calls"][0]["function"]["name"])
            self.assertEqual(1, len(fake_session.calls))
            call = fake_session.calls[0]
            self.assertEqual("http://127.0.0.1:11434/api/chat", call["url"])
            self.assertEqual("application/json", call["headers"]["Content-Type"])
            self.assertFalse(call["json"]["stream"])
            self.assertFalse(call["json"]["think"])
            self.assertEqual(0.5, call["json"]["options"]["temperature"])
            self.assertEqual({"target": "context"}, call["json"]["messages"][1]["tool_calls"][0]["function"]["arguments"])

    def test_create_wraps_local_http_errors_with_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = AppConfig(
                project_root=Path(temp_dir),
                provider="ollama",
                api_key="",
                chat_model="gemma4:e2b",
                vision_model="gemma4:e2b",
                base_url="http://127.0.0.1:11434",
            )
            client = OllamaClient(config=config, session=FakeErrorSession())

            with self.assertRaises(OllamaAPIError) as ctx:
                client.chat.completions.create(
                    model=config.chat_model,
                    messages=[{"role": "user", "content": "hi"}],
                )

            self.assertIn("503", str(ctx.exception))
            self.assertIn("model not loaded", str(ctx.exception))
