const searchInput = document.getElementById("song-search");
const listEl = document.getElementById("admin-song-list");
const editorPanel = document.getElementById("editor-panel");
const editorTitle = document.getElementById("editor-title");
const sourceNote = document.getElementById("source-note");
const lyricsText = document.getElementById("lyrics-text");
const saveBtn = document.getElementById("save-btn");
const saveStatus = document.getElementById("save-status");
const playLink = document.getElementById("play-link");

let currentSongId = null;
let debounceTimer = null;

function scheduleSearch() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(runSearch, 200);
}

async function runSearch() {
  const params = new URLSearchParams();
  if (searchInput.value.trim()) params.set("q", searchInput.value.trim());
  params.set("limit", "60");
  const songs = await apiGet(`/api/songs?${params.toString()}`);
  listEl.innerHTML = "";
  for (const s of songs) {
    const li = document.createElement("li");
    li.className = "song-row";
    li.style.cursor = "pointer";
    li.innerHTML = `<div>
        <div class="song-title">${escapeHtml(s.title)}</div>
        <div class="song-artist">${escapeHtml(s.artist || "")}</div>
      </div>
      <div>${s.has_lyrics ? '<span class="badge has-lyrics">Paroles OK</span>' : '<span class="badge no-lyrics">Sans paroles</span>'}</div>`;
    li.addEventListener("click", () => selectSong(s.id, s.title, s.artist));
    listEl.appendChild(li);
  }
}

async function selectSong(songId, title, artist) {
  currentSongId = songId;
  editorTitle.textContent = `${title} — ${artist || ""}`;
  editorPanel.classList.remove("hidden");
  playLink.href = `/play/${encodeURIComponent(songId)}`;
  saveStatus.textContent = "";

  const existing = await apiGet(`/api/admin/songs/${encodeURIComponent(songId)}/lyrics`);
  lyricsText.value = existing.full_text || "";
  sourceNote.value = existing.source_note || "";
  editorPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

saveBtn.addEventListener("click", async () => {
  if (!currentSongId) return;
  const text = lyricsText.value.trim();
  if (!text) {
    saveStatus.textContent = "Le texte ne peut pas être vide.";
    return;
  }
  saveBtn.disabled = true;
  saveStatus.textContent = "Enregistrement...";
  try {
    await apiPost(`/api/admin/songs/${encodeURIComponent(currentSongId)}/lyrics`, {
      full_text: text,
      source_note: sourceNote.value.trim(),
    });
    saveStatus.textContent = "Enregistré ✓";
    runSearch();
  } catch (e) {
    saveStatus.textContent = "Erreur : " + e.message;
  } finally {
    saveBtn.disabled = false;
  }
});

searchInput.addEventListener("input", scheduleSearch);

// Preselect a song passed via ?song=<id>, e.g. from the repertoire's
// "Ajouter les paroles" link.
const preselect = new URLSearchParams(window.location.search).get("song");
runSearch().then(async () => {
  if (preselect) {
    const song = await apiGet(`/api/songs/${encodeURIComponent(preselect)}`);
    selectSong(song.id, song.title, song.artist);
  }
});
