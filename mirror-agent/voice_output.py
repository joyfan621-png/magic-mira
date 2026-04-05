from __future__ import annotations

import asyncio
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable


def sanitize_speech_text(text: str) -> str:
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""

    normalized = re.sub(r"```.*?```", " ", normalized, flags=re.DOTALL)
    normalized = re.sub(r"`([^`]*)`", r"\1", normalized)
    normalized = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", normalized)
    normalized = re.sub(r"(\*\*|__|\*|_|~~)", "", normalized)

    cleaned_lines: list[str] = []
    for raw_line in normalized.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        is_heading = bool(re.match(r"^#{1,6}\s+", line))
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^\s*[-*+•]\s+", "", line)
        line = re.sub(r"^\s*\d+[.)、]\s*", "", line)
        line = line.strip()
        if not line:
            continue
        if is_heading:
            continue
        cleaned_lines.append(line)

    if not cleaned_lines:
        fallback = re.sub(r"\s+", " ", normalized).strip()
        return fallback

    spoken = "".join(
        line if line.endswith(("。", "！", "？", "!", "?")) else f"{line}。"
        for line in cleaned_lines
    )
    spoken = re.sub(r"\s+", " ", spoken).strip()
    spoken = re.sub(r"[，。！？!?]{2,}", lambda match: match.group(0)[0], spoken)
    return spoken


class VoiceOutput:
    def __init__(
        self,
        voice: str = "zh-CN-XiaoyiNeural",
        temp_dir: str | Path | None = None,
        communicate_factory: Callable[[str, str], Any] | None = None,
        player_command: list[str] | None = None,
    ) -> None:
        self.voice = voice
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir())
        self._communicate_factory = communicate_factory
        self.player_command = player_command or ["afplay"]

    def speak(self, text: str) -> Path:
        audio_path = asyncio.run(self.generate_audio_file(text))
        subprocess.run([*self.player_command, str(audio_path)], check=False)
        return audio_path

    async def generate_audio_file(self, text: str) -> Path:
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False, dir=self.temp_dir) as temp_file:
            output_path = Path(temp_file.name)

        communicate_cls = self._communicate_factory or _import_edge_tts_communicate()
        spoken_text = sanitize_speech_text(text) or str(text).strip() or "嗯。"
        communicator = communicate_cls(spoken_text, self.voice)
        await communicator.save(str(output_path))
        return output_path


def _import_edge_tts_communicate() -> Any:
    from edge_tts import Communicate

    return Communicate
