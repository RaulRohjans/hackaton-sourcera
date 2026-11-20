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
const interests = JSON.parse(byId("available-interests").textContent);
const interestField = byId("interest-field");
const interestToggle = byId("interests");
const interestMenu = byId("interest-menu");
const interestSearch = byId("interest-search");
const interestOptions = byId("interest-options");
const selectedInterests = new Set();
const minimumStories = 4;

const COPY = {
  en: {
    language: "English", locale: "en-GB", briefing: "Your briefing", stories: "In this briefing",
    transcript: "Transcript & sources", count: ["story", "stories"],
    narration: "Synthetic narration", ready: "Audio is ready.",
    creating: "Creating audio…", audioError: "Audio is unavailable. Try again.",
    flags: { comparison: "Sources differ", allegation: "Allegation", forecast: "Forecast", revision: "Revised figure" },
  },
  nl: {
    language: "Nederlands", locale: "nl-NL", briefing: "Jouw briefing", stories: "In deze briefing",
    transcript: "Transcript & bronnen", count: ["verhaal", "verhalen"],
    narration: "Synthetische vertelstem", ready: "De audio is klaar.",
    creating: "Audio maken…", audioError: "Audio is niet beschikbaar. Probeer het opnieuw.",
    flags: { comparison: "Bronnen verschillen", allegation: "Beschuldiging", forecast: "Prognose", revision: "Bijgesteld cijfer" },
  },
  de: {
    language: "Deutsch", locale: "de-DE", briefing: "Ihr Nachrichtenüberblick", stories: "In dieser Ausgabe",
    transcript: "Transkript und Quellen", count: ["Beitrag", "Beiträge"],
    narration: "Synthetische Sprecherstimme", ready: "Die Audioausgabe ist fertig.",
    creating: "Audio wird erstellt…", audioError: "Audio ist nicht verfügbar. Bitte erneut versuchen.",
    flags: { comparison: "Quellen weichen ab", allegation: "Vorwurf", forecast: "Prognose", revision: "Revidierte Zahl" },
  },
};

let activeRequest;
let briefing;
let matchingStoryCount = 0;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function storyCard(story, copy) {
  const article = element("article", null, "story");
  article.append(element("h3", story.title));
  const tags = element("ul", null, "topic-list story-topics");
  for (const topic of story.matched_topics) {
    tags.append(element("li", topic, "topic"));
  }
  const flags = new Set(story.claims.map((claim) => copy.flags[claim.kind]).filter(Boolean));
  for (const flag of flags) {
    tags.append(element("li", flag, "topic claim-flag"));
  }
  if (tags.childElementCount) article.append(tags);
  article.append(element("p", story.summary));
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

function searchText(value) {
  return value.toLowerCase().normalize("NFD").replace(/\p{M}/gu, "")
    .replace(/ß/g, "ss").replace(/[^\p{L}\p{N}]+/gu, " ").trim();
}

function editDistance(first, second) {
  let previous = Array.from({ length: second.length + 1 }, (_, index) => index);
  for (let row = 1; row <= first.length; row += 1) {
    const current = [row];
    for (let column = 1; column <= second.length; column += 1) {
      const change = Number(first[row - 1] !== second[column - 1]);
      current.push(Math.min(previous[column] + 1, current[column - 1] + 1, previous[column - 1] + change));
    }
    previous = current;
  }
  return previous[second.length];
}

function searchScore(query, term) {
  if (term === query) return 0;
  if (term.startsWith(query)) return 1;
  if (term.includes(query)) return 2;
  return 3 + Math.min(...[term, ...term.split(" ")].map(
    (token) => editDistance(query, token) / Math.max(query.length, token.length)
  ));
}

function renderOptions() {
  const query = searchText(interestSearch.value);
  const ranked = interests.map((interest) => ({
    interest,
    score: query ? Math.min(...interest.search_terms.map((term) => searchScore(query, searchText(term)))) : 0,
  })).sort((first, second) => first.score - second.score);
  const bestScore = ranked[0]?.score;
  const approximate = Boolean(query && bestScore >= 3);
  byId("interest-suggestions").hidden = !approximate;
  const matchLimit = query && bestScore === 0 ? 0 : 2;
  const results = approximate ? ranked.slice(0, 4) : ranked.filter(({ score }) => score <= matchLimit);
  interestOptions.replaceChildren(...results.map(({ interest }) => {
    const row = element("label", null, "interest-option");
    const checkbox = element("input");
    checkbox.type = "checkbox";
    checkbox.value = interest.id;
    checkbox.checked = selectedInterests.has(interest.id);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) selectedInterests.add(interest.id);
      else selectedInterests.delete(interest.id);
      updateInterests();
      reset();
    });
    row.append(checkbox, element("span", interest.label));
    return row;
  }));
}

function setInterestMenu(open, focusToggle = false) {
  interestMenu.hidden = !open;
  interestToggle.setAttribute("aria-expanded", String(open));
  if (open) {
    interestSearch.value = "";
    renderOptions();
    interestSearch.focus();
  } else if (focusToggle) {
    interestToggle.focus();
  }
}

function updateInterests() {
  const current = interests.filter(({ id }) => selectedInterests.has(id));
  matchingStoryCount = new Set(current.flatMap(({ story_ids }) => story_ids)).size;
  const count = current.length;
  byId("interest-selection").textContent = count ? count + " selected" : "Choose interests";
  byId("interest-coverage").textContent = interests.length === 0
    ? "No reviewed stories are available for this edition."
    : matchingStoryCount < minimumStories
      ? "Choose topics covering at least 4 stories (" + matchingStoryCount + " matched)."
      : matchingStoryCount + " matching stories";
  byId("selected-interests").replaceChildren(...current.map(({ label, id }) => {
    const item = element("li");
    const remove = element("button", null, "topic remove-topic");
    remove.type = "button";
    remove.setAttribute("aria-label", "Remove " + label);
    const cross = element("span", "×");
    cross.setAttribute("aria-hidden", "true");
    remove.append(document.createTextNode(label), cross);
    remove.addEventListener("click", () => {
      selectedInterests.delete(id);
      updateInterests();
      if (!interestMenu.hidden) renderOptions();
      interestToggle.focus();
      reset();
    });
    item.append(remove);
    return item;
  }));
}

function applyPreset(preset) {
  selectedInterests.clear();
  for (const { id } of interests) {
    if (preset.interests.includes(id)) selectedInterests.add(id);
  }
  for (const name of ["language", "voice", "max_minutes", "depth"]) {
    byId(name).value = preset[name];
  }
  updateInterests();
}

function reset() {
  activeRequest?.abort();
  activeRequest = undefined;
  briefing = undefined;
  generateButton.disabled = matchingStoryCount < minimumStories;
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
      generateButton.disabled = matchingStoryCount < minimumStories;
    }
  }
}

interestToggle.addEventListener("click", () => setInterestMenu(interestMenu.hidden));
interestSearch.addEventListener("input", renderOptions);
interestSearch.addEventListener("keydown", (event) => {
  if (event.key === "Enter") event.preventDefault();
});
byId("interest-done").addEventListener("click", () => setInterestMenu(false, true));
interestField.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !interestMenu.hidden) {
    event.preventDefault();
    setInterestMenu(false, true);
  }
});
interestField.addEventListener("focusout", (event) => {
  if (event.relatedTarget && !interestField.contains(event.relatedTarget)) setInterestMenu(false);
});
document.addEventListener("pointerdown", (event) => {
  if (!interestField.contains(event.target)) setInterestMenu(false);
});

form.addEventListener("change", (event) => {
  if (event.target.matches("select") && event.target !== listener) reset();
});
listener.addEventListener("change", () => {
  const preset = presets[listener.value];
  if (preset) {
    setInterestMenu(false);
    applyPreset(preset);
  } else {
    setInterestMenu(true);
  }
  reset();
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (activeRequest || matchingStoryCount < minimumStories) return;
  const profile = { ...presets[listener.value], ...Object.fromEntries(new FormData(form)) };
  profile.max_minutes = Number(profile.max_minutes);
  profile.interests = [...selectedInterests];
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

applyPreset(presets[listener.value] || presets.fx);
reset();
