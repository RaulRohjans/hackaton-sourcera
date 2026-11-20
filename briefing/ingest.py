import argparse
from collections import Counter, defaultdict
from dataclasses import astuple, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

from .config import Settings
from .storage import connect, initialize

LOG = logging.getLogger(__name__)
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
FORMAT_VERSION = 1


def clean(value) -> str:
    return " ".join(unicodedata.normalize("NFKC", value or "").split())


def tags(*values) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        clean(tag) for value in values if isinstance(value, list) for tag in value
        if isinstance(tag, str) and clean(tag) and clean(tag).upper() not in {"POSITIVE", "NEGATIVE"}
    ))


@dataclass
class Article:
    id: str
    feed: str
    publisher: str
    author: str
    language: str
    published_at: str
    headline: str
    url: str
    body: str
    categories: str
    tickers: str
    edition_id: str


def normalize(row: dict, feed: str) -> Article:
    article_id = clean(row["$id"])
    when = datetime.fromisoformat(str(row["date"]).replace("Z", "+00:00"))
    if when.tzinfo is None:
        raise ValueError("missing publication offset")
    published_at = when.astimezone(timezone.utc).isoformat(timespec="seconds")
    url = row["permalink"].strip()
    address = urlsplit(url)
    headline = clean(row["headline"])
    body = clean(row["text_content"])
    publication = row.get("publication") or {}
    publisher = clean(publication.get("name"))
    if not all((article_id, headline, body, publisher, address.hostname)) or address.scheme not in {
        "http", "https"
    } or address.username or address.password or re.search(r"[\s\\]", url):
        raise ValueError("missing fields or invalid permalink")
    if feed.startswith("invezz_"):
        publisher = "Invezz"
    return Article(
        article_id, feed, publisher, clean(row.get("source")), clean(row.get("language")).lower(),
        published_at, headline, url, body,
        json.dumps(tags(row.get("provider_categories"), row.get("categories")), ensure_ascii=False),
        json.dumps(tags(row.get("company_tickers")), ensure_ascii=False), article_id,
    )


def number_signature(article: Article) -> set[str]:
    return {re.sub(r"\D", "", number) for number in NUMBER.findall(article.body[:6000])}


def group_editions(articles: list[Article]) -> None:
    by_author = defaultdict(list)
    for article in articles:
        if article.feed == "invezz_en" and article.author:
            by_author[article.author.casefold()].append(article)

    # A translated edition needs a matching byline, publication window and body figures.
    used = set()
    for article in articles:
        if article.feed not in {"invezz_nl", "invezz_de"}:
            continue
        signature = number_signature(article)
        when = datetime.fromisoformat(article.published_at)
        candidates = []
        for original in by_author[article.author.casefold()]:
            if (original.id, article.language) in used:
                continue
            gap = abs((when - datetime.fromisoformat(original.published_at)).total_seconds())
            if gap > 900:
                continue
            other = number_signature(original)
            common = signature & other
            overlap = len(common) / max(len(signature | other), 1)
            if len(common) >= 3 and overlap >= 0.5:
                candidates.append((overlap, -gap, original.id))
        if candidates:
            article.edition_id = max(candidates)[2]
            used.add((article.edition_id, article.language))

    seen_url = {}
    seen_body = {}
    aliases = {}
    for article in sorted(articles, key=lambda a: (a.published_at, a.id)):
        url = urlsplit(article.url)
        key = (url.hostname, url.path.rstrip("/"))
        digest = sha256(article.body.casefold().encode()).digest()
        group = seen_url.get(key) or seen_body.get(digest) or article.edition_id
        if group != article.edition_id:
            aliases[article.edition_id] = group
        seen_url[key] = seen_body[digest] = group

    for article in articles:
        group = article.edition_id
        visited = set()
        while group in aliases and group not in visited:
            visited.add(group)
            group = aliases[group]
        article.edition_id = min(visited) if group in visited else group


def import_feeds(data_dir: Path, database: Path, force: bool = False) -> dict:
    files = sorted(data_dir.glob("*.jsonl"))
    fingerprint = json.dumps([FORMAT_VERSION, str(data_dir.resolve()), [
        (path.name, path.stat().st_size, path.stat().st_mtime_ns) for path in files
    ]])
    with connect(database) as db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute(
            "SELECT value FROM metadata WHERE key = 'import'"
        ).fetchone()
        if previous and not force:
            cached = json.loads(previous["value"])
            if cached["fingerprint"] == fingerprint:
                return cached["stats"]

        articles = {}
        skipped = 0
        for path in files:
            with path.open(encoding="utf-8", errors="replace") as file:
                for line_number, line in enumerate(file, 1):
                    if not line.strip():
                        continue
                    try:
                        article = normalize(json.loads(line), path.stem)
                        if article.id in articles:
                            raise ValueError("duplicate id")
                    except (ValueError, KeyError, TypeError, AttributeError):
                        skipped += 1
                        LOG.warning("Skipped invalid or duplicate record at %s:%d", path.name, line_number)
                    else:
                        articles[article.id] = article
        if files and not articles:
            raise ValueError("No valid articles in the mounted JSONL feeds.")

        records = list(articles.values())
        group_editions(records)
        db.execute("DELETE FROM articles")
        db.executemany("INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (astuple(article) for article in records))
        stats = {
            "article_count": len(records),
            "edition_count": len({article.edition_id for article in records}),
            "publishers": len({article.publisher for article in records}),
            "feeds": dict(Counter(article.feed for article in records)),
            "skipped": skipped,
        }
        db.execute("INSERT OR REPLACE INTO metadata VALUES ('import', ?)",
                   (json.dumps({"fingerprint": fingerprint, "stats": stats}),))
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize the local JSONL snapshot into SQLite.")
    parser.add_argument("--force", action="store_true", help="Reimport the snapshot even if it is unchanged.")
    args = parser.parse_args()
    settings = Settings()
    initialize(settings.database)
    print(json.dumps(import_feeds(settings.data_dir, settings.database, args.force), indent=2))


if __name__ == "__main__":
    main()
