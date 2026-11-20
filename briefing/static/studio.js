"use strict";

const byId = (id) => document.getElementById(id);
const form = byId("profile");
const listener = byId("listener");
const generateButton = byId("generate");
const playerTitle = byId("player-title");
const note = byId("player-note");
const status = byId("status");
const audio = byId("audio");
const download = byId("download-audio");
const retry = byId("retry-audio");
const storiesPanel = byId("stories-panel");
const stories = byId("stories");
const presets = JSON.parse(byId("listener-presets").textContent);

const COPY = {
  en: {
    language: "English", locale: "en-GB", briefing: "Your briefing", stories: "In this briefing",
    transcript: "Transcript & sources", count: ["story", "stories"],
    narration: "Synthetic narration", ready: "Audio is ready.",
    creating: "Creating audio…", audioError: "Audio is unavailable. Try again.",
  },
  nl: {
    language: "Nederlands", locale: "nl-NL", briefing: "Jouw briefing", stories: "In deze briefing",
    transcript: "Transcript & bronnen", count: ["verhaal", "verhalen"],
    narration: "Synthetische vertelstem", ready: "De audio is klaar.",
    creating: "Audio maken…", audioError: "Audio is niet beschikbaar. Probeer het opnieuw.",
  },
  de: {
    language: "Deutsch", locale: "de-DE", briefing: "Ihr Nachrichtenüberblick", stories: "In dieser Ausgabe",
    transcript: "Transkript und Quellen", count: ["Beitrag", "Beiträge"],
    narration: "Synthetische Sprecherstimme", ready: "Die Audioausgabe ist fertig.",
    creating: "Audio wird erstellt…", audioError: "Audio ist nicht verfügbar. Bitte erneut versuchen.",
  },
};

let activeRequest;
let briefing;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function storyCard(story, copy) {
  const article = element("article", null, "story");
  article.append(element("h3", story.title), element("p", story.summary));
  const details = element("details");
  const claims = element("div", null, "claims");
  const format = new Intl.DateTimeFormat(copy.locale, { dateStyle: "medium", timeZone: "UTC" });
  for (const claim of story.claims) {
    const section = element("div", null, "claim");
    const links = element("ul", null, "source-links");
    for (const source of claim.sources) {
      const item = element("li");
      const link = element("a", `${source.publisher} · ${format.format(new Date(source.published_at))}`);
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      item.append(link);
      links.append(item);
    }
    section.append(element("p", claim.spoken), links);
    claims.append(section);
  }
  details.append(element("summary", copy.transcript), claims);
  article.append(details);
  return article;
}

function showStatus(message, language = "en") {
  status.lang = language;
  status.textContent = message;
}

function reset() {
  activeRequest?.abort();
  activeRequest = undefined;
  briefing = undefined;
  generateButton.disabled = false;
  audio.hidden = true;
  if (audio.hasAttribute("src")) {
    audio.pause();
    audio.removeAttribute("src");
    audio.load();
  }
  download.hidden = true;
  download.removeAttribute("href");
  retry.hidden = true;
  storiesPanel.hidden = true;
  stories.replaceChildren();
  playerTitle.lang = "en";
  playerTitle.textContent = COPY.en.briefing;
  note.lang = "en";
  note.textContent = "Your audio and stories will appear here.";
  showStatus("");
}

function render(result) {
  const language = result.profile.language;
  const copy = COPY[language];
  const count = result.stories.length;
  playerTitle.lang = language;
  playerTitle.textContent = copy.briefing;
  note.lang = language;
  note.textContent = count
    ? `${copy.language} · ${count} ${copy.count[count === 1 ? 0 : 1]} · ${copy.narration}`
    : copy.language;
  if (!count) {
    showStatus(result.notice, language);
    return;
  }
  storiesPanel.lang = language;
  byId("stories-heading").textContent = copy.stories;
  stories.replaceChildren(...result.stories.map((story) => storyCard(story, copy)));
  storiesPanel.hidden = false;
}

async function jsonRequest(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const error = new Error(`Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

async function prepareAudio(result, signal) {
  const language = result.profile.language;
  const copy = COPY[language];
  const path = `/api/briefings/${result.id}/audio`;
  const options = { method: "POST", signal };
  retry.hidden = true;
  showStatus(copy.creating, language);
  try {
    let asset;
    try {
      asset = await jsonRequest(path, options);
    } catch (error) {
      if (signal.aborted || error.status !== 502) throw error;
      asset = await jsonRequest(`${path}?local=true`, options);
    }
    if (signal.aborted) return;
    audio.src = asset.url;
    audio.hidden = false;
    download.href = `${asset.url}?download=true`;
    download.hidden = false;
    showStatus(copy.ready, language);
  } catch {
    if (signal.aborted) return;
    showStatus(copy.audioError, language);
    retry.hidden = false;
  }
}

async function run(action) {
  const controller = new AbortController();
  activeRequest = controller;
  generateButton.disabled = true;
  try {
    await action(controller.signal);
  } finally {
    if (activeRequest === controller) {
      activeRequest = undefined;
      generateButton.disabled = false;
    }
  }
}

form.addEventListener("input", reset);
listener.addEventListener("change", () => {
  const preset = presets[listener.value];
  if (preset) {
    for (const name of ["interests", "language", "max_minutes", "depth"]) {
      byId(name).value = preset[name];
    }
  } else {
    byId("interests").focus();
    byId("interests").select();
  }
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (activeRequest) return;
  const profile = { ...presets[listener.value], ...Object.fromEntries(new FormData(form)) };
  profile.max_minutes = Number(profile.max_minutes);
  profile.interests = profile.interests.trim();
  if (!profile.interests) {
    showStatus("Enter the topics you want to hear about.");
    byId("interests").focus();
    return;
  }
  reset();
  showStatus("Building your briefing…");
  run(async (signal) => {
    try {
      const result = await jsonRequest("/api/briefings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile }),
        signal,
      });
      if (signal.aborted) return;
      briefing = result;
      render(result);
      if (result.stories.length) await prepareAudio(result, signal);
    } catch {
      if (!signal.aborted) showStatus("Briefing unavailable. Try generating it again.");
    }
  });
});

retry.addEventListener("click", () => {
  if (briefing && !activeRequest) run((signal) => prepareAudio(briefing, signal));
});

audio.addEventListener("error", () => {
  if (!briefing || !audio.hasAttribute("src") || !audio.error) return;
  const language = briefing.profile.language;
  audio.hidden = true;
  audio.removeAttribute("src");
  download.hidden = true;
  download.removeAttribute("href");
  showStatus(COPY[language].audioError, language);
  retry.hidden = false;
});
