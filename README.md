# The Liquid Briefing

A local newsroom demo for Sourcera. Generate an audio briefing and a separate short read from the same historical news edition. Open a story’s transcript to see the sources for each spoken claim.

## Run it

With Docker Desktop running and the supplied JSONL files in `liquid-briefing-data/`:

```sh
docker compose up --build
```

Open [the briefing studio](http://localhost:8000/) or [the API docs](http://localhost:8000/docs). The container imports the mounted feeds at startup, persists its results in SQLite, and can generate English and Dutch MP3s using its bundled local speech engine.

To use the hosted providers, copy `.env.example` to `.env` and set either or both keys. Recreate the container after changing `.env`.

| Setting | What it enables |
| --- | --- |
| `OPENAI_API_KEY` | Uses Structured Outputs to choose and order approved stories and fact IDs. `OPENAI_MODEL` defaults to `gpt-5.4-mini`. |
| `ELEVENLABS_API_KEY` | Synthesizes audio with Eleven v4 and exports a 128 kbps MP3. The four optional voice settings let you select voice IDs for each language and voice choice. |

The local editor works without OpenAI. The browser offers local narration if ElevenLabs fails. Local speech uses system voices on macOS and eSpeak NG in Docker. Available macOS voices depend on which voices are installed.

ElevenLabs runs when audio is requested. Identical scripts, voices, model settings and output formats share the same cached MP3 across briefings, playback and downloads. For bulk editions where lower cost matters, set `ELEVENLABS_MODEL=eleven_v4_turbo`. [ElevenLabs API pricing](https://elevenlabs.io/pricing/api)

### Run from Python

Use Python 3.10 or later. For local MP3s, install LAME or FFmpeg and use either macOS speech or eSpeak NG.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn briefing.app:app
```

Use `.venv/bin/python -m briefing.ingest --force` to rerun ingestion. Restart the app to reload the reviewed story catalog. `BRIEFING_DATA_DIR` and `BRIEFING_STATE_DIR` override the default input folder and `.runtime/` state directory.

## Five-minute demo

1. Click **Run U.S. producer-price story** for the one-story replay on 18 November 2026. Open **Transcript & sources** to verify the 0.3% monthly figure, 0.4% forecast and 6.5% annual figure in the linked Invezz and ActionForex coverage.
2. Switch to **Dutch investor** on the same date. Play the Dutch briefing and compare its story selection and level of detail. Intel’s story preserves the distinction between shareholders’ allegations and established facts.
3. Choose **Custom listener**, enter `Bitcoin, gold`, and generate a new edition. Try `Nvidia` with **Analytical** depth to see the two reported analyst estimates side by side. Change the replay date to see how the publication cutoff affects available stories.
4. Download **Text** and **MP3**. The text is independently readable and carries the links. The audio adds context and names the reporting outlet and date.

## API and delivery

| Endpoint | Result |
| --- | --- |
| `GET /api/replay` | Replay defaults, preset profiles and ingestion statistics |
| `POST /api/briefings` | Saves a briefing and returns its ID, short read, claims and sources. Pass an optional `story_id` to focus on one reviewed story. |
| `GET /api/briefings/{id}` | Retrieves the saved briefing JSON |
| `POST /api/briefings/{id}/audio` | Creates or reuses the MP3 and returns its playback URL |
| `GET /api/briefings/{id}/audio` | Streams the MP3. Add `?download=true` for an attachment. |
| `GET /api/briefings/{id}/message` | Returns the formatted text with source links. Add `?download=true` for an attachment. |

A future n8n workflow can generate a briefing, generate its audio, then fetch the text and binary MP3 from those endpoints. A self-hosted n8n instance needs network access to the app. The Compose service binds to localhost for this demo.

## Data and review

The ingestion path normalizes all six feeds to local SQLite. Exact duplicates and likely translated editions share an edition ID. Cross-publisher event groups and English and Dutch wording are editor-reviewed in `briefing/catalog.py`. Each fact must pass an anchor check against the article body. The replay uses a seven-day lookback and only considers evidence published by the requested time. Add new events by reviewing their source bodies and adding them to the catalog.

OpenAI gets a shortlist of approved paraphrases and returns IDs. The server validates them and renders the approved text and attribution. ElevenLabs receives the finished script. Ingestion itself uses no hosted API calls. The JSON response records token usage for the optional editorial pass, and speech costs depend on the generated script length and provider.

Newstex’s event license covers the supplied corpus. The build context excludes the dataset and local state. Keep the feeds and generated state local and remove the dataset and stored corpus after the event, per the supplied terms. If sharing code, export the app files without the dataset or Git history.
