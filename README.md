# event-control

Turn a photo of dates into events on a shared iCloud calendar.

Take a picture of a printed calendar, a schedule, a flyer, or a handwritten list of dates. An OpenAI vision model reads the events from it, you review and correct them on a mobile-friendly page, and the app writes them to an iCloud calendar over CalDAV. That calendar can be one you share with friends.

## How it works

1. **Upload.** The web page takes or chooses a photo. The browser shrinks it and converts iPhone HEIC photos to JPEG before uploading. You can add optional context, such as "soccer games for Maya's team, all at Lincoln Park."
2. **Parse.** The server sends the image to OpenAI with a strict JSON schema (structured outputs), so the response is always a well-formed list of events. The prompt includes today's date and your timezone so the model can fill in missing years. Each event comes back with the text it was read from and a high, medium, or low confidence rating, plus warnings about anything ambiguous.
3. **Review.** Each event is an editable card. You can fix titles, dates, and times, mark events as all-day, untick or remove events, or add ones the model missed.
4. **Save.** The app writes the selected events to the configured iCloud calendar. Each event's ID comes from its title, date, and start time, so if you submit the same photo twice the events are updated rather than duplicated.

Event rules:

- An event with no start time is saved as all-day.
- A timed event with no end time lasts one hour.
- An end time earlier than the start time (for example 22:00–01:00) is treated as ending the next day.
- A multi-day event uses an inclusive end date: June 3–5 covers all three days.

## Requirements

- Python 3.9 or newer
- An [OpenAI API key](https://platform.openai.com/api-keys)
- An Apple Account with access to the calendar, plus an **app-specific password** for it (see below)

### Getting an iCloud app-specific password

iCloud's calendar server won't accept your normal Apple Account password from third-party apps. Instead:

1. Sign in at [account.apple.com](https://account.apple.com).
2. Go to **Sign-In and Security**, then **App-Specific Passwords**, and generate one (for example, named "event-control").
3. Copy it exactly. It's 16 lowercase letters, shown as `abcd-efgh-ijkl-mnop`.

The username must be your **primary** Apple Account email. That's the address shown under your name in iPhone **Settings**, which isn't always your `@icloud.com` address.

An app-specific password can read and write your iCloud mail, contacts, and calendars, so keep `.env` private. You can revoke the password at any time from the same page.

## Setup

```bash
git clone <this repo> event-control
cd event-control

python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

cp .env.example .env
```

Then edit `.env`:

| Variable | Required | Description |
| --- | --- | --- |
| `OPENAI_API_KEY` | yes | Your OpenAI API key. |
| `OPENAI_MODEL` | no | Vision model for parsing. Defaults to `gpt-5.4`. `gpt-5.4-mini` is cheaper. |
| `CALDAV_URL` | no | Defaults to `https://caldav.icloud.com/`. |
| `CALDAV_USERNAME` | yes | Your primary Apple Account email. |
| `CALDAV_PASSWORD` | yes | The app-specific password. |
| `CALDAV_CALENDAR` | yes | Calendar name exactly as it appears in the Calendar app (case-insensitive). |
| `TIMEZONE` | no | IANA timezone for timed events, such as `America/Denver`. Defaults to `America/Denver`. |
| `APP_PASSCODE` | no | If set, the web page asks for this passcode before parsing or saving. Set it before sharing the app. |

Before running the app, check that the iCloud settings work:

```bash
.venv/bin/python -m scripts.check_icloud
```

The script prints the settings it loaded (never the password itself). It then tries to log in directly and through the CalDAV library, and lists every calendar your account can see, marking the one named in `CALDAV_CALENDAR`. When the raw login step shows `HTTP 207` and your calendar is marked, you're ready.

## Running

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- On the same computer, open <http://localhost:8000>.
- On your phone, connect to the same Wi-Fi and open `http://<your-computer's-LAN-IP>:8000`. On macOS, `ipconfig getifaddr en0` prints the LAN IP.

Settings are read once at startup, so **restart the server after editing `.env`**. During development, add `--reload` to restart automatically when code changes.

To let friends use it from outside your network, host it (for example on Fly.io, Render, or a small VPS) or expose it through a tunnel such as Tailscale or Cloudflare Tunnel. Always set `APP_PASSCODE` first, because anyone who can reach the page can otherwise write to your calendar.

## Testing

Run the unit tests:

```bash
.venv/bin/python -m pytest
```

The tests in `tests/test_events.py` cover the event rules: all-day and multi-day end dates, default durations, events past midnight, validation, stable event IDs, and the generated iCalendar output. They also check that the parsing schema meets OpenAI's strict structured-output requirements. They don't call OpenAI or iCloud.

To check end to end:

1. Run `.venv/bin/python -m scripts.check_icloud` to confirm calendar access.
2. Start the server and open the page.
3. Upload a photo of a few dates. Check that the parsed events, confidence badges, and warnings make sense.
4. Add the events, then confirm they appear in the Calendar app. It may take a moment to sync.
5. Submit the same events again and confirm they're updated rather than duplicated.

You can also exercise the API directly:

```bash
# Parse an image (add -H "X-Passcode: ..." if APP_PASSCODE is set)
curl -F "image=@schedule.jpg;type=image/jpeg" -F "hint=Soccer games" \
  http://localhost:8000/api/parse

# Add an event
curl -H "Content-Type: application/json" \
  -d '{"events":[{"title":"Game night","start_date":"2026-11-15","start_time":"18:00","end_time":"21:00"}]}' \
  http://localhost:8000/api/events
```

FastAPI's interactive API docs are at <http://localhost:8000/docs>.

## Troubleshooting

**"iCloud rejected the login (Unauthorized)"**: Run `.venv/bin/python -m scripts.check_icloud`. Common causes:

- `CALDAV_PASSWORD` is your normal Apple Account password instead of an app-specific password.
- `CALDAV_USERNAME` is an alias, such as your `@icloud.com` address, rather than your primary Apple Account email.
- The app-specific password was generated on a different Apple Account.
- The password is brand new. Wait a couple of minutes, and paste it rather than typing it.
- You edited `.env` but didn't restart the server.

**"No calendar named ..."**: The error lists the calendars the account can see. Copy the exact name into `CALDAV_CALENDAR`. A calendar someone else shared with you only appears after you've accepted the invitation, and you can only add events if they gave you edit access.

**"OpenAI request failed"**: Check `OPENAI_API_KEY`, that your OpenAI account has billing enabled, and that `OPENAI_MODEL` is a vision-capable model your key can use.

**Parsed dates are wrong**: Add context in the hint box, such as "These are all in March 2027" or "Ignore the printed holidays." Then fix anything remaining on the review screen before saving.

## Project layout

```
app/
  main.py         FastAPI routes: page, /api/config, /api/parse, /api/events
  parser.py       OpenAI vision call and extraction prompt
  models.py       Extraction schema, reviewed-event model, date rules, event IDs
  icloud.py       CalDAV connection and iCalendar generation
  config.py       Settings loaded from .env
  static/
    index.html    Single-page mobile UI (no build step)
scripts/
  check_icloud.py iCloud credential and calendar diagnostics
tests/
  test_events.py  Unit tests
```

## Limitations

- The app only creates and updates events. It doesn't list or delete existing ones.
- iCloud's CalDAV server works reliably but isn't officially documented for developers by Apple, and has no published rate limits.
