#!/usr/bin/env python3
"""
本地字幕 Pipeline（分句 + 翻譯 + 組裝 SRT）

Usage:
    .venv/bin/python local/run.py <影片或 words.json> [--opencc]

Options:
    --opencc    使用 OpenCC 增強中文翻譯（簡體→繁體）

Examples:
    .venv/bin/python local/run.py input/video.mp4
    .venv/bin/python local/run.py output/video.words.json
    .venv/bin/python local/run.py input/video.mp4 --opencc
"""

import glob
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Final

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

LOCAL_DIR = PROJECT_ROOT / "local"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
TMP_DIR = Path(tempfile.gettempdir())

# ── Constants ─────────────────────────────────────────────────────────────────
# Common capitalized words that don't need to be listed
_COMMON_CAPS: Final[frozenset[str]] = frozenset(
    {
        "i",
        "i'm",
        "i've",
        "i'll",
        "i'd",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "english",
        "chinese",
        "japanese",
        "french",
        "german",
        "dutch",
        "spanish",
        "american",
        "european",
        "british",
        "yes",
        "no",
        "ok",
        "okay",
    }
)

sys.path.insert(0, str(LOCAL_DIR))
from config import (
    SEGMENT_MODEL,
    TRANSLATE_MODEL,
    TRANSLATE_SOURCE_LANG,
    TRANSLATE_TARGET_LANG,
    USE_OPENCC,
    SUPPORTED_VIDEO_EXTS,
)


def run(cmd: list) -> None:
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)


def validate_input_path(path: Path) -> Path:
    """Validate and resolve input path, preventing path traversal."""
    resolved = path.resolve()

    allowed_parents = [PROJECT_ROOT, INPUT_DIR, OUTPUT_DIR]
    if not any(resolved.is_relative_to(p) for p in allowed_parents):
        raise ValueError(f"Path not allowed: {path}")

    return resolved


def resolve_words_json(input_file: Path) -> Path:
    """Return the words.json path, transcribing first if needed."""
    if input_file.name.endswith(".words.json"):
        return input_file

    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    from generate_subtitles import validate_filename

    safe_stem = validate_filename(input_file.stem)
    words_json = OUTPUT_DIR / f"{safe_stem}.words.json"
    if words_json.exists():
        return words_json

    print(f"  words.json 不存在，開始轉錄 {input_file.name} ...")
    run(
        [
            PYTHON,
            str(SCRIPTS_DIR / "generate_subtitles.py"),
            "--file",
            str(input_file),
            "--output",
            str(OUTPUT_DIR),
        ]
    )
    return words_json


def resolve_video_path(input_path: Path) -> Path:
    """Return the video file path for SRT output location."""
    if not input_path.name.endswith(".words.json"):
        return input_path

    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    from generate_subtitles import validate_filename

    stem = validate_filename(input_path.name[: -len(".words.json")])
    for ext in SUPPORTED_VIDEO_EXTS:
        candidate = INPUT_DIR / f"{stem}.{ext}"
        if candidate.exists():
            return candidate
    return input_path


def backup_file(path: Path) -> Path:
    """Create timestamped backup of a file."""
    if not path.exists():
        return path

    ts = int(time.time() * 1000)
    rnd = random.randint(0, 999)
    backup_path = path.with_suffix(path.suffix + f".bak.{ts}{rnd:03d}")
    shutil.copy2(path, backup_path)
    return backup_path


def fix_words_json(words_json: Path) -> None:
    """Apply glossary corrections to words.json with backup."""
    from glossary import load_corrections

    corrections = load_corrections()
    if not corrections:
        return

    # Create backup before modification
    backup_path = backup_file(words_json)
    if backup_path != words_json:
        print(f"  Backup: {backup_path.name}")

    # Build case-insensitive lookup
    lookup = {k.lower(): v for k, v in corrections.items()}

    with open(words_json, encoding="utf-8") as f:
        words = json.load(f)

    fixed = 0
    for entry in words:
        stripped = entry["word"].strip()
        if stripped.lower() in lookup:
            correct = lookup[stripped.lower()]
            leading = len(entry["word"]) - len(entry["word"].lstrip())
            trailing = len(entry["word"]) - len(entry["word"].rstrip())
            entry["word"] = (
                entry["word"][:leading]
                + correct
                + (entry["word"][len(entry["word"]) - trailing :] if trailing else "")
            )
            fixed += 1

    if fixed:
        with open(words_json, "w", encoding="utf-8") as f:
            json.dump(words, f, ensure_ascii=False, indent=2)
        print(f"  詞條修正：{fixed} 處")
    else:
        # No changes, remove backup
        if backup_path != words_json:
            backup_path.unlink(missing_ok=True)


# 常見不需列出的大寫詞


def detect_proper_nouns(tmp_dir: Path) -> list[str]:
    """Scan translated segments for mid-sentence capitalized words."""
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
            if (
                clean[0].isupper()
                and clean.lower() not in _COMMON_CAPS
                and clean.lower() not in known
            ):
                counts[clean] = counts.get(clean, 0) + 1

    return sorted(counts, key=lambda x: -counts[x])


def glossary_review(candidates: list[str]) -> None:
    """Show detected proper nouns and save to file for later review."""
    print_section("專有名詞校對")

    if not candidates:
        print("  未偵測到新的專有名詞\n")
        return

    # Write candidates to a separate file for later review
    candidates_file = LOCAL_DIR / "glossary_candidates.txt"
    with open(candidates_file, "w", encoding="utf-8") as f:
        f.write("# 候選專有名詞（請手動審核後移至 glossary.txt）\n")
        f.write("# 格式：\n")
        f.write("#   詞彙         → 加入翻譯保留清單\n")
        f.write("#   錯誤->正確    → 修正拼寫\n")
        f.write("#   # 詞彙        → 忽略（維持註解狀態）\n")
        f.write("#\n")
        for term in candidates:
            f.write(f"# {term}\n")

    print(f"  已儲存候選清單至：{candidates_file.name}")
    print(f"  共 {len(candidates)} 個候選詞彙\n")

    print("  以下詞彙可能是專有名詞（未在 glossary.txt 中）：\n")
    for term in candidates:
        print(f"    {term}")

    glossary_path = LOCAL_DIR / "glossary.txt"
    print(f"\n  如需確認，請在 {glossary_path} 中加入：")
    print("    正確詞：直接加一行（加入翻譯保留清單）")
    print("    拼寫修正：用「錯誤->正確」格式（下次自動修正）")
    print(f"\n  或直接編輯 {candidates_file.name} 後，複製到 glossary.txt")
    print()

    try:
        ans = (
            input("  要現在開啟 glossary_candidates.txt 編輯嗎？[y/N]: ")
            .strip()
            .lower()
        )
    except (EOFError, KeyboardInterrupt):
        ans = ""

    if ans == "y":
        subprocess.run(["open", str(candidates_file)])
    print()


def cleanup_tmp() -> None:
    for pattern in ("_segments_result_*.json", "_translated_result_*.json"):
        for f in glob.glob(str(TMP_DIR / pattern)):
            os.remove(f)


def print_section(title: str) -> None:
    print(f"\n── {title} {'─' * (44 - len(title))}")


def parse_arguments() -> tuple[Path, str, str, bool]:
    """Parse command line arguments and return (input_path, source_lang, target_lang, use_opencc)."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    positional = []
    source_lang = TRANSLATE_SOURCE_LANG
    target_lang = TRANSLATE_TARGET_LANG
    use_opencc = USE_OPENCC
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--source-lang" and i + 1 < len(sys.argv):
            source_lang = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--target-lang" and i + 1 < len(sys.argv):
            target_lang = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--opencc":
            use_opencc = True
            i += 1
        else:
            positional.append(sys.argv[i])
            i += 1

    return (
        validate_input_path(Path(positional[0])),
        source_lang,
        target_lang,
        use_opencc,
    )


def main() -> None:
    input_path, source_lang, target_lang, use_opencc = parse_arguments()

    # Clean up any stale temp files
    cleanup_tmp()

    # Resolve words.json (transcribe if needed)
    words_json = resolve_words_json(input_path)

    # Resolve video path for SRT output location
    srt_base_path = resolve_video_path(input_path)

    print(f"\n  輸入：{words_json.name}")

    # Apply glossary corrections (with backup)
    fix_words_json(words_json)

    # Step A: segmentation
    print_section(f"Step A：分句（{SEGMENT_MODEL}）")
    run([PYTHON, str(LOCAL_DIR / "segment.py"), str(words_json), str(TMP_DIR)])

    # Step B: translation
    print_section(f"Step B：翻譯（{TRANSLATE_MODEL}）")
    run(
        [
            PYTHON,
            str(LOCAL_DIR / "translate.py"),
            str(TMP_DIR),
            str(TMP_DIR),
            "--source-lang",
            source_lang,
            "--target-lang",
            target_lang,
        ]
    )

    # Assemble SRT
    print_section("組裝 SRT")
    assemble_cmd = [
        PYTHON,
        str(SCRIPTS_DIR / "assemble_srt.py"),
        str(TMP_DIR),
        str(srt_base_path),
        "--source-lang",
        source_lang,
        "--target-lang",
        target_lang,
    ]
    if use_opencc:
        assemble_cmd.append("--opencc")
    run(assemble_cmd)

    # Detect proper nouns before cleanup
    candidates = detect_proper_nouns(TMP_DIR)

    cleanup_tmp()

    print("\n  完成")
    glossary_review(candidates)


if __name__ == "__main__":
    main()
