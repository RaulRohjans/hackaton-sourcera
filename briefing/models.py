from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from .interests import INTERESTS

REPLAY = datetime(2026, 11, 18, 23, 59, 59, tzinfo=timezone.utc)
Language = Literal["en", "nl", "de"]
Tone = Literal["professional", "calm", "conversational"]
Voice = Literal["feminine", "masculine"]
InterestQuery = Annotated[str, Field(min_length=1, max_length=240)]
InterestSelection = Annotated[list[str], Field(min_length=1, max_length=len(INTERESTS))]


class Profile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    interests: InterestQuery | InterestSelection
    language: Language = "en"
    max_minutes: Literal[1, 2, 3] = 2
    depth: Literal["essentials", "analytical"] = "analytical"
    tone: Tone = "professional"
    voice: Voice = "masculine"

    @field_validator("interests")
    @classmethod
    def normalize_interests(cls, value: str | list[str]) -> str | list[str]:
        if isinstance(value, str):
            return " ".join(value.split())
        if any(interest not in INTERESTS for interest in value):
            raise ValueError("Unknown interest.")
        return list(dict.fromkeys(value))


class BriefingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Profile
    as_of: AwareDatetime = REPLAY
    use_ai: bool = True
    story_id: str | None = Field(default=None, min_length=1, max_length=80)


PRESETS = {
    "fx": Profile(interests=["economy", "central-banks"],
                  language="en", max_minutes=2, depth="analytical"),
    "retail": Profile(interests=["stocks", "technology"],
                      language="nl", max_minutes=1, depth="essentials",
                      tone="conversational", voice="feminine"),
    "wildcard": Profile(interests=["travel", "science", "culture", "film"],
                        language="de", max_minutes=1, depth="essentials"),
}


class Source(BaseModel):
    id: str
    publisher: str
    published_at: datetime
    author: str
    language: str
    url: str
    evidence_start: int


class Claim(BaseModel):
    id: str
    kind: str
    text: str
    spoken: str
    sources: list[Source]


class BriefingStory(BaseModel):
    id: str
    title: str
    summary: str
    matched_topics: list[str]
    claims: list[Claim]


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int


class Briefing(BaseModel):
    id: str
    profile: Profile
    as_of: datetime
    stories: list[BriefingStory]
    overview: str
    script: str
    estimated_seconds: int
    editor: Literal["reviewed", "openai"]
    usage: Usage | None
    notice: str | None
