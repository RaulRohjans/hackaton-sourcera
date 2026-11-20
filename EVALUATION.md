# Judging evaluation

The tests use the supplied 18 November 2026 replay. The event answer key and live judges’ wildcard preferences were unavailable in the workspace. The checks below use the feed articles, the challenge notes and an edited wildcard session.

## Trust and accuracy · 25 points

The FX edition’s lead story speaks three figures verified against both the ActionForex and Invezz articles. Each claim’s transcript links directly to its evidence.

| Figure heard | What the sources support |
| --- | --- |
| 0.3% | October U.S. producer prices rose 0.3% from September. |
| 0.4% | Economists had forecast a 0.4% monthly rise. |
| 6.5% | Producer prices were 6.5% higher than a year earlier. |

The short Dutch edition retains Nvidia’s two separate analyst estimates, $125.1 billion from ActionForex and $125.25 billion from Invezz. Its card flags the disagreement and links both reports. Intel’s allegation is explicitly attributed to shareholders. The scripts use reviewed factual paraphrases and describe forecasts as forecasts. Topic choices and voice settings leave those facts intact.

## Fit to the listener · 20 points

| Preset | Output verified in Edge |
| --- | --- |
| FX desk | Five English stories led by U.S. producer prices, followed by the Bank of Japan, U.S. retail sales and inflation in the euro area and U.K. |
| Dutch investor | Four Dutch stories about Nvidia, Intel, Anthropic and Lowe’s. |
| Wildcard Listener | Four German stories on Mars, U.S. flight delays, the Netflix release of *Obsession* and the Rubik’s Cube. |

The three sets had no stories in common in this replay. Swapping **Culture & design** for **Cryptocurrency** in the German wildcard edition replaced the Rubik’s Cube story with Bitcoin. Story tags show the selected interests that qualified each story. Changing only the voice leaves the script unchanged and generates a distinct audio file.

## Making sense of the news · 20 points

The full import consolidated 1,740 feed articles into 1,502 editions. The test verifies that the English, Dutch and German Invezz producer-price versions share one edition. The producer-price story combines Invezz and ActionForex, and a separate story on Jensen Huang’s departure combines Invezz, International Business Times and Zacks. Nvidia’s later earnings guidance is a separate event. A duplicate linked through both its URL and body now merges both source groups. The editor leads with significance and recency, then uses the listener’s remaining topics to choose a varied set.

## Scalability and cost · 15 points

Cold local benchmark on this Windows workstation, using the full feed snapshot and a fresh SQLite database.

| Volume | Articles | Ingest and verify | Indexed database | Metered API cost |
| --- | ---: | ---: | ---: | ---: |
| Full dataset, measured | 1,740 | 0.92 seconds | 11.1 MB | $0 |
| 10× volume, linear estimate | 17,400 | About 9.2 seconds | About 111 MB | $0 |

The estimate covers machine processing of similarly sized records. Hosting, storage retention and human editorial review are separate costs. The translation-matching step now searches a bounded publication window and calculates each original article’s number signature once. Topic ranking and rendering stay local. Repeating the same script and voice reuses the cached MP3. Hosted synthesis is optional and its billed volume depends on the characters in uncached scripts, which the benchmark reports for each preset.

Run `python -m briefing.evaluate` to reproduce the benchmark. With `--audio`, the three cold local MP3 renders took 0.53 to 1.01 seconds each and used 1.64 MB in total.

## Listening experience · 10 points

The short format uses one concise lead per story and keeps material disagreements audible. Longer editions have room for more context. Edge played both voice variants in all three languages and downloaded the exact bytes it streamed. On local eSpeak NG the FX edition ran about 108–109 seconds, the Dutch edition about 49 seconds and the wildcard edition about 48–49 seconds.

## Path to product · 10 points

The intended buyer is a publisher paying for a newsroom subscription. An editor groups events, checks claims and releases a dated edition. The publisher’s scheduler can use the existing API to generate approved listener segments and place the resulting audio and source-linked summaries in its morning newsletter or app. Every edition announces synthetic narration in the audio and repeats the disclosure next to the player.

## Repeat the checks

```sh
python -m unittest discover -s tests -v
python -m briefing.evaluate
```

Use the README walkthrough for the interactive browser checks. The browser test run used local audio on desktop and at 390 and 320 pixels wide. Hosted fallback was exercised with a simulated HTTP 502. The licensed corpus must be available locally for the replay tests.
