-- Schema for the NOPLP revision app.
-- IMPORTANT: this database never ships with real lyrics pre-loaded. The
-- `lyrics.full_text` column is populated only by the user, through the
-- admin UI (manual entry) or through import_lyrics.py (their own script /
-- JSON files), from sources they have the right to use.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS artists (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_name      TEXT NOT NULL UNIQUE,   -- as listed on the wiki, e.g. "Sardou Michel"
    display_name  TEXT NOT NULL           -- best-effort "Firstname Lastname", e.g. "Michel Sardou"
);

CREATE TABLE IF NOT EXISTS songs (
    id                      TEXT PRIMARY KEY,   -- slug, e.g. "sardou-michel-les-lacs-du-connemara"
    title                   TEXT NOT NULL,
    artist_id               INTEGER REFERENCES artists(id),
    collection              TEXT,                -- e.g. Disney movie / musical name (nullable)
    featured_artists        TEXT,                -- "avec X" text, free-form
    performed_by            TEXT,                -- "chanté par X" text, free-form (musicals/movies)
    wiki_target             TEXT,                -- original wiki page title, kept for reference/dedup
    is_meme_chanson         INTEGER NOT NULL DEFAULT 0,
    meme_10plus_times       INTEGER NOT NULL DEFAULT 0,
    meme_probable_reprise   INTEGER NOT NULL DEFAULT 0,
    meme_classic_100k       INTEGER NOT NULL DEFAULT 0,
    has_lyrics              INTEGER NOT NULL DEFAULT 0,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_songs_artist ON songs(artist_id);
CREATE INDEX IF NOT EXISTS idx_songs_meme ON songs(is_meme_chanson);
CREATE INDEX IF NOT EXISTS idx_songs_has_lyrics ON songs(has_lyrics);

-- User-supplied lyrics text. One row per song (kept in its own table so the
-- catalog can be reseeded from the wiki scrape without ever touching lyrics).
CREATE TABLE IF NOT EXISTS lyrics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id       TEXT NOT NULL UNIQUE REFERENCES songs(id) ON DELETE CASCADE,
    full_text     TEXT NOT NULL,     -- plain text, one verse line per line
    source_note   TEXT,              -- where the user got this from (their own notes, a licensed API, etc.)
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One practice session = one attempt at one song with one blanking strategy.
CREATE TABLE IF NOT EXISTS sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id          TEXT NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    mode             TEXT NOT NULL,      -- 'trous' | 'coupure' | 'review'
    params_json      TEXT,               -- JSON-encoded params used to generate the blanks
    started_at       TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at      TEXT,
    total_blanks     INTEGER,
    correct_blanks   INTEGER,
    score_percent    REAL
);

CREATE INDEX IF NOT EXISTS idx_sessions_song ON sessions(song_id);

-- One row per blank within a session (the actual scoring granularity).
CREATE TABLE IF NOT EXISTS blank_attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    song_id         TEXT NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    blank_index     INTEGER NOT NULL,   -- position of the blank within the song's word list
    expected_word   TEXT NOT NULL,
    user_answer     TEXT,
    is_correct      INTEGER NOT NULL,
    answered_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_blank_attempts_session ON blank_attempts(session_id);
CREATE INDEX IF NOT EXISTS idx_blank_attempts_song ON blank_attempts(song_id);

-- Rolling error bank used to build the "révision des erreurs" queue: one row
-- per (song, blank position), incremented every time that specific blank is
-- answered, so the review mode can prioritize the most frequently missed
-- words for each song.
CREATE TABLE IF NOT EXISTS error_bank (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id         TEXT NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    blank_index     INTEGER NOT NULL,
    expected_word   TEXT NOT NULL,
    times_seen      INTEGER NOT NULL DEFAULT 0,
    times_wrong     INTEGER NOT NULL DEFAULT 0,
    last_wrong_at   TEXT,
    UNIQUE(song_id, blank_index)
);

CREATE INDEX IF NOT EXISTS idx_error_bank_song ON error_bank(song_id);
CREATE INDEX IF NOT EXISTS idx_error_bank_wrong ON error_bank(times_wrong DESC);
