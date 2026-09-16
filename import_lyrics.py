"""
CLI to import lyrics you have the rights to use into the database.

This script does NOT fetch or generate any lyrics itself -- it only reads a
JSON file *you* provide (built by your own script/manual entry) and writes it
into the `lyrics` table. Expected format (a list of objects):

[
  {
    "song_id": "sardou-michel-les-lacs-du-connemara",   // preferred: exact id from data/catalog.json
    "wiki_target": "Les lacs du Connemara",               // OR match by the original wiki page title
    "lyrics": "Ligne 1...\nLigne 2...\n...",
    "source_note": "Saisi à la main depuis mon cahier de révision"
  },
  ...
]

Usage:
    python import_lyrics.py path/to/my_lyrics.json
    python import_lyrics.py path/to/my_lyrics.json --dry-run

Matching priority: song_id first, then wiki_target (case-sensitive exact
match). Unmatched entries are reported and skipped -- nothing is guessed.
"""
import argparse
import json
import sys
from pathlib import Path
from db import get_db, init_db


def find_song_id(conn, entry):
    if entry.get("song_id"):
        row = conn.execute("SELECT id FROM songs WHERE id = ?", (entry["song_id"],)).fetchone()
        if row:
            return row["id"]
    if entry.get("wiki_target"):
        row = conn.execute(
            "SELECT id FROM songs WHERE wiki_target = ?", (entry["wiki_target"],)
        ).fetchone()
        if row:
            return row["id"]
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("json_file", help="Path to your lyrics JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Report matches without writing")
    args = parser.parse_args()

    init_db()
    data = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("Expected a JSON list at the top level.", file=sys.stderr)
        sys.exit(1)

    matched, unmatched, written = 0, [], 0
    with get_db() as conn:
        for entry in data:
            text = entry.get("lyrics")
            if not text or not text.strip():
                unmatched.append((entry.get("song_id") or entry.get("wiki_target"), "empty lyrics"))
                continue
            song_id = find_song_id(conn, entry)
            if not song_id:
                unmatched.append((entry.get("song_id") or entry.get("wiki_target"), "no matching song"))
                continue
            matched += 1
            if args.dry_run:
                continue
            existing = conn.execute("SELECT id FROM lyrics WHERE song_id = ?", (song_id,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE lyrics SET full_text=?, source_note=?, updated_at=datetime('now') WHERE song_id=?",
                    (text, entry.get("source_note"), song_id),
                )
            else:
                conn.execute(
                    "INSERT INTO lyrics (song_id, full_text, source_note) VALUES (?, ?, ?)",
                    (song_id, text, entry.get("source_note")),
                )
            conn.execute("UPDATE songs SET has_lyrics=1, updated_at=datetime('now') WHERE id=?", (song_id,))
            written += 1

    print(f"Matched: {matched}/{len(data)}  Written: {written}  Unmatched: {len(unmatched)}")
    for ident, reason in unmatched[:50]:
        print(f"  - {ident!r}: {reason}")
    if len(unmatched) > 50:
        print(f"  ... and {len(unmatched) - 50} more")


if __name__ == "__main__":
    main()
