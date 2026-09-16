const setupPanel = document.getElementById("setup-panel");
const quizPanel = document.getElementById("quiz-panel");
const resultPanel = document.getElementById("result-panel");
const itemsContainer = document.getElementById("items-container");
const setupError = document.getElementById("setup-error");
const scoreBanner = document.getElementById("score-banner");

let currentSessionId = null;

async function startReview() {
  setupError.classList.add("hidden");
  const limit = parseInt(document.getElementById("limit").value, 10) || 15;
  let data;
  try {
    data = await apiPost("/api/exercise/review_start", { limit });
  } catch (e) {
    setupError.textContent = e.message;
    setupError.classList.remove("hidden");
    return;
  }
  if (!data.items.length) {
    setupError.textContent = "Pas encore d'erreurs enregistrées (ou plus aucune chanson avec paroles) : joue quelques exercices d'abord !";
    setupError.classList.remove("hidden");
    return;
  }
  currentSessionId = data.session_id;
  itemsContainer.innerHTML = "";
  for (const item of data.items) {
    const wrap = document.createElement("div");
    wrap.className = "review-item";
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = `${item.title} — ${item.artist || ""}`;
    const textLine = document.createElement("div");
    renderSegments(textLine, item.segments, "index");
    // renderSegments keys the input by the segment's absolute word index,
    // which is only unique *within* one song. Re-key it by this review
    // item's item_id, which the server groups answers by instead.
    const input = textLine.querySelector(".blank-input");
    if (input) input.dataset.key = item.item_id;
    wrap.appendChild(meta);
    wrap.appendChild(textLine);
    itemsContainer.appendChild(wrap);
  }
  setupPanel.classList.add("hidden");
  resultPanel.classList.add("hidden");
  quizPanel.classList.remove("hidden");
}

async function submitReview() {
  const inputs = itemsContainer.querySelectorAll(".blank-input");
  const answers = {};
  inputs.forEach((inp) => { answers[inp.dataset.key] = inp.value; });

  let data;
  try {
    data = await apiPost("/api/exercise/review_submit", {
      session_id: currentSessionId,
      answers,
      strict_accents: document.getElementById("strict-accents").checked,
    });
  } catch (e) {
    alert(e.message);
    return;
  }

  const byItem = {};
  for (const r of data.results) byItem[r.item_id] = r;
  inputs.forEach((inp) => {
    const r = byItem[inp.dataset.key];
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

document.getElementById("start-btn").addEventListener("click", startReview);
document.getElementById("submit-btn").addEventListener("click", submitReview);
document.getElementById("again-btn").addEventListener("click", () => {
  resultPanel.classList.add("hidden");
  setupPanel.classList.remove("hidden");
});
