import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from reminders import ReminderScheduler


class ReminderSchedulerTests(unittest.TestCase):
    def test_schedule_in_minutes_and_pop_due_returns_ready_items(self) -> None:
        current_time = datetime(2026, 4, 5, 12, 0, 0)

        def now() -> datetime:
            return current_time

        scheduler = ReminderScheduler(now_func=now)
        reminder = scheduler.schedule_in_minutes(
            minutes=15,
            message="面膜时间到了，记得摘掉哦。",
            source_text="我刚敷上了面膜，15分钟后提醒我摘掉。",
        )

        self.assertEqual([], scheduler.pop_due())
        self.assertEqual("面膜时间到了，记得摘掉哦。", reminder.message)

        current_time = current_time + timedelta(minutes=15, seconds=1)
        due = scheduler.pop_due()

        self.assertEqual(1, len(due))
        self.assertEqual("面膜时间到了，记得摘掉哦。", due[0].message)
        self.assertEqual([], scheduler.pop_due())
