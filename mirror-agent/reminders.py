from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import Callable
from uuid import uuid4


def _normalize_identity(text: str) -> str:
    return " ".join(str(text).split()).strip()


@dataclass
class Reminder:
    id: str
    message: str
    due_at: str
    due_at_ms: int
    source_text: str = ""


class ReminderScheduler:
    def __init__(self, now_func: Callable[[], datetime] | None = None) -> None:
        self._now_func = now_func or datetime.now
        self._lock = Lock()
        self._items: list[Reminder] = []

    def schedule_in_minutes(self, minutes: int, message: str, source_text: str = "") -> Reminder:
        minutes_value = max(int(minutes), 0)
        due_time = self._now_func() + timedelta(minutes=minutes_value)
        if due_time.microsecond and minutes_value > 0:
            due_time = due_time + timedelta(seconds=1)
        due_time = due_time.replace(microsecond=0)
        reminder = Reminder(
            id=uuid4().hex,
            message=str(message).strip() or "提醒时间到了哦。",
            due_at=due_time.isoformat(timespec="seconds"),
            due_at_ms=int(due_time.timestamp() * 1000),
            source_text=str(source_text).strip(),
        )
        with self._lock:
            self._items = [
                item
                for item in self._items
                if not self._matches_pending_identity(item, reminder)
            ]
            self._items.append(reminder)
        return reminder

    def pop_due(self) -> list[Reminder]:
        now_ms = int(self._now_func().timestamp() * 1000)
        due_items: list[Reminder] = []
        pending_items: list[Reminder] = []
        with self._lock:
            for item in self._items:
                if item.due_at_ms <= now_ms:
                    due_items.append(item)
                else:
                    pending_items.append(item)
            self._items = pending_items
        return due_items

    def _matches_pending_identity(self, existing: Reminder, incoming: Reminder) -> bool:
        existing_source = _normalize_identity(existing.source_text)
        incoming_source = _normalize_identity(incoming.source_text)
        if existing_source and incoming_source:
            return existing_source == incoming_source

        existing_message = _normalize_identity(existing.message)
        incoming_message = _normalize_identity(incoming.message)
        return bool(existing_message) and existing_message == incoming_message
