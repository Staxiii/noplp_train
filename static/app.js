// Small shared helpers used across pages.

async function apiGet(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} -> ${res.status}`);
  return res.json();
}

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `POST ${url} -> ${res.status}`);
  }
  return data;
}

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const child of children || []) {
    if (child) node.appendChild(child);
  }
  return node;
}

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/**
 * Render a list of "segments" (as produced by blanking.py: {type:'text',
 * text} or {type:'blank', index, length}) into a container, creating one
 * <input> per blank. `keyField` picks which property on the segment is used
 * to key the input's data-key attribute (default 'index'; review mode uses
 * 'index' too since segments always carry the absolute word index -- the
 * item_id grouping happens one level up, per review item).
 */
function renderSegments(container, segments, keyField = "index") {
  container.innerHTML = "";
  for (const seg of segments) {
    if (seg.type === "text") {
      container.appendChild(document.createTextNode(seg.text));
    } else if (seg.type === "blank") {
      const input = el("input", {
        type: "text",
        class: "blank-input",
        autocomplete: "off",
        autocapitalize: "off",
        spellcheck: "false",
        style: `width: ${Math.max(3, seg.length + 1)}ch`,
      });
      input.dataset.key = seg[keyField];
      container.appendChild(input);
    }
  }
}
