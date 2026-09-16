"""
Load data/catalog.json (scraped titles/artists/flags -- NO lyrics) into the
songs/artists tables. Safe to re-run: it upserts by song id / artist raw_name
and never touches the `lyrics` table, so re-seeding the catalog (e.g. after
pulling a fresh wiki export) never wipes out lyrics you've entered.
"""
import json
from pathlib import Path
from db import get_db, init_db

DATA_PATH = Path(__file__).parent / "data" / "catalog.json"


def upsert_artist(conn, raw_name, display_name):
    if not raw_name:
        return None
    cur = conn.execute("SELECT id FROM artists WHERE raw_name = ?", (raw_name,))
    row = cur.fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO artists (raw_name, display_name) VALUES (?, ?)",
        (raw_name, display_name or raw_name),
    )
    return cur.lastrowid


def main():
    init_db()
    catalog = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    with get_db() as conn:
        artist_cache = {}
        inserted, updated = 0, 0
        for song in catalog:
            raw = song["artist_raw"]
            if raw not in artist_cache:
                artist_cache[raw] = upsert_artist(conn, raw, song["artist_display"])
            artist_id = artist_cache[raw]

            existing = conn.execute(
                "SELECT id FROM songs WHERE id = ?", (song["id"],)
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE songs SET title=?, artist_id=?, collection=?,
                       featured_artists=?, performed_by=?, wiki_target=?,
                       is_meme_chanson=?, meme_10plus_times=?,
                       meme_probable_reprise=?, meme_classic_100k=?,
                       updated_at=datetime('now')
                       WHERE id=?""",
                    (
                        song["title"], artist_id, song["collection"],
                        song["featured_artists"], song["performed_by"], song["wiki_target"],
                        int(song["is_meme_chanson"]), int(song["meme_10plus_times"]),
                        int(song["meme_probable_reprise"]), int(song["meme_classic_100k"]),
                        song["id"],
                    ),
                )
                updated += 1
            else:
                conn.execute(
                    """INSERT INTO songs (id, title, artist_id, collection,
                       featured_artists, performed_by, wiki_target,
                       is_meme_chanson, meme_10plus_times, meme_probable_reprise,
                       meme_classic_100k)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        song["id"], song["title"], artist_id, song["collection"],
                        song["featured_artists"], song["performed_by"], song["wiki_target"],
                        int(song["is_meme_chanson"]), int(song["meme_10plus_times"]),
                        int(song["meme_probable_reprise"]), int(song["meme_classic_100k"]),
                    ),
                )
                inserted += 1

    print(f"Seed complete: {inserted} songs inserted, {updated} updated, "
          f"{len(artist_cache)} distinct artists.")


if __name__ == "__main__":
    main()
