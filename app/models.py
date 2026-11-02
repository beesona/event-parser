import hashlib
from datetime import date, datetime, time, timedelta, tzinfo
from typing import List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field, field_validator, model_validator

DEFAULT_EVENT_DURATION = timedelta(hours=1)


class ExtractedEvent(BaseModel):
    """One event as read by the LLM.

    OpenAI strict structured outputs require every field to be present, so
    unknown values are expressed as null rather than omitted.
    """

    title: str = Field(description="Short event name, keeping the original wording")
    start_date: str = Field(description="YYYY-MM-DD")
    start_time: Optional[str] = Field(description="24-hour HH:MM, or null if no time is given")
    end_date: Optional[str] = Field(
        description="YYYY-MM-DD, inclusive. Only for events spanning multiple days; otherwise null"
    )
    end_time: Optional[str] = Field(description="24-hour HH:MM, or null if no end time is given")
    all_day: bool = Field(description="True when no time of day is given")
    location: Optional[str]
    notes: Optional[str] = Field(description="Extra details from the image that don't fit the title")
    confidence: Literal["high", "medium", "low"] = Field(
        description="How sure you are that the date, time, and title were read correctly"
    )
    source_text: str = Field(description="The text exactly as it appears in the image for this event")


class Extraction(BaseModel):
    events: List[ExtractedEvent]
    warnings: List[str] = Field(
        description="Things the user should double-check, such as unreadable text or an assumed year"
    )


class CalendarEvent(BaseModel):
    """An event the user has reviewed and wants written to the calendar."""

    title: str = Field(min_length=1, max_length=255)
    start_date: date
    start_time: Optional[time] = None
    end_date: Optional[date] = None
    end_time: Optional[time] = None
    all_day: bool = False
    location: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("title", "location", "notes", mode="before")
    @classmethod
    def _strip(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def _normalize(self) -> "CalendarEvent":
        if self.start_time is None:
            self.all_day = True
        if self.all_day:
            self.start_time = None
            self.end_time = None
        start, end = self.bounds()
        if end <= start:
            raise ValueError("end must be after start")
        return self

    def bounds(
        self, tz: Optional[tzinfo] = None
    ) -> Tuple[Union[date, datetime], Union[date, datetime]]:
        """Start and end as iCalendar expects them: dates with an exclusive end
        for all-day events, timezone-aware datetimes otherwise."""
        if self.all_day:
            last_day = self.end_date or self.start_date
            return self.start_date, last_day + timedelta(days=1)

        start = datetime.combine(self.start_date, self.start_time, tzinfo=tz)
        if self.end_time is None:
            return start, start + DEFAULT_EVENT_DURATION

        end = datetime.combine(self.end_date or self.start_date, self.end_time, tzinfo=tz)
        if self.end_date is None and end <= start:
            end += timedelta(days=1)  # e.g. 22:00-01:00
        return start, end

    def uid(self) -> str:
        """Stable ID so re-submitting the same event overwrites it instead of duplicating."""
        start_time = self.start_time.isoformat("minutes") if self.start_time else ""
        key = "|".join([self.title.casefold(), self.start_date.isoformat(), start_time])
        return hashlib.sha256(key.encode()).hexdigest()[:32] + "@event-control"


class AddEventsRequest(BaseModel):
    events: List[CalendarEvent] = Field(min_length=1, max_length=200)


class SaveResult(BaseModel):
    title: str
    start_date: date
    ok: bool
    error: Optional[str] = None


class AddEventsResponse(BaseModel):
    calendar: str
    results: List[SaveResult]
