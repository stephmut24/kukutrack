from datetime import date

from app.services.calendar import generate_reminder_drafts


def test_calendar_generation_uses_schedule_offsets() -> None:
    reminders = generate_reminder_drafts(date(2026, 1, 1))

    assert len(reminders) == 41
    assert reminders[0].due_date == date(2026, 1, 1)
    assert reminders[13].due_date == date(2026, 1, 14)
    assert reminders[14].category == "vaccine"
    assert reminders[14].due_date == date(2026, 1, 8)
    assert reminders[-1].due_date == date(2026, 2, 26)
