"""
Blank-generation engine.

This module never contains or generates song lyrics itself: it only operates,
at run time, on whatever text the *user* has entered for a song through the
admin UI / import script. Two modes are supported, mirroring the brief:

- "trous": classic fill-in-the-blanks scattered across the whole text
  (every Nth word, or only "rare" words above a length threshold).
- "coupure": the NOPLP-style mechanic -- the text is shown up to a random
  cut point, then stops brutally, and the player must type the words that
  come next (until the end of that line).

Matching is done word-by-word, case/accent-insensitive by default (this is
configurable), so a small typo in accents doesn't fail an otherwise-correct
answer unless strict mode is requested.
"""
import re
import unicodedata

WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9'\-]+", re.UNICODE)

# Words too common/short to be interesting as blanks in "trous" keyword mode.
STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "à", "au", "aux",
    "en", "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles",
    "ce", "ces", "cet", "cette", "que", "qui", "quoi", "dont", "où",
    "pour", "par", "sur", "avec", "sans", "dans", "ne", "pas", "plus",
    "est", "es", "suis", "sont", "était", "été", "avoir", "être", "se",
    "son", "sa", "ses", "mon", "ma", "mes", "ton", "ta", "tes", "leur", "leurs",
    "y", "j", "l", "d", "c", "n", "s", "t", "m", "moi", "toi", "lui",
}


def normalize_word(w: str) -> str:
    """Lowercase + strip accents, for lenient comparison."""
    w = w.strip().lower()
    w = unicodedata.normalize("NFKD", w)
    w = "".join(ch for ch in w if not unicodedata.combining(ch))
    w = re.sub(r"[^a-z0-9'\-]", "", w)
    return w


def tokenize(text: str):
    """Split lyrics into tokens, keeping track of line breaks.

    Returns a list of dicts: {word, start, end, line_index}
    where start/end are character offsets in `text`.
    """
    tokens = []
    for line_index, line in enumerate(text.splitlines()):
        for m in WORD_RE.finditer(line):
            tokens.append({
                "word": m.group(0),
                "line_index": line_index,
                "line_text": line,
                "start": m.start(),
                "end": m.end(),
            })
    return tokens


def build_trous_exercise(text: str, strategy="every_n", n=6, min_len=4, seed=None):
    """Blank out a scattered set of words across the whole song.

    strategy: "every_n" blanks every Nth eligible word.
              "keywords" blanks words longer than min_len that aren't stopwords.
    Returns: (display_lines, blanks) where display_lines is a list of lines,
    each line a list of {type: 'word'|'blank', text|blank_index}, and blanks
    is a list of {index, expected_word (normalized answer key is server-side only)}.

    `index` on each blank is the word's ABSOLUTE ordinal position among every
    word in the song (not merely among the blanks), so the same position is
    comparable across different sessions/strategies -- this is what lets the
    error bank track "this exact word in this exact song" over time.
    """
    lines_raw = text.splitlines()
    lines_tokens = [list(WORD_RE.finditer(line)) for line in lines_raw]

    eligible_ids = set()
    for line_i, matches in enumerate(lines_tokens):
        for m in matches:
            word = m.group(0)
            is_eligible = True
            if strategy == "keywords":
                is_eligible = (
                    len(word) >= min_len
                    and normalize_word(word) not in STOPWORDS
                )
            if is_eligible:
                eligible_ids.add(id(m))

    # decide which eligible words become blanks
    blank_word_ids = set()
    if strategy == "every_n":
        eligible_in_order = [m for matches in lines_tokens for m in matches if id(m) in eligible_ids]
        for i, m in enumerate(eligible_in_order):
            if (i + 1) % n == 0:
                blank_word_ids.add(id(m))
    else:  # keywords: blank every eligible keyword
        blank_word_ids = eligible_ids

    display_lines = []
    blanks = []
    word_pos = 0  # absolute position across the WHOLE song
    for line_i, line in enumerate(lines_raw):
        segments = []
        last_end = 0
        for m in lines_tokens[line_i]:
            if m.start() > last_end:
                segments.append({"type": "text", "text": line[last_end:m.start()]})
            word = m.group(0)
            if id(m) in blank_word_ids:
                segments.append({"type": "blank", "index": word_pos, "length": len(word)})
                blanks.append({"index": word_pos, "expected_word": word})
            else:
                segments.append({"type": "text", "text": word})
            word_pos += 1
            last_end = m.end()
        if last_end < len(line):
            segments.append({"type": "text", "text": line[last_end:]})
        display_lines.append(segments)

    return display_lines, blanks


def build_coupure_exercise(text: str, cut_line=None, rng=None):
    """The NOPLP-style mechanic: reveal lines up to `cut_line` in full, then
    blank out the entirety of the remaining words on that line and the
    following line (a "brutal stop"). If cut_line is None, pick one at
    random among lines that have at least 3 words, avoiding the very first
    and last line so there's context before and a real continuation after.
    """
    import random
    r = rng or random
    lines_raw = [l for l in text.splitlines()]
    non_empty_idx = [i for i, l in enumerate(lines_raw) if l.strip()]
    if len(non_empty_idx) < 3:
        raise ValueError("Song text too short for the 'coupure' mode")

    candidates = non_empty_idx[1:-1] or non_empty_idx
    if cut_line is None:
        cut_line = r.choice(candidates)

    display_lines = []
    blanks = []
    word_pos = 0  # absolute position across the WHOLE song (see build_trous_exercise)

    for line_i, line in enumerate(lines_raw):
        matches = list(WORD_RE.finditer(line))
        if line_i < cut_line:
            display_lines.append([{"type": "text", "text": line}])
            word_pos += len(matches)
            continue
        if line_i == cut_line:
            # reveal first ~half of the words, blank the rest of this line
            keep_n = max(1, len(matches) // 2)
            segments = []
            last_end = 0
            for wi, m in enumerate(matches):
                if m.start() > last_end:
                    segments.append({"type": "text", "text": line[last_end:m.start()]})
                word = m.group(0)
                if wi < keep_n:
                    segments.append({"type": "text", "text": word})
                else:
                    segments.append({"type": "blank", "index": word_pos, "length": len(word)})
                    blanks.append({"index": word_pos, "expected_word": word})
                word_pos += 1
                last_end = m.end()
            if last_end < len(line):
                segments.append({"type": "text", "text": line[last_end:]})
            display_lines.append(segments)
            continue
        if line_i == cut_line + 1:
            # blank the whole next line too, so there's a real "continuation" to type
            segments = []
            last_end = 0
            for m in matches:
                if m.start() > last_end:
                    segments.append({"type": "text", "text": line[last_end:m.start()]})
                word = m.group(0)
                segments.append({"type": "blank", "index": word_pos, "length": len(word)})
                blanks.append({"index": word_pos, "expected_word": word})
                word_pos += 1
                last_end = m.end()
            if last_end < len(line):
                segments.append({"type": "text", "text": line[last_end:]})
            display_lines.append(segments)
            continue
        # everything after stays hidden entirely (not part of the exercise)
        break

    return display_lines, blanks, cut_line


def build_review_snippet(text: str, target_index: int, context_words: int = 6):
    """Locate the word at absolute position `target_index` in `text` (the
    same absolute-indexing scheme used by build_trous_exercise /
    build_coupure_exercise, and thus the same scheme `error_bank.blank_index`
    was recorded under) and return a short display snippet: a few words of
    preceding context as plain text, followed by a single blank standing in
    for the target word.

    This never returns the expected word to a caller that might forward it
    to the client -- it's returned alongside the segments so the *server*
    can grade it, exactly like the other exercise builders.

    Returns (segments, expected_word), or (None, None) if target_index is
    out of range for this text (e.g. the lyrics were edited/shortened after
    the error was recorded, so the old position no longer exists).
    """
    tokens = []
    for line in text.splitlines():
        for m in WORD_RE.finditer(line):
            tokens.append(m.group(0))

    if target_index < 0 or target_index >= len(tokens):
        return None, None

    expected_word = tokens[target_index]
    start = max(0, target_index - context_words)
    context = tokens[start:target_index]

    segments = []
    if start > 0:
        segments.append({"type": "text", "text": "(...) "})
    if context:
        segments.append({"type": "text", "text": " ".join(context) + " "})
    segments.append({"type": "blank", "index": target_index, "length": len(expected_word)})

    return segments, expected_word


def grade_answer(expected_word: str, user_answer: str, strict_accents=False) -> bool:
    if user_answer is None:
        return False
    if strict_accents:
        return user_answer.strip() == expected_word.strip()
    return normalize_word(user_answer) == normalize_word(expected_word)
