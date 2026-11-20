"use strict";

const byId = (id) => document.getElementById(id);
const form = byId("profile");
const edition = byId("edition");
const status = byId("status");
const audio = byId("audio");
const play = byId("play");
const seek = byId("seek");
const fallback = byId("local-audio");
const textDownload = byId("download-text");
const audioDownload = byId("download-audio");
const presetButtons = [...document.querySelectorAll("[data-preset]")];
const bars = Array.from({ length: 58 }, (_, index) => {
  const bar = document.createElement("i");
  const peak = Math.abs(Math.sin(index * 0.79) * Math.cos(index * 0.18));
  bar.style.height = `${12 + 86 * peak}%`;
  byId("hero-wave").append(bar);
  return bar;
});

let replay;
let activePreset = "fx";
let briefing;
let loadingAudio = false;
let generating = false;

const COPY = {
  en: {
    titles: { fx: "FX desk briefing", retail: "Dutch investor briefing", custom: "Your briefing" },
    language: "English",
    shortRead: "The short read",
    expand: "Open a story’s transcript to verify its spoken claims.",
    transcript: "Transcript & sources",
    comparison: "Sources cite different estimates",
    allegation: "Allegation",
    revision: "Revised figure",
    forecast: "Forecast",
  },
  nl: {
    titles: { fx: "Valutabriefing", retail: "Beursbriefing", custom: "Jouw briefing" },
    language: "Nederlands",
    shortRead: "In het kort",
    expand: "Open het transcript van een verhaal om de bronnen te controleren.",
    transcript: "Transcript & bronnen",
    comparison: "Bronnen noemen verschillende ramingen",
    allegation: "Beschuldiging",
    revision: "Bijgesteld cijfer",
    forecast: "Prognose",
  },
};

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content) node.textContent = content;
  return node;
}

function formatDate(iso, language = "en", year = false) {
  return new Intl.DateTimeFormat(language === "nl" ? "nl-NL" : "en-GB", {
    day: "numeric", month: "short", year: year ? "numeric" : undefined, timeZone: "UTC",
  }).format(new Date(iso));
}

function timecode(seconds) {
  if (!Number.isFinite(seconds)) return "—";
  const total = Math.floor(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function sourceLinks(sources, language) {
  const links = element("div", "source-links");
  for (const source of sources) {
    const date = formatDate(source.published_at, language);
    const a = element("a", "source-link", `${source.publisher} · ${date} ↗`);
    a.href = source.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.title = [source.author, source.publisher, formatDate(source.published_at, language, true)].filter(Boolean).join(" · ");
    links.append(a);
  }
  return links;
}

function storyCard(story, index, language) {
  const copy = COPY[language];
  const row = element("article", "story");
  const count = element("span", "story-index", String(index + 1).padStart(2, "0"));
  count.setAttribute("aria-hidden", "true");
  const body = element("div", "story-body");
  body.append(element("h3", "", story.title), element("p", "", story.summary));

  const sources = new Map(story.claims.flatMap((claim) => claim.sources).map((source) => [source.id, source]));
  const tools = element("div", "story-tools");
  tools.append(sourceLinks(sources.values(), language));
  body.append(tools);

  const transcript = element("details", "transcript");
  transcript.append(element("summary", "", copy.transcript));
  const claims = element("ol", "claims");
  for (const claim of story.claims) {
    const item = element("li", "");
    if (copy[claim.kind]) item.append(element("p", "claim-note", copy[claim.kind]));
    item.append(element("p", "", claim.spoken), sourceLinks(claim.sources, language));
    claims.append(item);
  }
  transcript.append(claims);
  body.append(transcript);
  row.append(count, body);
  return row;
}

function playerState() {
  if (!briefing) return;
  const label = audio.dataset.provider === "elevenlabs" ? "ElevenLabs" : audio.dataset.provider === "local" ? "Local voice" : "";
  const count = briefing.stories.length;
  const stories = briefing.profile.language === "nl"
    ? `${count} ${count === 1 ? "verhaal" : "verhalen"}`
    : `${count} ${count === 1 ? "story" : "stories"}`;
  const narration = briefing.profile.language === "nl" ? "Synthetische vertelstem" : "Synthetic narration";
  byId("edition-label").textContent = [stories, narration, label].filter(Boolean).join(" · ");
}

function render(result, preset) {
  briefing = result;
  edition.lang = result.profile.language;
  const copy = COPY[result.profile.language];
  audio.pause();
  audio.removeAttribute("src");
  audio.load();
  delete audio.dataset.provider;
  audioDownload.hidden = true;
  fallback.hidden = true;
  seek.disabled = true;
  seek.value = "0";
  bars.forEach((bar) => bar.classList.remove("played"));
  byId("current-time").textContent = "0:00";
  const hasStories = result.stories.length > 0;
  byId("duration").textContent = hasStories ? `~${timecode(result.estimated_seconds)}` : "—";
  byId("edition-title").textContent = copy.titles[preset];
  byId("edition-language").textContent = copy.language;
  byId("edition-date").textContent = formatDate(result.as_of, result.profile.language, true);
  byId("readout-heading").textContent = copy.shortRead;
  byId("readout-label").textContent = hasStories ? copy.expand : "";
  playerState();

  textDownload.href = `/api/briefings/${result.id}/message?download=true`;
  textDownload.hidden = !hasStories;
  const stories = byId("stories");
  stories.replaceChildren();
  stories.lang = result.profile.language;
  if (hasStories) {
    stories.append(...result.stories.map((story, index) => storyCard(story, index, result.profile.language)));
  } else {
    stories.append(element("p", "empty", result.notice));
  }
  status.textContent = hasStories ? result.notice || "" : "";
}

async function jsonRequest(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = typeof error.detail === "string" ? error.detail : null;
    throw new Error(detail || `Request failed (${response.status}). Check your settings and try again.`);
  }
  return response.json();
}

function setPreset(preset) {
  activePreset = preset;
  for (const button of presetButtons) {
    const selected = button.dataset.preset === preset;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  }
}

function readProfile() {
  const values = Object.fromEntries(new FormData(form));
  delete values.date;
  values.max_minutes = Number(values.max_minutes);
  return values;
}

async function generate(useAI = true) {
  if (generating || !form.reportValidity()) return;
  generating = true;
  const preset = activePreset;
  const profile = readProfile();
  if (!profile.interests.trim()) {
    generating = false;
    status.textContent = "Enter the topics you want to hear about.";
    byId("interests").focus();
    return;
  }
  const asOf = `${byId("replay-date").value}T23:59:59Z`;
  edition.setAttribute("aria-busy", "true");
  byId("generate").disabled = true;
  play.disabled = true;
  audio.pause();
  fallback.hidden = true;
  status.textContent = "Building briefing…";
  try {
    const result = await jsonRequest("/api/briefings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile, as_of: asOf, use_ai: useAI }),
    });
    render(result, preset);
  } catch (error) {
    status.textContent = error.message;
  } finally {
    edition.setAttribute("aria-busy", "false");
    byId("generate").disabled = false;
    generating = false;
    play.disabled = loadingAudio || !briefing?.stories.length;
  }
}

async function playBriefing(local = false) {
  if (!briefing?.stories.length || loadingAudio || generating) return;
  const currentId = briefing.id;
  if (!local && audio.getAttribute("src")) {
    if (audio.paused) await audio.play().catch(() => { status.textContent = "Playback could not start. Try again."; });
    else audio.pause();
    return;
  }

  loadingAudio = true;
  play.disabled = true;
  fallback.hidden = true;
  status.textContent = "Creating narration…";
  try {
    const result = await jsonRequest(`/api/briefings/${currentId}/audio?local=${local}`, { method: "POST" });
    if (briefing.id !== currentId || generating) return;
    audio.src = result.url;
    audio.dataset.provider = result.provider;
    playerState();
    audioDownload.href = `${result.url}?download=true`;
    audioDownload.hidden = false;
    status.textContent = "";
    await audio.play().catch(() => { status.textContent = "Audio is ready. Press Play to listen."; });
  } catch (error) {
    if (briefing.id !== currentId || generating) return;
    status.textContent = error.message;
    fallback.hidden = local || replay.audio_provider !== "elevenlabs";
  } finally {
    loadingAudio = false;
    play.disabled = generating || !briefing?.stories.length;
  }
}

function updateTimeline() {
  if (!Number.isFinite(audio.duration)) return;
  const progress = audio.currentTime / audio.duration;
  seek.disabled = false;
  seek.value = String(Math.round(progress * 1000));
  seek.setAttribute("aria-valuetext", `${timecode(audio.currentTime)} of ${timecode(audio.duration)}`);
  byId("current-time").textContent = timecode(audio.currentTime);
  byId("duration").textContent = timecode(audio.duration);
  bars.forEach((bar, index) => bar.classList.toggle("played", index < bars.length * progress));
}

for (const event of ["loadedmetadata", "timeupdate"]) audio.addEventListener(event, updateTimeline);
for (const event of ["play", "pause", "ended"]) {
  audio.addEventListener(event, () => {
    play.classList.toggle("is-playing", !audio.paused);
    play.setAttribute("aria-label", audio.paused ? "Play briefing" : "Pause briefing");
  });
}
audio.addEventListener("error", () => {
  if (!audio.getAttribute("src")) return;
  audio.removeAttribute("src");
  delete audio.dataset.provider;
  audioDownload.hidden = true;
  seek.disabled = true;
  playerState();
  status.textContent = "The audio could not be loaded. Press Play to retry.";
});
seek.addEventListener("input", () => {
  if (Number.isFinite(audio.duration)) audio.currentTime = Number(seek.value) * audio.duration / 1000;
});
play.addEventListener("click", () => playBriefing());
fallback.addEventListener("click", () => playBriefing(true));

form.addEventListener("input", (event) => {
  if (event.target.name !== "date") setPreset("custom");
});
form.addEventListener("submit", (event) => {
  event.preventDefault();
  generate();
});

for (const button of presetButtons) {
  button.addEventListener("click", () => {
    const preset = button.dataset.preset;
    if (generating) return;
    setPreset(preset);
    if (preset === "custom") {
      byId("interests").focus();
      byId("interests").select();
      return;
    }
    if (!replay) return;
    for (const [name, value] of Object.entries(replay.presets[preset])) byId(name).value = value;
    generate();
  });
}

async function start() {
  try {
    replay = await jsonRequest("/api/replay");
    byId("replay-date").value = replay.as_of.slice(0, 10);
    const count = replay.article_count.toLocaleString("en-US");
    byId("replay-stats").textContent = replay.article_count > 0
      ? `Replay · ${count} articles · ${replay.stories} reviewed stories`
      : "Replay data unavailable";
    await generate(false);
  } catch {
    edition.setAttribute("aria-busy", "false");
    byId("edition-label").textContent = "Replay unavailable";
    status.textContent = "The replay could not be loaded. Refresh the page to try again.";
  }
}

start();
