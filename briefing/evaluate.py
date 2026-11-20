"""Measure full-feed processing and the three local demo editions."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter, process_time

from .audio import synthesize
from .config import Settings
from .engine import assemble, load_catalog
from .ingest import import_feeds
from .models import BriefingRequest, PRESETS
from .storage import initialize


def measure(settings: Settings, include_audio: bool) -> dict:
    initialize(settings.database)
    start, cpu_start = perf_counter(), process_time()
    stats = import_feeds(settings.data_dir, settings.database)
    catalog = load_catalog(settings)
    wall, cpu = perf_counter() - start, process_time() - cpu_start
    if not stats["article_count"]:
        raise SystemExit("Mount the supplied JSONL feeds before running the evaluation.")
    database_bytes = settings.database.stat().st_size
    editions = {}
    for name, profile in PRESETS.items():
        start = perf_counter()
        briefing = assemble(settings, catalog, BriefingRequest(profile=profile, use_ai=False))
        edition = {
            "stories": [story.id for story in briefing.stories],
            "script_characters": len(briefing.script),
            "editor_wall_seconds": round(perf_counter() - start, 4),
        }
        if include_audio:
            start = perf_counter()
            asset = synthesize(settings, briefing, local=True)
            edition["audio_wall_seconds"] = round(perf_counter() - start, 3)
            edition["mp3_bytes"] = (settings.audio_dir / asset.filename).stat().st_size
        editions[name] = edition
    return {
        "full_dataset": {
            **stats, "reviewed_stories": len(catalog), "database_bytes": database_bytes,
            "ingest_and_review_wall_seconds": round(wall, 3),
            "ingest_and_review_cpu_seconds": round(cpu, 3),
            "metered_api_usd": 0,
        },
        "ten_times_volume_linear_estimate": {
            "article_count": 10 * stats["article_count"], "database_bytes": 10 * database_bytes,
            "ingest_and_review_wall_seconds": round(10 * wall, 3),
            "ingest_and_review_cpu_seconds": round(10 * cpu, 3),
            "metered_api_usd": 0,
        },
        "local_demo_editions": editions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", action="store_true", help="Measure local MP3 synthesis as well.")
    args = parser.parse_args()
    settings = Settings()
    with TemporaryDirectory(prefix="liquid-briefing-eval-") as state:
        settings.database = Path(state) / "briefing.sqlite3"
        settings.audio_dir = Path(state) / "audio"
        print(json.dumps(measure(settings, args.audio), indent=2))


if __name__ == "__main__":
    main()
