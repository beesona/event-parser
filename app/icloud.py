from datetime import datetime, timezone, tzinfo
from typing import List

import caldav
import icalendar
from caldav.lib.error import AuthorizationError, DAVError

from .config import Settings
from .models import CalendarEvent, SaveResult


class CalendarError(Exception):
    pass


def build_ical(event: CalendarEvent, tz: tzinfo) -> str:
    start, end = event.bounds(tz)

    vevent = icalendar.Event()
    vevent.add("uid", event.uid())
    vevent.add("dtstamp", datetime.now(timezone.utc))
    vevent.add("summary", event.title)
    vevent.add("dtstart", start)
    vevent.add("dtend", end)
    if event.location:
        vevent.add("location", event.location)
    if event.notes:
        vevent.add("description", event.notes)

    cal = icalendar.Calendar()
    cal.add("prodid", "-//event-control//EN")
    cal.add("version", "2.0")
    cal.add_component(vevent)
    cal.add_missing_timezones()
    return cal.to_ical().decode()


def _open_calendar(settings: Settings) -> caldav.Calendar:
    client = caldav.DAVClient(
        url=settings.caldav_url,
        username=settings.caldav_username,
        password=settings.caldav_password,
    )
    try:
        calendars = client.principal().calendars()
    except AuthorizationError as exc:
        raise CalendarError(
            f"iCloud rejected the login ({exc.reason}). Check CALDAV_USERNAME and that "
            "CALDAV_PASSWORD is an app-specific password. Run "
            "`.venv/bin/python -m scripts.check_icloud` for details."
        ) from exc
    except DAVError as exc:
        raise CalendarError(f"Could not reach the calendar server: {exc}") from exc

    wanted = settings.caldav_calendar.strip().casefold()
    for calendar in calendars:
        if (calendar.name or "").strip().casefold() == wanted:
            return calendar

    available = ", ".join(sorted(c.name or "(unnamed)" for c in calendars)) or "none"
    raise CalendarError(
        f"No calendar named {settings.caldav_calendar!r}. Available calendars: {available}"
    )


def save_events(events: List[CalendarEvent], settings: Settings) -> List[SaveResult]:
    calendar = _open_calendar(settings)
    results = []
    for event in events:
        try:
            calendar.save_event(ical=build_ical(event, settings.tz))
            results.append(SaveResult(title=event.title, start_date=event.start_date, ok=True))
        except DAVError as exc:
            results.append(
                SaveResult(
                    title=event.title, start_date=event.start_date, ok=False, error=str(exc)
                )
            )
    return results
