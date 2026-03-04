#!/usr/bin/env python3
"""
本地字幕 Pipeline（分句 + 翻譯 + 組裝 SRT）

Usage:
    .venv/bin/python local/run.py <影片或 words.json>

Examples:
    .venv/bin/python local/run.py input/video.mp4
    .venv/bin/python local/run.py output/video.words.json
"""

import glob
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON  = PROJECT_ROOT / ".venv" / "bin" / "python"
PYTHON       = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

LOCAL_DIR    = PROJECT_ROOT / "local"
SCRIPTS_DIR  = PROJECT_ROOT / "scripts"
INPUT_DIR    = PROJECT_ROOT / "input"
OUTPUT_DIR   = PROJECT_ROOT / "output"
TMP_DIR      = Path(tempfile.gettempdir())

sys.path.insert(0, str(LOCAL_DIR))
from config import SEGMENT_MODEL, TRANSLATE_MODEL


def run(cmd: list) -> None:
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)


def resolve_words_json(input_file: Path) -> Path:
    """Return the words.json path, transcribing first if needed."""
    if input_file.name.endswith(".words.json"):
        return input_file

    words_json = OUTPUT_DIR / f"{input_file.stem}.words.json"
    if words_json.exists():
        return words_json

    print(f"  words.json 不存在，開始轉錄 {input_file.name} ...")
    run([PYTHON, str(SCRIPTS_DIR / "generate_subtitles.py"),
         "--file", str(input_file),
         "--output", str(OUTPUT_DIR)])
    return words_json


_VIDEO_EXTS = ("mp4", "mov", "mkv", "avi", "m4v", "webm", "flv", "wmv")


def resolve_video_path(input_path: Path) -> Path:
    """Return the video file path to use as the SRT output base.

    If input is already a video file, return it directly.
    If input is a words.json, look for the corresponding video in input/.
    Falls back to input_path if no matching video is found.
    """
    if not input_path.name.endswith(".words.json"):
        return input_path  # already a video

    stem = input_path.name[: -len(".words.json")]  # e.g. "video" from "video.words.json"
    for ext in _VIDEO_EXTS:
        candidate = INPUT_DIR / f"{stem}.{ext}"
        if candidate.exists():
            return candidate
    return input_path  # fallback: output next to words.json


def fix_words_json(words_json: Path) -> None:
    """Apply glossary corrections to words.json (in-place)."""
    from glossary import load_corrections
    corrections = load_corrections()
    if not corrections:
        return

    # Build case-insensitive lookup: lower(wrong) → correct
    lookup = {k.lower(): v for k, v in corrections.items()}

    with open(words_json, encoding="utf-8") as f:
        words = json.load(f)

    fixed = 0
    for entry in words:
        stripped = entry["word"].strip()
        if stripped.lower() in lookup:
            correct = lookup[stripped.lower()]
            # Preserve leading/trailing whitespace from original
            leading = len(entry["word"]) - len(entry["word"].lstrip())
            trailing = len(entry["word"]) - len(entry["word"].rstrip())
            entry["word"] = entry["word"][:leading] + correct + (entry["word"][len(entry["word"]) - trailing:] if trailing else "")
            fixed += 1

    if fixed:
        with open(words_json, "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False, indent=2)
        print(f"  詞條修正：{fixed} 處")


# 常見不需列出的大寫詞
_COMMON_CAPS = {
    "i", "i'm", "i've", "i'll", "i'd",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    "english", "chinese", "japanese", "french", "german", "dutch", "spanish",
    "american", "european", "british", "yes", "no", "ok", "okay",
}


def detect_proper_nouns(tmp_dir: Path) -> list[str]:
    """Scan translated segments for mid-sentence capitalized words not in glossary."""
    results = []
    i = 0
    while True:
        p = tmp_dir / f"_translated_result_{i}.json"
        if not p.exists():
            break
        with open(p, encoding="utf-8") as f:
            results.extend(json.load(f))
        i += 1
    if not results:
        return []

    from glossary import load_terms, load_corrections
    known = {t.lower() for t in load_terms()}
    known |= {v.lower() for v in load_corrections().values()}

    counts: dict[str, int] = {}
    for seg in results:
        words_in_seg = seg.get("src", "").split()
        for word_idx, word in enumerate(words_in_seg):
            clean = re.sub(r"[^a-zA-Z'&-]", "", word)
            if len(clean) < 2 or word_idx == 0:
                continue
            if clean[0].isupper() and clean.lower() not in _COMMON_CAPS and clean.lower() not in known:
                counts[clean] = counts.get(clean, 0) + 1

    return sorted(counts, key=lambda x: -counts[x])


def glossary_review(candidates: list[str]) -> None:
    """Show detected proper nouns and offer to open glossary.txt for editing."""
    print_section("專有名詞校對")

    if not candidates:
        print("  未偵測到新的專有名詞\n")
        return

    print("  以下詞彙可能是專有名詞（未在 glossary.txt 中）：\n")
    for term in candidates[:30]:
        print(f"    {term}")
    if len(candidates) > 30:
        print(f"    … 共 {len(candidates)} 個")

    glossary_path = LOCAL_DIR / "glossary.txt"
    print(f"\n  如需修正拼寫，請在 {glossary_path} 中加入：")
    print("    正確詞：直接加一行（加入翻譯保留清單）")
    print("    拼寫修正：用「錯誤->正確」格式（下次自動修正）")
    print()

    try:
        ans = input("  要現在開啟 glossary.txt 編輯嗎？[y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""

    if ans == "y":
        subprocess.run(["open", str(glossary_path)])
    print()


def cleanup_tmp() -> None:
    for pattern in ("_segments_result_*.json", "_translated_result_*.json"):
        for f in glob.glob(str(TMP_DIR / pattern)):
            os.remove(f)


def print_section(title: str) -> None:
    print(f"\n── {title} {'─' * (44 - len(title))}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    input_path = Path(sys.argv[1])
    if not input_path.is_absolute():
        input_path = PROJECT_ROOT / input_path

    if not input_path.exists():
        print(f"ERROR: 找不到檔案：{input_path}", file=sys.stderr)
        sys.exit(1)

    # Clean up any stale temp files from a previous interrupted run
    cleanup_tmp()

    words_json = resolve_words_json(input_path)

    # Resolve the video file for SRT output location:
    # Always output .en.srt / .cht.srt next to the video in input/
    srt_base_path = resolve_video_path(input_path)

    print(f"\n  輸入：{words_json.name}")

    # Glossary post-processing: fix known misspellings in words.json
    fix_words_json(words_json)

    # Step A: segmentation
    print_section(f"Step A：分句（{SEGMENT_MODEL}）")
    run([PYTHON, str(LOCAL_DIR / "segment.py"), str(words_json), str(TMP_DIR)])

    # Step B: translation
    print_section(f"Step B：翻譯（{TRANSLATE_MODEL}）")
    run([PYTHON, str(LOCAL_DIR / "translate.py"), str(TMP_DIR), str(TMP_DIR)])

    # Assemble SRT
    print_section("組裝 SRT")
    run([PYTHON, str(SCRIPTS_DIR / "assemble_srt.py"), str(TMP_DIR), str(srt_base_path)])

    # Detect proper nouns before cleanup
    candidates = detect_proper_nouns(TMP_DIR)

    cleanup_tmp()

    print("\n  完成")
    glossary_review(candidates)


if __name__ == "__main__":
    main()
