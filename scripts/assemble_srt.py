#!/usr/bin/env python3
"""
Assemble bilingual SRT subtitles from translated batch results.

Usage:
    python scripts/assemble_srt.py <tmpdir> [input_file] [--prefix PREFIX] [--source-lang XX] [--target-lang XX] [--opencc]

Arguments:
    tmpdir      Directory containing translated batch result JSON files
    input_file  Optional: original video/words.json path (determines output .srt filename)
    --prefix    Filename prefix for translated batch files (default: _translated_result)
                Files are expected as <prefix>_0.json, <prefix>_1.json, ...
    --opencc    Optional: apply OpenCC conversion to enhance Chinese translation (s2tw)

Outputs:
    <stem>.<src_ext>.srt  — Source language subtitles
    <stem>.<tgt_ext>.srt  — Target language subtitles
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Final

try:
    import OpenCC

    OPENCC_AVAILABLE = True
except ImportError:
    OPENCC_AVAILABLE = False

sys.path.insert(0, str(Path(__file__).parent.parent / "local"))
from config import SUPPORTED_VIDEO_EXTS

HOLD_TIME = 0.4  # Seconds subtitle lingers after last word ends

LANG_SRT_EXT = {
    "en": "en",
    "zh-TW": "cht",
    "ja": "jp",
}

# ── CJK SRT normalisation ─────────────────────────────────────────────────────
_FWSP = "\u3000"  # 全形空格（與中文字等寬）
_CHT_REMOVE = re.compile(r"[。]")  # full stop — always remove
_CHT_TO_SPC = re.compile(r"[，、；]")  # commas / semicolons → 全形空格
_MULTI_FWSP = re.compile(r"\u3000{2,}")  # collapse consecutive 全形空格


def normalize_cht(text: str) -> str:
    """Apply Chinese SRT formatting conventions (業界慣例).

    - Removes sentence-ending periods (。)
    - Replaces commas and enumeration marks (，、；) with a full-width space (　)
    - Collapses consecutive full-width spaces to one
    - Preserves semantic punctuation: ？！…：《》「」『』〈〉—
    - Strips leading/trailing whitespace (half- and full-width)

    Per-line target: 12–16 chars, hard limit 20 chars (enforced by translation prompt).
    """
    text = _CHT_REMOVE.sub("", text)
    text = _CHT_TO_SPC.sub(_FWSP, text)
    text = _MULTI_FWSP.sub(_FWSP, text)
    return text.strip("\u3000 \t\n")


_JP_REMOVE = re.compile(r"[。]")
_JP_TO_SPC = re.compile(r"[、；]")


def normalize_jp(text: str) -> str:
    """Apply Japanese SRT formatting conventions.

    - Removes sentence-ending periods (。)
    - Replaces enumeration marks (、；) with a full-width space (　)
    - Collapses consecutive full-width spaces to one
    - Preserves semantic punctuation: ？！…《》「」『』〈〉—
    - Strips leading/trailing whitespace (half- and full-width)
    """
    text = _JP_REMOVE.sub("", text)
    text = _JP_TO_SPC.sub(_FWSP, text)
    text = _MULTI_FWSP.sub(_FWSP, text)
    return text.strip("\u3000 \t\n")


LANG_NORMALIZERS = {
    "zh-TW": normalize_cht,
    "ja": normalize_jp,
}


def opencc_convert(text: str, converter) -> str:
    """Apply OpenCC conversion to enhance/normalize Chinese text."""
    if not text:
        return text
    return converter.convert(text)


def load_segments(tmpdir: str, prefix: str = "_translated_result") -> list[dict]:
    """Load all translated batch result files in order."""
    all_segments = []
    i = 0
    while True:
        p = os.path.join(tmpdir, f"{prefix}_{i}.json")
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

    # Parse positional and optional args
    positional = []
    source_lang = "en"
    target_lang = "zh-TW"
    use_opencc = False
    tr_prefix = "_translated_result"
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--source-lang" and i + 1 < len(sys.argv):
            source_lang = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--target-lang" and i + 1 < len(sys.argv):
            target_lang = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--prefix" and i + 1 < len(sys.argv):
            tr_prefix = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--opencc":
            use_opencc = True
            i += 1
        else:
            positional.append(sys.argv[i])
            i += 1

    tmpdir = positional[0]
    input_file = positional[1] if len(positional) > 1 else ""

    segments = load_segments(tmpdir, tr_prefix)

    if not segments:
        print("ERROR: No translated results found.", file=sys.stderr)
        sys.exit(1)

    # Initialize OpenCC converter if requested
    opencc_converter = None
    if use_opencc:
        if not OPENCC_AVAILABLE:
            print(
                "WARNING: OpenCC not installed. Install with: pip install OpenCC",
                file=sys.stderr,
            )
        else:
            opencc_converter = OpenCC.OpenCC("s2tw")
            print("Using OpenCC (Simplified → Traditional Taiwan) for enhancement")

    # Determine output stem
    if input_file:
        stem = input_file
        extensions = [f".{ext}" for ext in SUPPORTED_VIDEO_EXTS] + [".words.json"]
        for ext in extensions:
            if stem.endswith(ext):
                stem = stem[: -len(ext)]
                break
        else:
            stem = os.path.splitext(stem)[0]
    else:
        stem = os.path.join(tmpdir, "output")

    src_ext = LANG_SRT_EXT.get(source_lang, source_lang)
    tgt_ext = LANG_SRT_EXT.get(target_lang, target_lang)

    src_out = stem + f".{src_ext}.srt"
    tgt_out = stem + f".{tgt_ext}.srt"

    def enhanced_normalize(text: str) -> str:
        text = (tgt_normalizer or (lambda x: x))(text)
        if opencc_converter and text:
            text = opencc_convert(text, opencc_converter)
        return text

    tgt_normalizer = LANG_NORMALIZERS.get(target_lang)

    src_content, src_count = build_srt(segments, "src")
    tgt_content, tgt_count = build_srt(segments, "tgt", normalize=enhanced_normalize)

    with open(src_out, "w", encoding="utf-8") as f:
        f.write(src_content)

    with open(tgt_out, "w", encoding="utf-8") as f:
        f.write(tgt_content)

    src_label = src_ext.upper()
    tgt_label = tgt_ext.upper()
    print(f"{src_label}  SRT → {src_out}  （{src_count} 條）")
    print(f"{tgt_label} SRT → {tgt_out}  （{tgt_count} 條）")


if __name__ == "__main__":
    main()
