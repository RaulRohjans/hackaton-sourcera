from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from .audio import AudioError, synthesize
from .config import PACKAGE, Settings
from .engine import assemble, load_catalog
from .ingest import import_feeds
from .models import Briefing, BriefingRequest, PRESETS, REPLAY
from .storage import connect, initialize


def load_data(settings: Settings):
    initialize(settings.database)
    stats = import_feeds(settings.data_dir, settings.database)
    return stats, load_catalog(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    app.state.settings = settings
    app.state.stats, app.state.catalog = await run_in_threadpool(load_data, settings)
    yield


app = FastAPI(
    title="The Liquid Briefing", version="1.0.0", lifespan=lifespan,
    description="Generate a personalized audio edition from the reviewed Sourcera replay.",
)
app.mount("/static", StaticFiles(directory=PACKAGE / "static"), name="static")
templates = Jinja2Templates(directory=PACKAGE / "templates")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def studio(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={
        "presets": {key: profile.model_dump() for key, profile in PRESETS.items()},
        "default_profile": PRESETS["fx"],
        "replay_date": REPLAY.strftime("%d %B %Y"),
    })


@app.get("/healthz", include_in_schema=False)
def health():
    return {"status": "ok"}


@app.get("/api/replay")
def replay():
    return {
        **app.state.stats,
        "stories": len(app.state.catalog),
        "as_of": REPLAY,
        "presets": PRESETS,
        "audio_provider": "elevenlabs" if app.state.settings.elevenlabs_key else "local",
        "openai_enabled": bool(app.state.settings.openai_key),
    }


def saved_briefing(briefing_id: UUID) -> Briefing:
    with connect(app.state.settings.database) as db:
        row = db.execute("SELECT payload FROM briefings WHERE id = ?", (briefing_id.hex,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Briefing not found.")
    return Briefing.model_validate_json(row["payload"])


@app.post("/api/briefings", response_model=Briefing, status_code=201)
def create_briefing(options: BriefingRequest):
    settings = app.state.settings
    briefing = assemble(settings, app.state.catalog, options)
    with connect(settings.database) as db:
        db.execute("INSERT INTO briefings VALUES (?, ?)", (briefing.id, briefing.model_dump_json()))
    return briefing


@app.get("/api/briefings/{briefing_id}", response_model=Briefing)
def get_briefing(briefing_id: UUID):
    return saved_briefing(briefing_id)


@app.get("/api/briefings/{briefing_id}/message", response_class=PlainTextResponse)
def get_message(briefing_id: UUID, download: bool = False):
    briefing = saved_briefing(briefing_id)
    language = briefing.profile.language
    replay_label, voice_label = {
        "en": ("Historical replay", "Synthetic narration"),
        "nl": ("Historische editie", "Synthetische vertelstem"),
        "de": ("Historische Ausgabe", "Synthetische Sprecherstimme"),
    }[language]
    message = ["The Liquid Briefing", f"{replay_label} · {briefing.as_of:%Y-%m-%d} UTC · {voice_label}"]
    for story in briefing.stories:
        message.extend(("", story.title, story.summary))
        sources = {source.id: source for claim in story.claims for source in claim.sources}
        for source in sources.values():
            message.append(f"{source.publisher} ({source.published_at:%Y-%m-%d}) · {source.url}")
    if not briefing.stories:
        message.extend(("", briefing.notice or ""))
    headers = {"Content-Disposition": 'attachment; filename="liquid-briefing.txt"'} if download else {}
    return PlainTextResponse("\n".join(message) + "\n", headers=headers)


@app.post("/api/briefings/{briefing_id}/audio")
def generate_audio(briefing_id: UUID, local: bool = False):
    briefing = saved_briefing(briefing_id)
    settings = app.state.settings
    try:
        asset = synthesize(settings, briefing, local)
    except AudioError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    with connect(settings.database) as db:
        db.execute(
            "INSERT OR REPLACE INTO audio (briefing_id, filename, provider) VALUES (?, ?, ?)",
            (briefing_id.hex, asset.filename, asset.provider),
        )
    return {"url": f"/api/briefings/{briefing_id.hex}/audio", "provider": asset.provider}


@app.get("/api/briefings/{briefing_id}/audio", response_class=FileResponse)
def get_audio(briefing_id: UUID, download: bool = False):
    settings = app.state.settings
    with connect(settings.database) as db:
        row = db.execute("SELECT filename FROM audio WHERE briefing_id = ?", (briefing_id.hex,)).fetchone()
    if row is None:
        raise HTTPException(404, "Generate audio for this briefing first.")
    path = settings.audio_dir / row["filename"]
    if not path.is_file():
        raise HTTPException(404, "Cached audio is missing. Generate it again.")
    filename = f"liquid-briefing-{briefing_id.hex[:8]}.mp3" if download else "liquid-briefing.mp3"
    return FileResponse(path, media_type="audio/mpeg", filename=filename,
                        content_disposition_type="attachment" if download else "inline")
