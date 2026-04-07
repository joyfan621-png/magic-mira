from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_API_KEY = "QC-ec54458ab82f7ed7f5fb12e483b4a328-a9a066909083ee6ac2b5c67e3db89d20"
DEFAULT_PROVIDER = "ollama"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "gemma4:e2b"
DEFAULT_AIPING_BASE_URL = "https://aiping.cn/api/v1/chat/completions"


@dataclass
class AppConfig:
    project_root: Path
    provider: str = DEFAULT_PROVIDER
    api_key: str = DEFAULT_API_KEY
    chat_model: str = DEFAULT_OLLAMA_MODEL
    vision_model: str = DEFAULT_OLLAMA_MODEL
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    request_timeout: int = 120

    def __post_init__(self) -> None:
        self.project_root = Path(self.project_root).resolve()
        self.provider = (self.provider or DEFAULT_PROVIDER).strip().lower()
        if self.provider not in {"ollama", "aiping"}:
            self.provider = DEFAULT_PROVIDER

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> "AppConfig":
        root = Path(project_root or Path(__file__).resolve().parent)
        provider = os.getenv("MIRROR_AGENT_PROVIDER", os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER)).strip().lower()
        if provider not in {"ollama", "aiping"}:
            provider = DEFAULT_PROVIDER

        if provider == "ollama":
            chat_model = os.getenv("OLLAMA_CHAT_MODEL", os.getenv("MIRROR_AGENT_CHAT_MODEL", DEFAULT_OLLAMA_MODEL))
            vision_model = os.getenv("OLLAMA_VISION_MODEL", os.getenv("MIRROR_AGENT_VISION_MODEL", chat_model))
            return cls(
                project_root=root,
                provider=provider,
                api_key=os.getenv("OLLAMA_API_KEY", ""),
                chat_model=chat_model,
                vision_model=vision_model,
                base_url=os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
                request_timeout=int(os.getenv("OLLAMA_REQUEST_TIMEOUT", "120")),
            )

        return cls(
            project_root=root,
            provider=provider,
            api_key=os.getenv("AIPING_API_KEY", os.getenv("ZHIPUAI_API_KEY", DEFAULT_API_KEY)),
            chat_model=os.getenv("AIPING_CHAT_MODEL", os.getenv("ZHIPUAI_CHAT_MODEL", "GLM-5")),
            vision_model=os.getenv(
                "AIPING_VISION_MODEL",
                os.getenv("ZHIPUAI_VISION_MODEL", "Doubao-Seed-2.0-pro"),
            ),
            base_url=os.getenv("AIPING_BASE_URL", DEFAULT_AIPING_BASE_URL),
            request_timeout=int(os.getenv("AIPING_REQUEST_TIMEOUT", "60")),
        )

    @property
    def api_key_configured(self) -> bool:
        if self.provider == "ollama":
            return True
        return bool(self.api_key)

    @property
    def soul_path(self) -> Path:
        return self.project_root / "soul.md"

    @property
    def memory_dir(self) -> Path:
        return self.project_root / "memory"

    @property
    def profile_path(self) -> Path:
        return self.memory_dir / "profile.md"

    @property
    def insights_path(self) -> Path:
        return self.memory_dir / "insights.md"

    @property
    def diary_dir(self) -> Path:
        return self.memory_dir / "diary"

    @property
    def knowledge_dir(self) -> Path:
        return self.project_root / "knowledge"

    @property
    def knowledge_path(self) -> Path:
        return self.knowledge_dir / "skincare.md"
