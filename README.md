# The Liquid Briefing

A local newsroom demo for Sourcera. Set a listener’s interests, audio language, length and level of detail to generate a personalized news briefing. Play or download the MP3 and open any story’s transcript for its sources.

## Run it

With Docker Desktop running and the supplied JSONL files in `liquid-briefing-data/`:

```sh
docker compose up --build
```

Open [the briefing studio](http://localhost:8000/) or [the API docs](http://localhost:8000/docs). The container imports the mounted feeds at startup, persists its results in SQLite, and can generate English, Dutch and German MP3s using its bundled local speech engine.

To use the hosted providers, copy `.env.example` to `.env` and set either or both keys. Recreate the container after changing `.env`.

| Setting | What it enables |
| --- | --- |
| `OPENAI_API_KEY` | Uses Structured Outputs to choose and order approved stories and fact IDs. `OPENAI_MODEL` defaults to `gpt-5.4-mini`. |
| `ELEVENLABS_API_KEY` | Synthesizes audio with Eleven v4 and exports a 128 kbps MP3. Optional voice IDs are configured per language in `.env.example`. |

The local editor works without OpenAI. The studio automatically tries local narration when ElevenLabs fails. Local speech uses eSpeak NG in Docker or installed system voices on macOS.

The studio requests audio as part of generating a briefing. Identical scripts, voices, model settings and output formats share the same cached MP3 across briefings, playback and downloads. For bulk editions where lower cost matters, set `ELEVENLABS_MODEL=eleven_v4_turbo`. [ElevenLabs API pricing](https://elevenlabs.io/pricing/api)

### Run from Python

Use Python 3.10 or later. For local MP3s, install LAME or FFmpeg and use either macOS speech or eSpeak NG.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn briefing.app:app
```

Use `.venv/bin/python -m briefing.ingest --force` to rerun ingestion. Restart the app to reload the reviewed story catalog. `BRIEFING_DATA_DIR` and `BRIEFING_STATE_DIR` override the default input folder and `.runtime/` state directory.

## Five-minute demo

1. Leave **FX desk** selected and click **Generate briefing**. Play the English markets briefing and open **Transcript & sources** to check the producer-price figures.
2. Select **Dutch investor** and generate again. Compare its shorter Dutch briefing on Nvidia and Intel with the FX desk’s macroeconomic stories.
3. Select **Wildcard Listener** and generate its German briefing on U.S. flight delays and the Rubik’s Cube. Change the interests to `Mars, Netflix` and generate again to see the stories change while keeping German selected.
4. Click **Download Audio** and play the MP3. Each download follows the briefing currently shown in the player.

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

The ingestion path normalizes all six feeds to local SQLite. Exact duplicates and likely translated editions share an edition ID. Cross-publisher event groups and all English, Dutch and German briefing wording are reviewed in `briefing/catalog.py`. Each fact must pass an anchor check against the article body. The studio uses the 18 November replay. The API accepts other cutoffs and uses a seven-day lookback. Matching is limited to reviewed stories, with coverage across markets, technology, travel, culture, science and entertainment.

OpenAI gets a shortlist of approved paraphrases and returns IDs. The server validates them and renders the approved text and attribution. ElevenLabs receives the finished script. Ingestion itself uses no hosted API calls. The JSON response records token usage for the optional editorial pass, and speech costs depend on the generated script length and provider.

Newstex’s event license covers the supplied corpus. The build context excludes the dataset and local state. Keep the feeds and generated state local and remove the dataset and stored corpus after the event, per the supplied terms. If sharing code, export the app files without the dataset or Git history.
