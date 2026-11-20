from contextlib import ExitStack
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from briefing.app import app
from briefing.config import Settings
from briefing.ingest import Article, group_editions
from briefing.interests import INTERESTS
from briefing.models import PRESETS
from briefing.storage import connect


class ReplayEvaluation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        settings = Settings()
        if not list(settings.data_dir.glob("*.jsonl")):
            raise unittest.SkipTest("The licensed replay feeds are required.")
        stack = ExitStack()
        cls.addClassCleanup(stack.close)
        state = stack.enter_context(TemporaryDirectory())
        stack.enter_context(patch.dict("os.environ", {
            "BRIEFING_STATE_DIR": state, "OPENAI_API_KEY": "", "ELEVENLABS_API_KEY": "",
        }))
        cls.client = stack.enter_context(TestClient(app))

    def generate(self, name, **updates):
        profile = PRESETS[name].model_dump()
        profile.update(updates)
        response = self.client.post("/api/briefings", json={"profile": profile})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_producer_prices_match_three_figures_in_audio_and_source(self):
        episode = self.generate("fx")
        self.assertEqual(episode["stories"][0]["id"], "us-ppi")
        claims = {claim["id"]: claim for claim in episode["stories"][0]["claims"]}
        for claim_id, figure, spoken in (
            ("october-monthly", "0.3%", "zero point three percent"),
            ("october-monthly", "0.4%", "zero point four percent"),
            ("october-annual", "6.5%", "six point five percent"),
        ):
            with self.subTest(figure=figure):
                claim = claims[claim_id]
                self.assertIn(spoken, claim["spoken"])
                self.assertIn(claim["spoken"], episode["script"])
                self.assertEqual({source["publisher"] for source in claim["sources"]}, {"ActionForex", "Invezz"})
                with connect(app.state.settings.database) as db:
                    for source in claim["sources"]:
                        row = db.execute("SELECT body, url FROM articles WHERE id = ?", (source["id"],)).fetchone()
                        start = source["evidence_start"]
                        self.assertIn(figure, row["body"][start:start + 600])
                        self.assertEqual(source["url"], row["url"])

    def test_disagreement_and_allegation_are_retained_in_short_audio(self):
        episode = self.generate("retail")
        claims = {claim["id"]: claim for story in episode["stories"] for claim in story["claims"]}
        comparison = claims["nvidia-consensus"]
        self.assertEqual(comparison["kind"], "comparison")
        self.assertEqual({source["publisher"] for source in comparison["sources"]}, {"ActionForex", "Invezz"})
        for phrase in ("Analistenramingen verschillen", "125,1", "125,25", "Aandeelhouders stellen"):
            self.assertIn(phrase, episode["script"])
        self.assertEqual(claims["intel-allegation"]["kind"], "allegation")

    def test_presets_have_distinct_tagged_stories_and_voice_does_not_change_script(self):
        picked = set()
        for name, profile in PRESETS.items():
            with self.subTest(preset=name):
                result = self.generate(name)
                self.assertEqual(result["profile"]["language"], profile.language)
                self.assertIn(len(result["stories"]), (4, 5))
                for story in result["stories"]:
                    self.assertNotIn(story["id"], picked)
                    picked.add(story["id"])
                    expected = [INTERESTS[key].labels[profile.language] for key in profile.interests
                                if story["id"] in INTERESTS[key].story_ids]
                    self.assertTrue(expected)
                    self.assertEqual(story["matched_topics"], expected)
                voice = "masculine" if profile.voice == "feminine" else "feminine"
                self.assertEqual(self.generate(name, voice=voice)["script"], result["script"])

        wildcard = self.generate("wildcard", interests=["travel", "science", "film", "crypto"])
        self.assertEqual({story["id"] for story in wildcard["stories"]},
                         {"us-flight-delays", "mars-sulphur", "obsession-streaming", "bitcoin-spot"})

    def test_longer_deeper_edition_adds_facts_and_legacy_request_still_works(self):
        short = self.generate("fx", max_minutes=1, depth="essentials")
        long = self.generate("fx", max_minutes=3, depth="analytical")
        self.assertGreater(long["estimated_seconds"], short["estimated_seconds"])
        self.assertGreater(len(long["stories"][0]["claims"]), len(short["stories"][0]["claims"]))
        legacy = self.client.post("/api/briefings", json={
            "profile": {"interests": "Nvidia", "language": "en"},
            "story_id": "nvidia-leadership",
        }).json()
        self.assertEqual(len(legacy["stories"]), 1)
        lead = legacy["stories"][0]["claims"][0]
        self.assertEqual(lead["id"], "huang-resigns")
        self.assertEqual(len({source["publisher"] for source in lead["sources"]}), 3)

    def test_full_dataset_and_translated_editions(self):
        replay = self.client.get("/api/replay").json()
        self.assertEqual((replay["article_count"], replay["edition_count"], replay["skipped"]), (1740, 1502, 0))
        with connect(app.state.settings.database) as db:
            rows = db.execute(
                "SELECT edition_id FROM articles WHERE id IN (?, ?, ?)",
                ("INVZ-10009737-01M7AMS30JH9CG20KPB7WFHP1P",
                 "INVZ-10010408-01M7AP8YTKFS6J0E74GTFXKS4Z",
                 "INVZ-10010403-01M7AP91R04FNA1Y3JBZWX2EVN"),
            ).fetchall()
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({row["edition_id"] for row in rows}), 1)


class EditionMerging(unittest.TestCase):
    def test_exact_duplicates_merge_transitively_across_url_and_body(self):
        records = [
            Article(key, "feed", "Publisher", "", "en", f"2026-11-18T{time}:00:00+00:00",
                    "", f"https://example.com/{url}", body, "[]", "[]", key)
            for key, time, url, body in [
                ("a", "08", "first", "First report"),
                ("b", "09", "second", "Second report"),
                ("c", "10", "first", "Second report"),
            ]
        ]
        group_editions(records)
        self.assertEqual(len({record.edition_id for record in records}), 1)
