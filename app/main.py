import secrets
from pathlib import Path
from typing import Optional

import openai
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .config import Settings, get_settings
from .icloud import CalendarError, save_events
from .models import AddEventsRequest, AddEventsResponse, Extraction
from .parser import ExtractionError, extract_events

STATIC_DIR = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

app = FastAPI(title="event-control")


def require_passcode(
    x_passcode: Optional[str] = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if settings.app_passcode and not secrets.compare_digest(
        (x_passcode or "").encode(), settings.app_passcode.encode()
    ):
        raise HTTPException(status_code=401, detail="Wrong or missing passcode.")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config", dependencies=[Depends(require_passcode)])
def config(settings: Settings = Depends(get_settings)) -> dict:
    return {"calendar": settings.caldav_calendar, "timezone": settings.timezone}


@app.post("/api/parse", dependencies=[Depends(require_passcode)])
def parse(
    image: UploadFile = File(...),
    hint: str = Form(""),
    settings: Settings = Depends(get_settings),
) -> Extraction:
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported image type {image.content_type!r}. Use JPEG, PNG, WebP, or GIF.",
        )
    data = image.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image is larger than 20 MB.")

    try:
        return extract_events(data, image.content_type, hint, settings)
    except ExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except openai.OpenAIError as exc:
        raise HTTPException(status_code=502, detail=f"OpenAI request failed: {exc}") from exc


@app.post("/api/events", dependencies=[Depends(require_passcode)])
def add_events(
    body: AddEventsRequest, settings: Settings = Depends(get_settings)
) -> AddEventsResponse:
    try:
        results = save_events(body.events, settings)
    except CalendarError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return AddEventsResponse(calendar=settings.caldav_calendar, results=results)
