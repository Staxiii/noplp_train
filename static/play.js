const songId = window.SONG_ID;

const titleEl = document.getElementById("song-title");
const artistEl = document.getElementById("song-artist");
const setupPanel = document.getElementById("setup-panel");
const exercisePanel = document.getElementById("exercise-panel");
const resultPanel = document.getElementById("result-panel");
const lyricsDisplay = document.getElementById("lyrics-display");
const setupError = document.getElementById("setup-error");
const scoreBanner = document.getElementById("score-banner");

const modeSelect = document.getElementById("mode");
const trousOptions = document.getElementById("trous-options");
const strategySelect = document.getElementById("strategy");
const nWrap = document.getElementById("n-wrap");
const minLenWrap = document.getElementById("minlen-wrap");

let currentSessionId = null;

async function loadSong() {
  const song = await apiGet(`/api/songs/${encodeURIComponent(songId)}`);
  titleEl.textContent = song.title;
  artistEl.textContent = song.artist || "";
  if (!song.has_lyrics) {
    setupError.textContent = "Aucune parole enregistrée pour cette chanson. Ajoute-la depuis Admin avant de jouer.";
    setupError.classList.remove("hidden");
    document.getElementById("start-btn").disabled = true;
  }
}

modeSelect.addEventListener("change", () => {
  trousOptions.classList.toggle("hidden", modeSelect.value !== "trous");
});
strategySelect.addEventListener("change", () => {
  const isKeywords = strategySelect.value === "keywords";
  nWrap.classList.toggle("hidden", isKeywords);
  minLenWrap.classList.toggle("hidden", !isKeywords);
});
trousOptions.classList.toggle("hidden", modeSelect.value !== "trous");

function renderExercise(displayLines) {
  lyricsDisplay.innerHTML = "";
  for (const lineSegments of displayLines) {
    const lineDiv = document.createElement("div");
    renderSegments(lineDiv, lineSegments, "index");
    lyricsDisplay.appendChild(lineDiv);
  }
}

async function startExercise() {
  setupError.classList.add("hidden");
  const mode = modeSelect.value;
  const body = { song_id: songId, mode };
  if (mode === "trous") {
    body.strategy = strategySelect.value;
    body.n = parseInt(document.getElementById("n").value, 10) || 6;
    body.min_len = parseInt(document.getElementById("min-len").value, 10) || 5;
  }
  let data;
  try {
    data = await apiPost("/api/exercise/start", body);
  } catch (e) {
    setupError.textContent = e.message;
    setupError.classList.remove("hidden");
    return;
  }
  currentSessionId = data.session_id;
  renderExercise(data.display_lines);
  setupPanel.classList.add("hidden");
  resultPanel.classList.add("hidden");
  exercisePanel.classList.remove("hidden");
  const firstInput = lyricsDisplay.querySelector("input");
  if (firstInput) firstInput.focus();
}

async function submitExercise() {
  const inputs = lyricsDisplay.querySelectorAll(".blank-input");
  const answers = {};
  inputs.forEach((inp) => { answers[inp.dataset.key] = inp.value; });

  let data;
  try {
    data = await apiPost("/api/exercise/submit", {
      session_id: currentSessionId,
      answers,
      strict_accents: document.getElementById("strict-accents").checked,
    });
  } catch (e) {
    alert(e.message);
    return;
  }

  const byIndex = {};
  for (const r of data.results) byIndex[r.index] = r;
  inputs.forEach((inp) => {
    const r = byIndex[inp.dataset.key];
    if (!r) return;
    inp.disabled = true;
    if (r.correct) {
      inp.classList.add("correct");
    } else {
      inp.classList.add("incorrect");
      inp.value = r.expected_word;
    }
  });

  const pct = data.score_percent;
  scoreBanner.textContent = `Score : ${data.correct_blanks} / ${data.total_blanks} (${pct}%)`;
  scoreBanner.className = "score-banner " + (pct >= 80 ? "good" : pct >= 50 ? "mid" : "bad");
  resultPanel.classList.remove("hidden");
}

document.getElementById("start-btn").addEventListener("click", startExercise);
document.getElementById("submit-btn").addEventListener("click", submitExercise);
document.getElementById("restart-btn").addEventListener("click", () => {
  exercisePanel.classList.add("hidden");
  setupPanel.classList.remove("hidden");
});
document.getElementById("again-btn").addEventListener("click", () => {
  resultPanel.classList.add("hidden");
  setupPanel.classList.remove("hidden");
});

loadSong();
