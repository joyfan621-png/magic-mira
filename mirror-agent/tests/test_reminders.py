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
            message="面膜时间到了，记得摘掉并轻轻按摩一下哦。",
            source_text="我刚敷上了面膜，15分钟后提醒我摘掉。",
        )

        self.assertEqual([], scheduler.pop_due())
        self.assertEqual("面膜时间到了，记得摘掉并轻轻按摩一下哦。", reminder.message)

        current_time = current_time + timedelta(minutes=15, seconds=1)
        due = scheduler.pop_due()

        self.assertEqual(1, len(due))
        self.assertEqual("面膜时间到了，记得摘掉并轻轻按摩一下哦。", due[0].message)
        self.assertEqual([], scheduler.pop_due())

    def test_schedule_in_minutes_replaces_existing_pending_reminder_with_same_message(self) -> None:
        current_time = datetime(2026, 4, 5, 12, 0, 0)

        def now() -> datetime:
            return current_time

        scheduler = ReminderScheduler(now_func=now)
        first = scheduler.schedule_in_minutes(
            minutes=1,
            message="面膜时间到了，记得摘掉并轻轻按摩一下哦。",
            source_text="1分钟后提醒我摘面膜",
        )

        current_time = current_time + timedelta(seconds=20)
        second = scheduler.schedule_in_minutes(
            minutes=1,
            message="面膜时间到了，记得摘掉并轻轻按摩一下哦。",
            source_text="1分钟后提醒我摘面膜",
        )

        self.assertNotEqual(first.id, second.id)

        current_time = current_time + timedelta(seconds=41)
        self.assertEqual([], scheduler.pop_due())

        current_time = current_time + timedelta(seconds=20)
        due = scheduler.pop_due()

        self.assertEqual(1, len(due))
        self.assertEqual(second.id, due[0].id)
        self.assertEqual([], scheduler.pop_due())
