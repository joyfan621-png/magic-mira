from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import Callable
from uuid import uuid4


@dataclass
class Reminder:
    id: str
    message: str
    due_at: str
    source_text: str = ""


class ReminderScheduler:
    def __init__(self, now_func: Callable[[], datetime] | None = None) -> None:
        self._now_func = now_func or datetime.now
        self._lock = Lock()
        self._items: list[Reminder] = []

    def schedule_in_minutes(self, minutes: int, message: str, source_text: str = "") -> Reminder:
        due_time = self._now_func() + timedelta(minutes=max(int(minutes), 0))
        reminder = Reminder(
            id=uuid4().hex,
            message=str(message).strip() or "提醒时间到了哦。",
            due_at=due_time.isoformat(),
            source_text=str(source_text).strip(),
        )
        with self._lock:
            self._items.append(reminder)
        return reminder

    def pop_due(self) -> list[Reminder]:
        now = self._now_func()
        due_items: list[Reminder] = []
        pending_items: list[Reminder] = []
        with self._lock:
            for item in self._items:
                if datetime.fromisoformat(item.due_at) <= now:
                    due_items.append(item)
                else:
                    pending_items.append(item)
            self._items = pending_items
        return due_items
