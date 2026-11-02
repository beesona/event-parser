from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.icloud import build_ical
from app.models import CalendarEvent, Extraction

TZ = ZoneInfo("America/Denver")


def test_all_day_event_has_exclusive_end_date():
    event = CalendarEvent(title="Tournament", start_date="2026-06-03", end_date="2026-06-05")
    assert event.all_day
    assert event.bounds(TZ) == (date(2026, 6, 3), date(2026, 6, 6))


def test_missing_start_time_means_all_day():
    event = CalendarEvent(title="Bake sale", start_date="2026-11-15", end_time="15:00")
    assert event.all_day
    assert event.end_time is None


def test_timed_event_without_end_defaults_to_one_hour():
    event = CalendarEvent(title="Game", start_date="2026-11-15", start_time="18:00")
    start, end = event.bounds(TZ)
    assert start == datetime(2026, 11, 15, 18, 0, tzinfo=TZ)
    assert end - start == timedelta(hours=1)


def test_end_time_before_start_time_rolls_past_midnight():
    event = CalendarEvent(
        title="Late show", start_date="2026-11-15", start_time="22:00", end_time="01:00"
    )
    _, end = event.bounds(TZ)
    assert end == datetime(2026, 11, 16, 1, 0, tzinfo=TZ)


def test_end_before_start_is_rejected():
    with pytest.raises(ValidationError, match="end must be after start"):
        CalendarEvent(title="Oops", start_date="2026-06-05", end_date="2026-06-03")


def test_blank_strings_become_none():
    event = CalendarEvent(title="  Dinner ", start_date="2026-11-15", location="  ", notes="")
    assert event.title == "Dinner"
    assert event.location is None
    assert event.notes is None


def test_uid_is_stable_and_distinguishes_times():
    a = CalendarEvent(title="Game", start_date="2026-11-15", start_time="10:00")
    b = CalendarEvent(title="game", start_date="2026-11-15", start_time="10:00", location="Park")
    c = CalendarEvent(title="Game", start_date="2026-11-15", start_time="14:00")
    assert a.uid() == b.uid()
    assert a.uid() != c.uid()


def test_build_ical_timed_event():
    event = CalendarEvent(
        title="Game night",
        start_date="2026-11-15",
        start_time="18:00",
        end_time="21:00",
        location="Erin's place",
        notes="Bring snacks",
    )
    ical = build_ical(event, TZ)
    assert f"UID:{event.uid()}" in ical
    assert "SUMMARY:Game night" in ical
    assert "DTSTART;TZID=America/Denver:20261115T180000" in ical
    assert "DTEND;TZID=America/Denver:20261115T210000" in ical
    assert "LOCATION:Erin's place" in ical
    assert "DESCRIPTION:Bring snacks" in ical
    assert "BEGIN:VTIMEZONE" in ical


def test_build_ical_all_day_event():
    event = CalendarEvent(title="Camping", start_date="2026-07-10", end_date="2026-07-12")
    ical = build_ical(event, TZ)
    assert "DTSTART;VALUE=DATE:20260710" in ical
    assert "DTEND;VALUE=DATE:20260713" in ical


def test_extraction_schema_is_strict_compatible():
    from openai.lib._pydantic import to_strict_json_schema

    schema = to_strict_json_schema(Extraction)
    event_schema = schema["$defs"]["ExtractedEvent"]
    assert set(event_schema["required"]) == set(event_schema["properties"])
    assert event_schema["additionalProperties"] is False
