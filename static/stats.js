function fmtPct(v) {
  return v === null || v === undefined ? "—" : `${Math.round(v * 10) / 10}%`;
}

async function loadStats() {
  const data = await apiGet("/api/stats");

  const cards = document.getElementById("stat-cards");
  const o = data.overall || {};
  const cardDefs = [
    { label: "Sessions terminées", value: o.sessions_played || 0 },
    { label: "Score moyen", value: fmtPct(o.avg_score) },
    { label: "Mots corrects / total", value: `${o.total_correct || 0} / ${o.total_blanks || 0}` },
  ];
  cards.innerHTML = "";
  for (const c of cardDefs) {
    const div = document.createElement("div");
    div.className = "stat-card";
    div.innerHTML = `<div class="value">${c.value}</div><div class="label">${c.label}</div>`;
    cards.appendChild(div);
  }

  const bySongBody = document.querySelector("#by-song-table tbody");
  bySongBody.innerHTML = "";
  document.getElementById("by-song-empty").textContent = data.by_song.length ? "" : "Aucune session terminée pour l'instant.";
  for (const row of data.by_song) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${escapeHtml(row.title)}</td><td>${escapeHtml(row.artist || "")}</td>
      <td>${row.attempts}</td><td>${fmtPct(row.avg_score)}</td><td>${fmtPct(row.best_score)}</td>`;
    bySongBody.appendChild(tr);
  }

  const worstBody = document.querySelector("#worst-words-table tbody");
  worstBody.innerHTML = "";
  document.getElementById("worst-words-empty").textContent = data.worst_words.length ? "" : "Aucun mot raté enregistré pour l'instant.";
  for (const row of data.worst_words) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${escapeHtml(row.expected_word)}</td><td>${escapeHtml(row.title)}</td>
      <td>${escapeHtml(row.artist || "")}</td><td>${row.times_wrong} / ${row.times_seen}</td>`;
    worstBody.appendChild(tr);
  }
}

loadStats();
