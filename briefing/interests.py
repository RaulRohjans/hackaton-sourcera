from dataclasses import dataclass


@dataclass(frozen=True)
class Interest:
    labels: dict[str, str]
    aliases: tuple[str, ...]
    story_ids: tuple[str, ...]


INTERESTS = {
    "economy": Interest(
        {"en": "Economy", "nl": "Economie", "de": "Wirtschaft"},
        ("macro", "inflation", "producer prices", "retail sales", "CPI", "PPI", "eurozone"),
        ("us-ppi", "us-retail", "uk-cpi", "euro-cpi", "boj-rates"),
    ),
    "stocks": Interest(
        {"en": "Stock markets", "nl": "Aandelenmarkten", "de": "Aktienmärkte"},
        ("equities", "earnings", "shares", "Nasdaq", "Intel", "Nvidia", "Lowe’s", "IPO"),
        ("nvidia-outlook", "intel-lawsuit", "anthropic-ipo", "nvidia-leadership", "lowes-earnings"),
    ),
    "technology": Interest(
        {"en": "Technology", "nl": "Technologie", "de": "Technologie"},
        ("tech", "software", "hardware", "semiconductors", "chips", "Intel", "Nvidia"),
        ("nvidia-outlook", "intel-lawsuit", "anthropic-ipo", "nvidia-leadership"),
    ),
    "central-banks": Interest(
        {"en": "Central banks & currencies", "nl": "Centrale banken en valuta",
         "de": "Zentralbanken und Währungen"},
        ("forex", "FX", "interest rates", "Fed", "dollar", "yen", "ECB", "EZB", "BoJ", "sterling"),
        ("boj-rates", "uk-cpi", "euro-cpi", "gold-spot"),
    ),
    "ai": Interest(
        {"en": "Artificial intelligence", "nl": "Kunstmatige intelligentie",
         "de": "Künstliche Intelligenz"},
        ("AI", "KI", "machine learning", "Anthropic", "Claude", "Nvidia", "chips"),
        ("nvidia-outlook", "anthropic-ipo", "nvidia-leadership"),
    ),
    "crypto": Interest(
        {"en": "Cryptocurrency", "nl": "Cryptovaluta", "de": "Kryptowährungen"},
        ("crypto", "Bitcoin", "BTC", "blockchain", "digital currencies"),
        ("bitcoin-spot",),
    ),
    "commodities": Interest(
        {"en": "Commodities", "nl": "Grondstoffen", "de": "Rohstoffe"},
        ("gold", "goud", "goldpreis", "bullion", "precious metals", "edelmetalle"),
        ("gold-spot",),
    ),
    "travel": Interest(
        {"en": "Travel & aviation", "nl": "Reizen en luchtvaart", "de": "Reisen und Luftfahrt"},
        ("flights", "airports", "airlines", "FAA", "tourism", "Flüge"),
        ("us-flight-delays",),
    ),
    "science": Interest(
        {"en": "Science & space", "nl": "Wetenschap en ruimtevaart", "de": "Wissenschaft und Weltraum"},
        ("Mars", "NASA", "Curiosity", "spaceflight", "astronomy", "research"),
        ("mars-sulphur",),
    ),
    "culture": Interest(
        {"en": "Culture & design", "nl": "Cultuur en design", "de": "Kultur und Design"},
        ("Rubik", "Rubik’s Cube", "Zauberwürfel", "toys", "puzzles", "Hungary", "games"),
        ("rubiks-cube",),
    ),
    "film": Interest(
        {"en": "Film & streaming", "nl": "Film en streaming", "de": "Film und Streaming"},
        ("Netflix", "cinema", "movies", "horror", "Obsession", "Peacock", "entertainment"),
        ("obsession-streaming",),
    ),
}
