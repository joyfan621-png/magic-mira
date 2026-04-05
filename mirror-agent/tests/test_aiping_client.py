import tempfile
import unittest
from pathlib import Path

import requests

from config import AppConfig
from third_party_client import AiPingClient, ThirdPartyAPIError


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.ok = True
        self.status_code = 200
        self.text = '{"choices":[{"message":{"content":"ok"}}]}'

    def raise_for_status(self) -> None:
        return None

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
        return FakeResponse({"choices": [{"message": {"role": "assistant", "content": "ok"}}]})


class FakeErrorResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text
        self.ok = False

    def raise_for_status(self) -> None:
        raise requests.HTTPError(f"{self.status_code} error", response=self)

    def json(self) -> dict:
        return {"msg": "请求model参数不在支持列表中"}


class FakeErrorSession:
    def post(self, url: str, headers: dict, json: dict, timeout: int) -> FakeErrorResponse:
        return FakeErrorResponse(404, '{"msg":"请求model参数不在支持列表中"}')


class AiPingClientTests(unittest.TestCase):
    def test_create_posts_to_third_party_endpoint_with_auth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = AppConfig(
                project_root=Path(temp_dir),
                provider="aiping",
                api_key="test-key",
                chat_model="GLM-5",
                vision_model="GLM-5",
                base_url="https://aiping.cn/api/v1/chat/completions",
            )
            fake_session = FakeSession()
            client = AiPingClient(config=config, session=fake_session)

            response = client.chat.completions.create(
                model=config.chat_model,
                messages=[{"role": "user", "content": "hi"}],
                tools=[{"type": "function", "function": {"name": "demo"}}],
                extra_body={"temperature": 0.5},
            )

            self.assertEqual("ok", response["choices"][0]["message"]["content"])
            self.assertEqual(1, len(fake_session.calls))
            call = fake_session.calls[0]
            self.assertEqual("https://aiping.cn/api/v1/chat/completions", call["url"])
            self.assertEqual(f"Bearer {config.api_key}", call["headers"]["Authorization"])
            self.assertEqual("application/json", call["headers"]["Content-Type"])
            self.assertEqual(config.chat_model, call["json"]["model"])
            self.assertEqual(0.5, call["json"]["temperature"])
            self.assertEqual("demo", call["json"]["tools"][0]["function"]["name"])

    def test_create_wraps_upstream_http_errors_with_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = AppConfig(
                project_root=Path(temp_dir),
                provider="aiping",
                api_key="test-key",
                chat_model="GLM-5",
                vision_model="GLM-5",
                base_url="https://aiping.cn/api/v1/chat/completions",
            )
            client = AiPingClient(config=config, session=FakeErrorSession())

            with self.assertRaises(ThirdPartyAPIError) as ctx:
                client.chat.completions.create(
                    model="GLM-4V",
                    messages=[{"role": "user", "content": "hi"}],
                )

            self.assertIn("404", str(ctx.exception))
            self.assertIn("请求model参数不在支持列表中", str(ctx.exception))
