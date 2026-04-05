from __future__ import annotations

from typing import Any

import requests

from config import AppConfig


class ThirdPartyAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class AiPingClient:
    def __init__(self, config: AppConfig, session: requests.Session | Any | None = None) -> None:
        self.config = config
        self.session = session or requests.Session()
        self.chat = _ChatAPI(self)

    @property
    def headers(self) -> dict[str, str]:
        authorization = self.config.api_key.strip()
        if authorization and not authorization.lower().startswith("bearer "):
            authorization = f"Bearer {authorization}"
        return {
            "Authorization": authorization,
            "Content-Type": "application/json",
        }


class _ChatAPI:
    def __init__(self, client: AiPingClient) -> None:
        self.completions = _CompletionsAPI(client)


class _CompletionsAPI:
    def __init__(self, client: AiPingClient) -> None:
        self.client = client

    def create(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
        if extra_body:
            payload.update(extra_body)

        try:
            response = self.client.session.post(
                self.client.config.base_url,
                headers=self.client.headers,
                json=payload,
                timeout=self.client.config.request_timeout,
            )
        except requests.RequestException as exc:
            raise ThirdPartyAPIError(f"第三方接口连接失败：{exc}") from exc

        if not response.ok:
            body = response.text[:500]
            message = _extract_error_message(response)
            raise ThirdPartyAPIError(
                f"第三方接口请求失败（{response.status_code}）：{message}",
                status_code=response.status_code,
                body=body,
            )

        try:
            return response.json()
        except ValueError as exc:
            body = response.text[:500]
            raise ThirdPartyAPIError(
                "第三方接口返回的不是 JSON，先别急，我已经把问题拦下来了。",
                status_code=response.status_code,
                body=body,
            ) from exc


def _extract_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:200] or "上游没有返回可读错误信息"

    if isinstance(payload, dict):
        for key in ("msg", "message", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return response.text[:200] or "上游没有返回可读错误信息"
