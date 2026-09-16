const qInput = document.getElementById("q");
const withLyrics = document.getElementById("with-lyrics");
const memeOnly = document.getElementById("meme-only");
const listEl = document.getElementById("song-list");
const countLine = document.getElementById("count-line");

let debounceTimer = null;

function scheduleLoad() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(loadSongs, 200);
}

async function loadSongs() {
  const params = new URLSearchParams();
  if (qInput.value.trim()) params.set("q", qInput.value.trim());
  if (withLyrics.checked) params.set("with_lyrics", "1");
  if (memeOnly.checked) params.set("meme", "1");
  params.set("limit", "300");

  let songs;
  try {
    songs = await apiGet(`/api/songs?${params.toString()}`);
  } catch (e) {
    countLine.textContent = "Erreur de chargement.";
    return;
  }

  countLine.textContent = `${songs.length} chanson(s) affichée(s)${songs.length === 300 ? " (limite atteinte, affine ta recherche)" : ""}.`;
  listEl.innerHTML = "";
  for (const s of songs) {
    const badges = [];
    if (s.is_meme_chanson) badges.push(`<span class="badge meme">Même chanson${s.meme_10plus_times ? " 10+" : ""}</span>`);
    badges.push(s.has_lyrics
      ? `<span class="badge has-lyrics">Paroles OK</span>`
      : `<span class="badge no-lyrics">Sans paroles</span>`);

    const li = document.createElement("li");
    li.className = "song-row";
    const left = document.createElement("div");
    left.innerHTML = `<div class="song-title">${escapeHtml(s.title)}</div>
                       <div class="song-artist">${escapeHtml(s.artist || "")}${s.collection ? " · " + escapeHtml(s.collection) : ""}</div>`;
    const right = document.createElement("div");
    right.innerHTML = badges.join("");
    if (s.has_lyrics) {
      const link = document.createElement("a");
      link.className = "btn";
      link.style.marginLeft = "10px";
      link.textContent = "Jouer";
      link.href = `/play/${encodeURIComponent(s.id)}`;
      right.appendChild(link);
    } else {
      const link = document.createElement("a");
      link.className = "btn secondary";
      link.style.marginLeft = "10px";
      link.textContent = "Ajouter les paroles";
      link.href = `/admin?song=${encodeURIComponent(s.id)}`;
      right.appendChild(link);
    }
    li.appendChild(left);
    li.appendChild(right);
    listEl.appendChild(li);
  }
}

qInput.addEventListener("input", scheduleLoad);
withLyrics.addEventListener("change", loadSongs);
memeOnly.addEventListener("change", loadSongs);

loadSongs();
