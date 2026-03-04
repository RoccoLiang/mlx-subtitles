#!/usr/bin/env python3
"""
Assemble bilingual ASS subtitles from translated batch results.

Usage:
    python scripts/assemble_ass.py <tmpdir> <words.json> [input_file]

Arguments:
    tmpdir      Directory containing _words_result_0.json, _words_result_1.json, ...
    words.json  Word-level timestamp file from mlx-whisper
    input_file  Optional: original video path (determines output .ass filename)
"""

import bisect
import json
import os
import re
import sys

HOLD_TIME = 0.4  # Seconds subtitle lingers after last word ends


def load_words(words_json: str) -> list[dict]:
    with open(words_json, encoding="utf-8") as f:
        return json.load(f)


def load_sentences(tmpdir: str) -> list[dict]:
    all_sentences = []
    i = 0
    while True:
        p = os.path.join(tmpdir, f"_words_result_{i}.json")
        if not os.path.exists(p):
            break
        with open(p, encoding="utf-8") as f:
            all_sentences.extend(json.load(f))
        i += 1
    return all_sentences


# ── Text cleaning ──────────────────────────────────────────────────────────────

def wclean(w: str) -> str:
    """Strip punctuation, lowercase — keeps ASCII alnum and Unicode word chars."""
    return re.sub(r"[^\w]", "", w, flags=re.UNICODE).lower()


def is_cjk(text: str) -> bool:
    """True when CJK (Japanese/Chinese) characters outnumber ASCII alnum chars."""
    cjk = sum(1 for c in text if "\u3040" <= c <= "\u9fff")
    asc = sum(1 for c in text if c.isascii() and c.isalnum())
    return cjk > max(asc, 2)


# ── Token index helpers ────────────────────────────────────────────────────────

def build_index(wc: list[str]) -> tuple[str, list[int]]:
    """Concatenate all cleaned tokens and record their start positions."""
    wcat = "".join(wc)
    starts: list[int] = []
    pos = 0
    for tok in wc:
        starts.append(pos)
        pos += len(tok)
    return wcat, starts


def merged(wc: list[str], i: int) -> str:
    """Concatenate token i with token i+1 (handles 'JP' + '-8000' → 'jp8000')."""
    return wc[i] + (wc[i + 1] if i + 1 < len(wc) else "")


# ── Position finders ───────────────────────────────────────────────────────────

def find_start(
    src_text: str,
    search_from: int,
    wc: list[str],
    wcat: str,
    wcat_starts: list[int],
    window: int = 150,
) -> int | None:
    """Return the best word-array index where src_text begins."""
    src_clean = wclean(src_text)
    if not src_clean:
        return None

    if is_cjk(src_clean):
        anchor = src_clean[:6]
        lo = wcat_starts[max(0, search_from - 3)]
        hi = wcat_starts[min(search_from + window, len(wc) - 1)] + 10
        idx = wcat.find(anchor, lo, hi)
        if idx == -1:
            anchor = src_clean[:3]
            idx = wcat.find(anchor, max(0, lo - 30), hi + 30)
        if idx == -1:
            return None
        return max(0, bisect.bisect_right(wcat_starts, idx) - 1)

    # English: token-based with fuzzy prefix matching
    toks = [wclean(w) for w in src_text.split() if wclean(w)]
    anchor = toks[:3]
    if not anchor:
        return None
    best_score, best_pos = 0, None
    for j in range(max(0, search_from - 3), min(search_from + window, len(wc))):
        score = 0
        for k, a in enumerate(anchor):
            idx = j + k
            if idx >= len(wc):
                break
            w = wc[idx]
            if a and w and (
                w == a
                or (len(a) >= 4 and (w.startswith(a[:4]) or merged(wc, idx).startswith(a[:4])))
                or (len(w) >= 4 and a.startswith(w[:4]))
            ):
                score += 1
        if score > best_score:
            best_score, best_pos = score, j
        if score == len(anchor):
            break
    return best_pos if best_score >= min(2, len(anchor)) else None


def find_end(
    start: int,
    src_text: str,
    wc: list[str],
    wcat: str,
    wcat_starts: list[int],
    words: list[dict],
    extra: int = 12,
) -> int:
    """Return the best word-array index where src_text ends."""
    src_clean = wclean(src_text)

    if is_cjk(src_clean):
        anchor = src_clean[-4:]
        lo = wcat_starts[start]
        hi = min(lo + len(src_clean) + 30, len(wcat))
        idx = wcat.rfind(anchor, lo, hi)
        if idx == -1:
            return min(start + max(1, len(src_clean) // 2), len(words) - 1)
        return min(max(start, bisect.bisect_right(wcat_starts, idx) - 1), len(words) - 1)

    last_toks = [wclean(w) for w in src_text.split()[-3:] if wclean(w)]
    end_pos = start
    n = len(src_text.split())
    for j in range(start, min(start + n + extra, len(wc))):
        w = wc[j]
        for lw in last_toks:
            if lw and w and (
                w == lw
                or merged(wc, j) == lw
                or (len(lw) >= 4 and (w.startswith(lw[:4]) or lw.startswith(w[:4])))
            ):
                end_pos = j
    return min(end_pos, len(words) - 1)


# ── Timing ─────────────────────────────────────────────────────────────────────

def compute_timings(
    all_sentences: list[dict],
    words: list[dict],
    wc: list[str],
    wcat: str,
    wcat_starts: list[int],
) -> list[tuple[float, float]]:
    timings: list[tuple[float, float]] = []
    search_from = 0
    for entry in all_sentences:
        src = entry.get("src", "")
        pos = find_start(src, search_from, wc, wcat, wcat_starts)
        if pos is not None:
            end_pos = find_end(pos, src, wc, wcat, wcat_starts, words)
            t_s = words[pos]["start"]
            t_e = words[end_pos]["end"]
            if t_e <= t_s:
                t_e = t_s + 0.5
            # Advance search cursor — for CJK advance to end; for English advance to midpoint
            if is_cjk(wclean(src)):
                search_from = max(search_from, end_pos)
            else:
                search_from = max(search_from, pos + max(1, len(src.split()) // 2))
        else:
            t_s = timings[-1][1] if timings else 0
            t_e = t_s + 1.5
        timings.append((t_s, t_e))
    return timings


# ── ASS formatting ─────────────────────────────────────────────────────────────

ASS_HEADER = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ZH,Noto Sans CJK TC,52,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,10,10,62,136
Style: EN,Noto Sans,26,&H00BBBBBB,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,10,10,14,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""

WATERMARK = re.compile(r"amara\.org|subtitles by the|opensubtitles", re.I)

# ASCII sequences inside Chinese lines use Noto Sans at a smaller size so
# Latin glyphs visually match the height of surrounding CJK characters.
_ASCII_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9 \-\.\']*[A-Za-z0-9]|[A-Za-z0-9])")
ZH_EN_FONTSIZE = 50  # Latin embedded in ZH lines (ZH style is 52pt)


def sec_to_ass(s: float) -> str:
    ms = int(round(s * 1000))
    h = ms // 3_600_000; ms %= 3_600_000
    m = ms // 60_000;    ms %= 60_000
    sc = ms // 1000;     ms %= 1000
    return f"{h}:{m:02d}:{sc:02d}.{ms // 10:02d}"


def clean_zh(text: str) -> str:
    text = text.strip()
    text = re.sub(r"[。！？]+$", "", text)
    text = text.replace("——", "—")
    return text



def zh_with_font_tags(text: str) -> str:
    # Process each line segment separately to avoid tagging the \N line-break marker.
    # Use Noto Sans (non-CJK) at a reduced size so Latin glyphs visually match CJK height.
    def _tag(m: re.Match) -> str:
        return f"{{\\fnNoto Sans\\fs{ZH_EN_FONTSIZE}}}{m.group(1)}{{\\fnNoto Sans CJK TC\\fs0}}"
    segments = text.split("\\N")
    tagged = [_ASCII_RE.sub(_tag, seg) for seg in segments]
    return "\\N".join(tagged)


def build_ass(
    all_sentences: list[dict],
    timings: list[tuple[float, float]],
) -> list[str]:
    lines = [ASS_HEADER]
    for idx, entry in enumerate(all_sentences):
        if WATERMARK.search(entry.get("src", "")) or WATERMARK.search(entry.get("tgt", "")):
            continue
        t_s, t_e = timings[idx]

        # Hold time: linger until next subtitle starts (or HOLD_TIME, whichever is sooner)
        next_start = timings[idx + 1][0] if idx + 1 < len(timings) else t_e + HOLD_TIME
        t_e = min(t_e + HOLD_TIME, next_start)

        s = sec_to_ass(t_s)
        e = sec_to_ass(t_e)

        zh = zh_with_font_tags(clean_zh(entry["tgt"]).replace("\n", "\\N"))
        en = entry["src"].strip().replace("\n", "\\N")

        lines.append(f"Dialogue: 0,{s},{e},ZH,,0000,0000,0000,,{zh}")
        lines.append(f"Dialogue: 0,{s},{e},EN,,0000,0000,0000,,{en}")
    return lines


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    tmpdir = sys.argv[1]
    words_json = sys.argv[2]
    input_file = sys.argv[3] if len(sys.argv) > 3 else ""

    words = load_words(words_json)
    all_sentences = load_sentences(tmpdir)

    if not all_sentences:
        print("ERROR: No translation results found.", file=sys.stderr)
        sys.exit(1)

    wc = [wclean(w["word"]) for w in words]
    wcat, wcat_starts = build_index(wc)

    timings = compute_timings(all_sentences, words, wc, wcat, wcat_starts)
    lines = build_ass(all_sentences, timings)

    out = os.path.splitext(input_file)[0] + ".ass" if input_file else os.path.join(tmpdir, "output.ass")
    with open(out, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines) + "\n")

    print(f"ASS 輸出至: {out}")
    print(f"共 {len(all_sentences)} 條字幕")


if __name__ == "__main__":
    main()
