# The Liquid Briefing

A local newsroom demo for Sourcera. Pick interests, an audio language, a voice, a length and a level of detail. Generate a personalized briefing with four or five spoken stories. Play or download the MP3 and open any story’s transcript for its sources.

## Run it

With Docker Desktop running and the supplied JSONL files in `liquid-briefing-data/`:

```sh
docker compose up --build
```

Open [the briefing studio](http://localhost:8000/) or [the API docs](http://localhost:8000/docs). The container imports the mounted feeds at startup, persists its results in SQLite, and can generate English, Dutch and German MP3s using its bundled local speech engine.

To use the hosted providers, copy `.env.example` to `.env` and set either or both keys. Recreate the container after changing `.env`.

| Setting | What it enables |
| --- | --- |
| `OPENAI_API_KEY` | Enables optional Structured Outputs editorial selection for API requests with free-text interests. `OPENAI_MODEL` defaults to `gpt-5.4-mini`. The studio ranks its selected topics locally. |
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

1. Generate the **FX desk** edition. Open **Transcript & sources** on the lead story and check the 0.3% monthly rise, the 0.4% forecast and the 6.5% annual rate.
2. Generate **Dutch investor**. Its four stock-market stories include separate estimates from ActionForex and Invezz. Look for the disagreement label on Nvidia and the allegation label on Intel.
3. Generate **Wildcard Listener**. Its four German stories cover science, aviation, film and design. Open **Interests**, search for `bitcon` and select **Cryptocurrency** from the closest topics. Remove **Culture & design** and generate again to hear Bitcoin take the place of the Rubik’s Cube.
4. Change **Voice** and generate again to hear the alternate narration. Play the briefing or click **Download Audio**. Both use the generated MP3.

The interest picker counts distinct reviewed matches. When a narrow selection covers fewer than four stories, add another interest to fill the edition. One-minute editions cover four stories. Longer editions can cover five.

[Judging evaluation and benchmark](EVALUATION.md)

## API and delivery

| Endpoint | Result |
| --- | --- |
| `GET /api/replay` | Replay defaults, preset profiles, available interest IDs and ingestion statistics |
| `POST /api/briefings` | Saves a briefing and returns its ID, topic matches, claims and sources. Send interest IDs as an array for the studio's ranking or send a free-text string. Pass an optional `story_id` to focus on one reviewed story. |
| `GET /api/briefings/{id}` | Retrieves the saved briefing JSON |
| `POST /api/briefings/{id}/audio` | Creates or reuses the MP3 and returns its playback URL |
| `GET /api/briefings/{id}/audio` | Streams the MP3. Add `?download=true` for an attachment. |
| `GET /api/briefings/{id}/message` | Returns the formatted text with source links. Add `?download=true` for an attachment. |

A newsroom scheduler can generate an approved edition, request its audio, then fetch the text and MP3 for a newsletter or app. The Compose service binds to localhost for this demo.

## Data and review

The ingestion path normalizes all six feeds to local SQLite. Exact duplicates and likely translated editions share an edition ID. Cross-publisher event groups and all English, Dutch and German briefing wording are reviewed in `briefing/catalog.py`. Each fact must pass an anchor check against the article body. The studio uses the 18 November replay. The API accepts other cutoffs and uses a seven-day lookback. Matching is limited to reviewed stories, with coverage across markets, technology, travel, culture, science and entertainment.

OpenAI gets a shortlist of approved paraphrases and returns IDs. The server validates them and renders the approved text and attribution. ElevenLabs receives the finished script. Ingestion itself uses no hosted API calls. The JSON response records token usage for the optional editorial pass, and speech costs depend on the generated script length and provider.

Newstex’s event license covers the supplied corpus. The build context excludes the dataset and local state. Keep the feeds and generated state local and remove the dataset and stored corpus after the event, per the supplied terms. If sharing code, export the app files without the dataset or Git history.
