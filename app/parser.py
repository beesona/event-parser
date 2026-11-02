import base64
from datetime import datetime

from openai import OpenAI

from .config import Settings
from .models import Extraction

INSTRUCTIONS = """\
You extract calendar events from photos of printed calendars, schedules, flyers, \
and handwritten lists of dates.

Today is {today} and the user's timezone is {timezone}.

Rules:
- Return one entry per occurrence. Expand recurring entries such as "every Tuesday in \
March" into one event per date, but only when the dates are unambiguous; otherwise \
add a warning instead of guessing.
- An event spanning several days (e.g. "Jun 3-5 tournament") is a single entry with \
an end_date.
- If the year is shown anywhere (title, month header), use it. Otherwise choose the \
year that puts the date closest to today, and add a warning saying which year you assumed.
- Times are 24-hour HH:MM. "7pm" is 19:00. If no time is given, set all_day to true \
and leave start_time and end_time null.
- Ignore holidays, moon phases, and other decorations pre-printed by the calendar \
template, unless the user's context says otherwise.
- Never invent events. If text is partly unreadable, give your best reading, set \
confidence to low, and explain in warnings.
- Keep titles short; put any extra detail in notes.
"""


class ExtractionError(Exception):
    pass


def extract_events(
    image: bytes, mime_type: str, hint: str, settings: Settings
) -> Extraction:
    client = OpenAI(api_key=settings.openai_api_key)
    today = datetime.now(settings.tz).strftime("%A, %B %-d, %Y")

    prompt = "Extract every event from this image."
    if hint.strip():
        prompt += f"\n\nContext from the user: {hint.strip()}"

    data_url = f"data:{mime_type};base64,{base64.b64encode(image).decode()}"
    response = client.responses.parse(
        model=settings.openai_model,
        instructions=INSTRUCTIONS.format(today=today, timezone=settings.timezone),
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url, "detail": "high"},
                ],
            }
        ],
        text_format=Extraction,
    )

    if response.output_parsed is None:
        raise ExtractionError("The model did not return any structured events.")
    return response.output_parsed
