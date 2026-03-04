#!/usr/bin/env python3
"""
Assemble bilingual SRT subtitles from translated batch results.

Usage:
    python scripts/assemble_srt.py <tmpdir> [input_file]

Arguments:
    tmpdir      Directory containing _translated_result_0.json, _translated_result_1.json, ...
    input_file  Optional: original video/words.json path (determines output .srt filename)

Outputs:
    <stem>.en.srt   — English source subtitles
    <stem>.cht.srt  — Traditional Chinese translated subtitles
"""

import json
import os
import re
import sys

HOLD_TIME = 0.4  # Seconds subtitle lingers after last word ends

# ── Chinese SRT normalisation ──────────────────────────────────────────────────
_CHT_REMOVE  = re.compile(r'[。]')          # full stop — always remove
_CHT_TO_SPC  = re.compile(r'[，、；]')      # commas / semicolons → space
_MULTI_SPC   = re.compile(r'  +')           # collapse multiple spaces


def normalize_cht(text: str) -> str:
    """Apply Chinese SRT formatting conventions.

    - Removes sentence-ending periods (。)
    - Replaces commas and enumeration marks (，、；) with a half-width space
    - Preserves semantic punctuation: ？！…：《》「」『』〈〉—
    - Collapses multiple spaces and strips leading/trailing whitespace
    """
    text = _CHT_REMOVE.sub('', text)
    text = _CHT_TO_SPC.sub(' ', text)
    text = _MULTI_SPC.sub(' ', text).strip()
    return text


def load_segments(tmpdir: str) -> list[dict]:
    """Load all translated batch result files in order."""
    all_segments = []
    i = 0
    while True:
        p = os.path.join(tmpdir, f"_translated_result_{i}.json")
        if not os.path.exists(p):
            break
        with open(p, encoding="utf-8") as f:
            segments = json.load(f)
        all_segments.extend(segments)
        i += 1
    return all_segments


def sec_to_srt(s: float) -> str:
    ms = int(round(s * 1000))
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    sc = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{sc:02d},{ms:03d}"


def build_srt(segments: list[dict], text_key: str, normalize=None) -> tuple[str, int]:
    """Return (srt_content, actual_entry_count).

    normalize: optional callable applied to each text entry (e.g. normalize_cht).
    """
    lines = []
    counter = 1
    n = len(segments)
    for idx, entry in enumerate(segments):
        text = entry.get(text_key, "").strip()
        if normalize:
            text = normalize(text)
        if not text:
            continue
        t_s = entry["start"]
        t_e = entry["end"]

        # Hold time: linger until next subtitle starts (or HOLD_TIME, whichever is sooner)
        next_start = segments[idx + 1]["start"] if idx + 1 < n else t_e + HOLD_TIME
        t_e = min(t_e + HOLD_TIME, next_start)

        lines.append(str(counter))
        lines.append(f"{sec_to_srt(t_s)} --> {sec_to_srt(t_e)}")
        lines.append(text)
        lines.append("")
        counter += 1
    return "\n".join(lines), counter - 1


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    tmpdir = sys.argv[1]
    input_file = sys.argv[2] if len(sys.argv) > 2 else ""

    segments = load_segments(tmpdir)

    if not segments:
        print("ERROR: No translated results found.", file=sys.stderr)
        sys.exit(1)

    # Determine output stem
    if input_file:
        stem = input_file
        for ext in (".mp4", ".mkv", ".mov", ".avi", ".m4v", ".words.json"):
            if stem.endswith(ext):
                stem = stem[: -len(ext)]
                break
        else:
            stem = os.path.splitext(stem)[0]
    else:
        stem = os.path.join(tmpdir, "output")

    en_out = stem + ".en.srt"
    cht_out = stem + ".cht.srt"

    en_content, en_count = build_srt(segments, "src")
    cht_content, cht_count = build_srt(segments, "tgt", normalize=normalize_cht)

    with open(en_out, "w", encoding="utf-8") as f:
        f.write(en_content)

    with open(cht_out, "w", encoding="utf-8") as f:
        f.write(cht_content)

    print(f"EN  SRT → {en_out}  （{en_count} 條）")
    print(f"CHT SRT → {cht_out}  （{cht_count} 條）")


if __name__ == "__main__":
    main()
