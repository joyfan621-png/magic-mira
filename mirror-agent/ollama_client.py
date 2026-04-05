from __future__ import annotations

import json
from typing import Any, Iterator

import requests

from config import AppConfig


OLLAMA_OPTION_KEYS = {
    "temperature",
    "top_k",
    "top_p",
    "num_ctx",
    "num_predict",
    "repeat_penalty",
    "seed",
    "stop",
}


class OllamaAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class OllamaClient:
    provider_name = "ollama"

    def __init__(self, config: AppConfig, session: requests.Session | Any | None = None) -> None:
        self.config = config
        self.session = session or requests.Session()
        self.chat = _ChatAPI(self)

    @property
    def base_url(self) -> str:
        return self.config.base_url.rstrip("/")


class _ChatAPI:
    def __init__(self, client: OllamaClient) -> None:
        self.completions = _CompletionsAPI(client)


class _CompletionsAPI:
    def __init__(self, client: OllamaClient) -> None:
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
            "messages": _normalize_messages(messages),
            "stream": False,
            "think": False,
        }
        if tools:
            payload["tools"] = tools

        options: dict[str, Any] = {}
        for key, value in (extra_body or {}).items():
            if key in OLLAMA_OPTION_KEYS:
                options[key] = value
            else:
                payload[key] = value
        if options:
            payload["options"] = options

        try:
            response = self.client.session.post(
                f"{self.client.base_url}/api/chat",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.client.config.request_timeout,
            )
        except requests.RequestException as exc:
            raise OllamaAPIError(f"本地 Ollama 没连上：{exc}") from exc

        if not response.ok:
            body = response.text[:500]
            message = _extract_error_message(response)
            raise OllamaAPIError(
                f"本地 Ollama 请求失败（{response.status_code}）：{message}",
                status_code=response.status_code,
                body=body,
            )

        try:
            data = response.json()
        except ValueError as exc:
            body = response.text[:500]
            raise OllamaAPIError(
                "本地 Ollama 返回的不是 JSON，我先把这次异常拦下来了。",
                status_code=response.status_code,
                body=body,
            ) from exc

        return {
            "choices": [
                {
                    "message": _normalize_response_message(data.get("message", {})),
                }
            ]
        }

    def stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        extra_body: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": _normalize_messages(messages),
            "stream": True,
            "think": False,
        }

        options: dict[str, Any] = {}
        for key, value in (extra_body or {}).items():
            if key in OLLAMA_OPTION_KEYS:
                options[key] = value
            else:
                payload[key] = value
        if options:
            payload["options"] = options

        try:
            response = self.client.session.post(
                f"{self.client.base_url}/api/chat",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=self.client.config.request_timeout,
                stream=True,
            )
        except requests.RequestException as exc:
            raise OllamaAPIError(f"本地 Ollama 没连上：{exc}") from exc

        if not response.ok:
            body = response.text[:500]
            message = _extract_error_message(response)
            raise OllamaAPIError(
                f"本地 Ollama 请求失败（{response.status_code}）：{message}",
                status_code=response.status_code,
                body=body,
            )

        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = data.get("message") or {}
            content = str(message.get("content", ""))
            if content:
                yield content


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for message in messages:
        item: dict[str, Any] = {
            "role": message.get("role", "user"),
            "content": message.get("content", ""),
        }
        if "images" in message:
            item["images"] = message["images"]
        if "tool_name" in message:
            item["tool_name"] = message["tool_name"]
        tool_calls = message.get("tool_calls")
        if tool_calls:
            item["tool_calls"] = _normalize_tool_calls(tool_calls)
        normalized.append(item)
    return normalized


def _normalize_tool_calls(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_calls: list[dict[str, Any]] = []
    for tool_call in tool_calls:
        function = tool_call.get("function", {})
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        normalized_calls.append(
            {
                "function": {
                    "name": function.get("name", ""),
                    "arguments": arguments,
                }
            }
        )
    return normalized_calls


def _normalize_response_message(message: dict[str, Any]) -> dict[str, Any]:
    normalized_tool_calls: list[dict[str, Any]] = []
    for index, tool_call in enumerate(message.get("tool_calls") or [], start=1):
        function = tool_call.get("function", {})
        normalized_tool_calls.append(
            {
                "id": tool_call.get("id", f"ollama_call_{index}"),
                "type": "function",
                "function": {
                    "name": function.get("name", ""),
                    "arguments": function.get("arguments", {}),
                },
            }
        )

    return {
        "role": message.get("role", "assistant"),
        "content": str(message.get("content", "")).strip(),
        "tool_calls": normalized_tool_calls,
    }


def _extract_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:200] or "本地模型没有返回可读错误信息"

    if isinstance(payload, dict):
        for key in ("error", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return response.text[:200] or "本地模型没有返回可读错误信息"
