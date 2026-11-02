"""Diagnose iCloud CalDAV access using the same settings as the app.

Run from the project root:  .venv/bin/python -m scripts.check_icloud
"""

import re
import sys

import caldav
import httpx

from app.config import get_settings

PROPFIND_BODY = """<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:"><d:prop><d:current-user-principal/></d:prop></d:propfind>"""


def check_settings(settings) -> None:
    print("1. Settings loaded from .env / environment")
    username, password = settings.caldav_username, settings.caldav_password
    print(f"   CALDAV_URL       = {settings.caldav_url}")
    print(f"   CALDAV_USERNAME  = {username!r}")
    print(f"   CALDAV_PASSWORD  = {len(password)} chars, starts {password[:2]!r}...")
    if username != username.strip() or password != password.strip():
        print("   ! Leading/trailing whitespace in username or password")
    if any(q in username + password for q in "\"'"):
        print("   ! Quote characters are part of the value")
    if "@" not in username:
        print("   ! Username should be your full Apple ID email address")
    if not re.fullmatch(r"[a-z]{4}-?[a-z]{4}-?[a-z]{4}-?[a-z]{4}", password):
        print("   ! Password doesn't look like an app-specific password (xxxx-xxxx-xxxx-xxxx)")


def check_raw_login(settings) -> bool:
    print("\n2. Raw PROPFIND with Basic auth (bypasses the caldav library)")
    try:
        response = httpx.request(
            "PROPFIND",
            settings.caldav_url,
            auth=(settings.caldav_username, settings.caldav_password),
            headers={"Depth": "0", "Content-Type": "application/xml; charset=utf-8"},
            content=PROPFIND_BODY,
            timeout=20,
        )
    except httpx.HTTPError as exc:
        print(f"   ! Request failed: {exc!r}")
        return False

    print(f"   HTTP {response.status_code} {response.reason_phrase}")
    if response.status_code == 207:
        href = re.search(r"<href[^>]*>([^<]+)</href>", response.text.split("current-user-principal")[1])
        print(f"   Login OK. Principal: {href.group(1) if href else '(not found in response)'}")
        return True
    if response.status_code == 401:
        print("   Apple rejected these credentials.")
    else:
        print(f"   Unexpected response body:\n{response.text[:500]}")
    return False


def check_caldav_library(settings) -> None:
    print("\n3. caldav library (what the app uses)")
    client = caldav.DAVClient(
        url=settings.caldav_url,
        username=settings.caldav_username,
        password=settings.caldav_password,
    )
    try:
        calendars = client.principal().calendars()
    except Exception as exc:
        print(f"   ! {type(exc).__name__}: {exc}")
        return
    print(f"   Found {len(calendars)} calendars:")
    for calendar in calendars:
        marker = "  <- CALDAV_CALENDAR" if (calendar.name or "").strip().casefold() == settings.caldav_calendar.strip().casefold() else ""
        print(f"     - {calendar.name!r}{marker}")


def main() -> int:
    settings = get_settings()
    check_settings(settings)
    raw_ok = check_raw_login(settings)
    check_caldav_library(settings)
    return 0 if raw_ok else 1


if __name__ == "__main__":
    sys.exit(main())
