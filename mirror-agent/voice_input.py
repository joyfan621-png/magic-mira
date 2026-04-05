from __future__ import annotations

import math
import tempfile
import wave
from collections import deque
from pathlib import Path
from typing import Any, Callable


DEFAULT_WAKE_WORD = "小镜"


def extract_wake_text(text: str, wake_word: str = DEFAULT_WAKE_WORD) -> str | None:
    normalized = text.strip()
    if not wake_word:
        return normalized
    if wake_word not in normalized:
        return None
    _, remainder = normalized.split(wake_word, 1)
    return remainder.strip()


def save_wav_file(
    output_path: str | Path,
    frames: list[bytes],
    sample_rate: int,
    channels: int,
    sample_width: int,
) -> Path:
    path = Path(output_path)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"".join(frames))
    return path


def transcribe_audio_file(
    audio_path: str | Path,
    whisper_model_name: str = "base",
    whisper_loader: Callable[[str], Any] | None = None,
) -> str:
    loader = whisper_loader or _load_whisper_model
    model = loader(whisper_model_name)
    result = model.transcribe(str(audio_path), language="zh")
    return str(result.get("text", "")).strip()


class VoiceInput:
    def __init__(
        self,
        wake_word: str = DEFAULT_WAKE_WORD,
        whisper_model_name: str = "base",
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1024,
        energy_threshold: int = 900,
        silence_seconds: float = 1.2,
        max_record_seconds: float = 10.0,
        whisper_loader: Callable[[str], Any] | None = None,
        pyaudio_module: Any | None = None,
    ) -> None:
        self.wake_word = wake_word
        self.whisper_model_name = whisper_model_name
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.energy_threshold = energy_threshold
        self.silence_seconds = silence_seconds
        self.max_record_seconds = max_record_seconds
        self._whisper_loader = whisper_loader
        self._pyaudio_module = pyaudio_module
        self._model: Any | None = None

    def listen_for_prompt(self) -> str:
        while True:
            wav_path = self.capture_utterance()
            if wav_path is None:
                continue

            transcript = self.transcribe(wav_path)
            try:
                wav_path.unlink(missing_ok=True)
            except OSError:
                pass

            prompt = extract_wake_text(transcript, self.wake_word)
            if prompt is None:
                continue
            return prompt

    def capture_utterance(self) -> Path | None:
        pyaudio = self._get_pyaudio_module()
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )

        frames: list[bytes] = []
        pre_roll = deque(maxlen=max(1, int(self.sample_rate / self.chunk_size * 0.5)))
        speech_started = False
        silent_chunks = 0
        max_chunks = max(1, int(self.sample_rate / self.chunk_size * self.max_record_seconds))
        silence_limit = max(1, int(self.sample_rate / self.chunk_size * self.silence_seconds))

        try:
            for _ in range(max_chunks):
                chunk = stream.read(self.chunk_size, exception_on_overflow=False)
                energy = chunk_energy(chunk)
                if not speech_started:
                    pre_roll.append(chunk)
                    if energy >= self.energy_threshold:
                        speech_started = True
                        frames.extend(pre_roll)
                        silent_chunks = 0
                    continue

                frames.append(chunk)
                if energy < self.energy_threshold:
                    silent_chunks += 1
                    if silent_chunks >= silence_limit:
                        break
                else:
                    silent_chunks = 0
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()

        if not frames:
            return None

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            return save_wav_file(
                temp_file.name,
                frames=frames,
                sample_rate=self.sample_rate,
                channels=self.channels,
                sample_width=audio.get_sample_size(pyaudio.paInt16),
            )

    def transcribe(self, wav_path: str | Path) -> str:
        result = self._get_model().transcribe(str(wav_path), language="zh")
        return str(result.get("text", "")).strip()

    def _get_model(self) -> Any:
        if self._model is None:
            loader = self._whisper_loader or _load_whisper_model
            self._model = loader(self.whisper_model_name)
        return self._model

    def _get_pyaudio_module(self) -> Any:
        if self._pyaudio_module is None:
            self._pyaudio_module = _import_pyaudio()
        return self._pyaudio_module


def chunk_energy(chunk: bytes) -> int:
    if not chunk:
        return 0
    sample_count = len(chunk) // 2
    if sample_count == 0:
        return 0

    total = 0
    for index in range(0, len(chunk), 2):
        sample = int.from_bytes(chunk[index : index + 2], byteorder="little", signed=True)
        total += sample * sample
    return int(math.sqrt(total / sample_count))


def _load_whisper_model(model_name: str) -> Any:
    import whisper

    return whisper.load_model(model_name)


def _import_pyaudio() -> Any:
    import pyaudio

    return pyaudio
