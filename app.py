"""
NOPLP Révision -- Flask prototype.

Reminder: no song lyrics are bundled with this app. `data/catalog.json` only
holds titles/artists/metadata scraped from the fan wiki; the `lyrics` table
is populated by the user (admin UI or import_lyrics.py) from sources they
have the right to use.
"""
import json
import secrets
from collections import defaultdict
from flask import Flask, request, jsonify, render_template, abort

from db import get_db, init_db
import blanking

app = Flask(__name__)

# in-memory cache of "live" exercises: session_id -> {blanks, song_id}
# (kept server-side so the correct words are never sent to the browser)
ACTIVE_EXERCISES = {}


# ---------------------------------------------------------------- pages ----

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/play/<song_id>")
def play(song_id):
    return render_template("play.html", song_id=song_id)


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/review")
def review():
    return render_template("review.html")


@app.route("/stats")
def stats_page():
    return render_template("stats.html")


# ------------------------------------------------------------- songs API ---

@app.route("/api/songs")
def api_songs():
    q = request.args.get("q", "").strip()
    only_with_lyrics = request.args.get("with_lyrics") == "1"
    only_meme = request.args.get("meme") == "1"
    artist = request.args.get("artist", "").strip()
    limit = min(int(request.args.get("limit", 200)), 1000)

    sql = """
        SELECT s.id, s.title, s.collection, s.featured_artists, s.performed_by,
               s.is_meme_chanson, s.meme_10plus_times, s.has_lyrics,
               a.display_name AS artist
        FROM songs s LEFT JOIN artists a ON a.id = s.artist_id
        WHERE 1=1
    """
    params = []
    if q:
        sql += " AND (s.title LIKE ? OR a.display_name LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if only_with_lyrics:
        sql += " AND s.has_lyrics = 1"
    if only_meme:
        sql += " AND s.is_meme_chanson = 1"
    if artist:
        sql += " AND a.display_name = ?"
        params.append(artist)
    sql += " ORDER BY a.display_name, s.title LIMIT ?"
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/artists")
def api_artists():
    with get_db() as conn:
        rows = conn.execute(
            """SELECT a.display_name AS artist, COUNT(*) AS song_count,
                      SUM(s.has_lyrics) AS with_lyrics
               FROM artists a JOIN songs s ON s.artist_id = a.id
               GROUP BY a.id ORDER BY a.display_name"""
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/songs/<song_id>")
def api_song_detail(song_id):
    with get_db() as conn:
        song = conn.execute(
            """SELECT s.*, a.display_name AS artist
               FROM songs s LEFT JOIN artists a ON a.id = s.artist_id
               WHERE s.id = ?""",
            (song_id,),
        ).fetchone()
        if not song:
            abort(404)
        lyrics = conn.execute(
            "SELECT full_text, source_note FROM lyrics WHERE song_id = ?", (song_id,)
        ).fetchone()
    data = dict(song)
    data["lyrics_preview"] = None
    if lyrics:
        # small preview only (first line), never the full text, to keep the
        # song list screen spoiler-free
        first_line = lyrics["full_text"].splitlines()[0] if lyrics["full_text"] else ""
        data["lyrics_preview"] = first_line[:60]
    return jsonify(data)


# -------------------------------------------------------------- admin API --

@app.route("/api/admin/songs/<song_id>/lyrics", methods=["GET"])
def api_get_lyrics_for_edit(song_id):
    """Only used by the admin/editing screen -- returns the *actual* text
    the user themselves entered, for them to review/edit."""
    with get_db() as conn:
        row = conn.execute("SELECT full_text, source_note FROM lyrics WHERE song_id=?", (song_id,)).fetchone()
    if not row:
        return jsonify({"full_text": "", "source_note": ""})
    return jsonify(dict(row))


@app.route("/api/admin/songs/<song_id>/lyrics", methods=["POST"])
def api_save_lyrics(song_id):
    payload = request.get_json(force=True)
    text = (payload.get("full_text") or "").strip()
    note = payload.get("source_note")
    if not text:
        return jsonify({"error": "full_text is required"}), 400

    with get_db() as conn:
        song = conn.execute("SELECT id FROM songs WHERE id=?", (song_id,)).fetchone()
        if not song:
            abort(404)
        existing = conn.execute("SELECT id FROM lyrics WHERE song_id=?", (song_id,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE lyrics SET full_text=?, source_note=?, updated_at=datetime('now') WHERE song_id=?",
                (text, note, song_id),
            )
        else:
            conn.execute(
                "INSERT INTO lyrics (song_id, full_text, source_note) VALUES (?, ?, ?)",
                (song_id, text, note),
            )
        conn.execute("UPDATE songs SET has_lyrics=1, updated_at=datetime('now') WHERE id=?", (song_id,))
    return jsonify({"ok": True})


# ----------------------------------------------------------- exercise API --

@app.route("/api/exercise/start", methods=["POST"])
def api_exercise_start():
    payload = request.get_json(force=True)
    song_id = payload.get("song_id")
    mode = payload.get("mode", "trous")  # 'trous' | 'coupure'
    strategy = payload.get("strategy", "every_n")
    n = int(payload.get("n", 6))
    min_len = int(payload.get("min_len", 5))

    with get_db() as conn:
        lyr = conn.execute("SELECT full_text FROM lyrics WHERE song_id=?", (song_id,)).fetchone()
        song = conn.execute("SELECT id FROM songs WHERE id=?", (song_id,)).fetchone()
        if not song:
            abort(404)
        if not lyr:
            return jsonify({"error": "Aucune parole enregistrée pour cette chanson. "
                                      "Ajoute-la d'abord depuis /admin."}), 400

        if mode == "coupure":
            try:
                display_lines, blanks, cut_line = blanking.build_coupure_exercise(lyr["full_text"])
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            params = {"mode": "coupure", "cut_line": cut_line}
        else:
            display_lines, blanks = blanking.build_trous_exercise(
                lyr["full_text"], strategy=strategy, n=n, min_len=min_len
            )
            params = {"mode": "trous", "strategy": strategy, "n": n, "min_len": min_len}

        cur = conn.execute(
            "INSERT INTO sessions (song_id, mode, params_json, total_blanks) VALUES (?, ?, ?, ?)",
            (song_id, mode, json.dumps(params), len(blanks)),
        )
        session_id = cur.lastrowid

    ACTIVE_EXERCISES[session_id] = {"song_id": song_id, "blanks": blanks}
    # Never send expected_word to the client
    safe_blanks = [{"index": b["index"]} for b in blanks]
    return jsonify({
        "session_id": session_id,
        "display_lines": display_lines,
        "blanks": safe_blanks,
        "total_blanks": len(blanks),
    })


def _grade_and_record(conn, session_id_db, song_id, blanks, answers, strict_accents, key_field="index"):
    """Grade a list of {index, expected_word} blanks against `answers`
    (mapping blank key -> user text), writing blank_attempts + error_bank
    rows for `song_id` under `session_id_db`. Shared by the single-song
    /api/exercise/submit and the cross-song /api/exercise/review_submit so
    grading logic (and the "never trust the client's answer key" rule)
    lives in exactly one place.

    Returns (results, correct_count).
    """
    results = []
    correct_count = 0
    for b in blanks:
        idx = b["index"]
        expected = b["expected_word"]
        lookup_key = b.get(key_field, idx)
        user_answer = answers.get(str(lookup_key), answers.get(lookup_key, ""))
        is_correct = blanking.grade_answer(expected, user_answer, strict_accents)
        correct_count += int(is_correct)

        conn.execute(
            """INSERT INTO blank_attempts (session_id, song_id, blank_index,
               expected_word, user_answer, is_correct)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id_db, song_id, idx, expected, user_answer, int(is_correct)),
        )

        existing = conn.execute(
            "SELECT id, times_seen, times_wrong FROM error_bank WHERE song_id=? AND blank_index=?",
            (song_id, idx),
        ).fetchone()
        if existing:
            new_wrong = existing["times_wrong"] + (0 if is_correct else 1)
            conn.execute(
                """UPDATE error_bank SET times_seen=times_seen+1, times_wrong=?,
                   expected_word=?, last_wrong_at=CASE WHEN ? THEN datetime('now') ELSE last_wrong_at END
                   WHERE id=?""",
                (new_wrong, expected, 0 if is_correct else 1, existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO error_bank (song_id, blank_index, expected_word,
                   times_seen, times_wrong, last_wrong_at)
                   VALUES (?, ?, ?, 1, ?, ?)""",
                (song_id, idx, expected, 0 if is_correct else 1,
                 None if is_correct else "now"),
            )
            if not is_correct:
                conn.execute(
                    "UPDATE error_bank SET last_wrong_at=datetime('now') WHERE song_id=? AND blank_index=?",
                    (song_id, idx),
                )

        results.append({
            key_field: lookup_key,
            "correct": is_correct,
            "expected_word": expected,
            "user_answer": user_answer,
        })
    return results, correct_count


@app.route("/api/exercise/review_start", methods=["POST"])
def api_review_start():
    """Build a short quiz made only of previously-missed words, across all
    songs that still have lyrics, ordered by how often they were missed.

    Unlike a naive version of this endpoint, the expected words never reach
    the client: only a short context snippet + a blank marker per item is
    sent, keyed by a local `item_id`. Grading happens entirely server-side
    in /api/exercise/review_submit, exactly like the single-song flow.
    """
    limit = int((request.get_json(silent=True) or {}).get("limit", 15))
    with get_db() as conn:
        rows = conn.execute(
            """SELECT eb.song_id, eb.blank_index, s.title, a.display_name AS artist
               FROM error_bank eb
               JOIN songs s ON s.id = eb.song_id
               LEFT JOIN artists a ON a.id = s.artist_id
               WHERE eb.times_wrong > 0 AND s.has_lyrics = 1
               ORDER BY eb.times_wrong DESC, eb.last_wrong_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

        lyrics_cache = {}
        items = []
        blanks = []
        for row in rows:
            song_id = row["song_id"]
            if song_id not in lyrics_cache:
                lyr = conn.execute(
                    "SELECT full_text FROM lyrics WHERE song_id=?", (song_id,)
                ).fetchone()
                lyrics_cache[song_id] = lyr["full_text"] if lyr else None
            full_text = lyrics_cache[song_id]
            if not full_text:
                continue

            segments, expected_word = blanking.build_review_snippet(full_text, row["blank_index"])
            if segments is None:
                # lyrics were edited/shortened since this error was recorded;
                # the old position no longer exists -- skip it rather than guess
                continue

            item_id = len(items)
            items.append({
                "item_id": item_id,
                "song_id": song_id,
                "title": row["title"],
                "artist": row["artist"],
                "segments": segments,
            })
            blanks.append({
                "item_id": item_id,
                "index": row["blank_index"],
                "expected_word": expected_word,
                "song_id": song_id,
            })

    review_session_id = "review-" + secrets.token_hex(8)
    ACTIVE_EXERCISES[review_session_id] = {"mode": "review", "blanks": blanks}
    return jsonify({
        "session_id": review_session_id,
        "items": items,
        "total_blanks": len(items),
    })


@app.route("/api/exercise/submit", methods=["POST"])
def api_exercise_submit():
    payload = request.get_json(force=True)
    session_id = payload.get("session_id")
    answers = payload.get("answers", {})  # {blank_index: "user text"}
    strict_accents = bool(payload.get("strict_accents", False))

    exercise = ACTIVE_EXERCISES.get(session_id)
    if not exercise or exercise.get("mode") == "review":
        return jsonify({"error": "Session inconnue ou expirée"}), 400

    song_id = exercise["song_id"]
    blanks = exercise["blanks"]

    with get_db() as conn:
        results, correct_count = _grade_and_record(conn, session_id, song_id, blanks, answers, strict_accents)
        score_percent = round(100.0 * correct_count / len(blanks), 1) if blanks else 0.0
        conn.execute(
            """UPDATE sessions SET finished_at=datetime('now'), correct_blanks=?,
               score_percent=? WHERE id=?""",
            (correct_count, score_percent, session_id),
        )

    ACTIVE_EXERCISES.pop(session_id, None)
    return jsonify({
        "results": results,
        "correct_blanks": correct_count,
        "total_blanks": len(blanks),
        "score_percent": score_percent,
    })


@app.route("/api/exercise/review_submit", methods=["POST"])
def api_review_submit():
    """Grade a review batch built by /api/exercise/review_start. Because a
    review batch spans multiple songs, we can't file it under a single
    `sessions` row (song_id is NOT NULL there) -- instead we create one
    'review'-mode session row per song actually touched, each holding just
    that song's subset of the batch, and record blank_attempts/error_bank
    exactly as the single-song flow does."""
    payload = request.get_json(force=True)
    session_id = payload.get("session_id")
    answers = payload.get("answers", {})  # {item_id: "user text"}
    strict_accents = bool(payload.get("strict_accents", False))

    exercise = ACTIVE_EXERCISES.get(session_id)
    if not exercise or exercise.get("mode") != "review":
        return jsonify({"error": "Session inconnue ou expirée"}), 400

    by_song = defaultdict(list)
    for b in exercise["blanks"]:
        by_song[b["song_id"]].append(b)

    all_results = []
    total_correct = 0
    total_blanks = 0

    with get_db() as conn:
        for song_id, song_blanks in by_song.items():
            cur = conn.execute(
                "INSERT INTO sessions (song_id, mode, params_json, total_blanks) VALUES (?, 'review', NULL, ?)",
                (song_id, len(song_blanks)),
            )
            session_id_db = cur.lastrowid
            results, correct_count = _grade_and_record(
                conn, session_id_db, song_id, song_blanks, answers, strict_accents, key_field="item_id"
            )
            score_percent = round(100.0 * correct_count / len(song_blanks), 1) if song_blanks else 0.0
            conn.execute(
                """UPDATE sessions SET finished_at=datetime('now'), correct_blanks=?,
                   score_percent=? WHERE id=?""",
                (correct_count, score_percent, session_id_db),
            )
            all_results.extend(results)
            total_correct += correct_count
            total_blanks += len(song_blanks)

    ACTIVE_EXERCISES.pop(session_id, None)
    score_percent = round(100.0 * total_correct / total_blanks, 1) if total_blanks else 0.0
    return jsonify({
        "results": all_results,
        "correct_blanks": total_correct,
        "total_blanks": total_blanks,
        "score_percent": score_percent,
    })


# ---------------------------------------------------------------- stats ----

@app.route("/api/stats")
def api_stats():
    with get_db() as conn:
        overall = conn.execute(
            """SELECT COUNT(*) AS sessions_played,
                      AVG(score_percent) AS avg_score,
                      SUM(total_blanks) AS total_blanks,
                      SUM(correct_blanks) AS total_correct
               FROM sessions WHERE finished_at IS NOT NULL"""
        ).fetchone()
        by_song = conn.execute(
            """SELECT s.id, s.title, a.display_name AS artist,
                      COUNT(*) AS attempts, AVG(se.score_percent) AS avg_score,
                      MAX(se.score_percent) AS best_score
               FROM sessions se
               JOIN songs s ON s.id = se.song_id
               LEFT JOIN artists a ON a.id = s.artist_id
               WHERE se.finished_at IS NOT NULL
               GROUP BY s.id ORDER BY attempts DESC LIMIT 25"""
        ).fetchall()
        worst_words = conn.execute(
            """SELECT eb.expected_word, s.title, a.display_name AS artist,
                      eb.times_wrong, eb.times_seen
               FROM error_bank eb
               JOIN songs s ON s.id = eb.song_id
               LEFT JOIN artists a ON a.id = s.artist_id
               WHERE eb.times_wrong > 0
               ORDER BY eb.times_wrong DESC LIMIT 25"""
        ).fetchall()

    return jsonify({
        "overall": dict(overall),
        "by_song": [dict(r) for r in by_song],
        "worst_words": [dict(r) for r in worst_words],
    })


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
