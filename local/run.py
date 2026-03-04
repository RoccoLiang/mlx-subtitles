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
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON  = PROJECT_ROOT / ".venv" / "bin" / "python"
PYTHON       = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

LOCAL_DIR    = PROJECT_ROOT / "local"
SCRIPTS_DIR  = PROJECT_ROOT / "scripts"
OUTPUT_DIR   = PROJECT_ROOT / "output"
TMP_DIR      = Path("/tmp")


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


def fix_words_json(words_json: Path) -> None:
    """Apply glossary corrections to words.json (in-place)."""
    sys.path.insert(0, str(LOCAL_DIR))
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
            entry["word"] = entry["word"].replace(stripped, correct)
            fixed += 1

    if fixed:
        with open(words_json, "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False, indent=2)
        print(f"  詞條修正：{fixed} 處")


def cleanup_tmp() -> None:
    for pattern in ("_segments_result_*.json", "_translated_result_*.json"):
        for f in glob.glob(str(TMP_DIR / pattern)):
            os.remove(f)


def print_section(title: str) -> None:
    print(f"\n── {title} {'─' * (44 - len(title))}")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if "--help" in sys.argv else 1)

    input_path = Path(sys.argv[1])
    if not input_path.is_absolute():
        input_path = PROJECT_ROOT / input_path

    if not input_path.exists():
        print(f"ERROR: 找不到檔案：{input_path}", file=sys.stderr)
        sys.exit(1)

    words_json = resolve_words_json(input_path)

    print(f"\n  輸入：{words_json.name}")

    # Glossary post-processing: fix known misspellings in words.json
    fix_words_json(words_json)

    # Step A: segmentation
    print_section("Step A：分句（Gemma 3 27B）")
    run([PYTHON, str(LOCAL_DIR / "segment.py"), str(words_json), str(TMP_DIR)])

    # Step B: translation
    print_section("Step B：翻譯（TranslateGemma 27B）")
    run([PYTHON, str(LOCAL_DIR / "translate.py"), str(TMP_DIR), str(TMP_DIR)])

    # Assemble SRT
    print_section("組裝 SRT")
    run([PYTHON, str(SCRIPTS_DIR / "assemble_srt.py"), str(TMP_DIR), str(input_path)])

    cleanup_tmp()
    print("\n  完成\n")


if __name__ == "__main__":
    main()
