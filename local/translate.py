#!/usr/bin/env python3
"""
Step B: Translate subtitle segments via LM Studio.

Usage:
    python local/translate.py <segments_dir> [output_dir] [--source-lang XX] [--target-lang XX]

Reads:  <segments_dir>/_segments_result_*.json
Writes: <output_dir>/_translated_result_*.json
"""

import json
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not found. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    LMSTUDIO_BASE_URL,
    TRANSLATE_MODEL,
    TRANSLATE_USE_NATIVE,
    TRANSLATE_SOURCE_LANG,
    TRANSLATE_TARGET_LANG,
    TRANSLATE_CHAT_BATCH_SIZE,
    TRANSLATE_MAX_TOKENS,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_BACKOFF_BASE,
    MIN_SUCCESS_RATE,
    validate_lmstudio_url,
)
from glossary import as_keep_list

LANG_LABELS = {
    "en": "English",
    "zh-TW": "Traditional Chinese (Taiwan)",
    "ja": "Japanese",
}

LANG_STYLE_HINTS = {
    "zh-TW": (
        "Use natural spoken style. Each line should be 12–16 Chinese characters, hard limit 20; max 2 lines per entry.\n"
        "Chinese SRT punctuation rules: no period (。) at line end; no commas (，) mid-line — replace with a full-width space (　); keep ？！…《》 only when semantically necessary.\n"
    ),
    "ja": (
        "Use natural spoken Japanese. Each line should be 12–20 characters, hard limit 24; max 2 lines per entry.\n"
        "Japanese SRT punctuation rules: no period (。) at line end; no commas (、) mid-line — replace with a full-width space (　); keep ？！…《》「」 only when semantically necessary.\n"
    ),
}


def _call(payload: dict) -> str:
    validate_lmstudio_url()  # Lazy validation on first API call
    url = f"{LMSTUDIO_BASE_URL}/chat/completions"
    try:
        resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        if not resp.ok:
            raise RuntimeError(f"API error {resp.status_code}: {resp.text[:400]}")
        data = resp.json()

        if not data.get("choices"):
            raise ValueError("API response missing 'choices'")
        content = data["choices"][0].get("message", {}).get("content", "").strip()
        if not content:
            raise ValueError("API response has empty content")
        return content
    except requests.exceptions.Timeout:
        raise TimeoutError(f"API request timed out after {REQUEST_TIMEOUT}s")
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"API request failed: {e}")


def translate_native(text: str) -> str:
    """TranslateGemma structured content format (one segment per call)."""
    return _call(
        {
            "model": TRANSLATE_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "source_lang_code": TRANSLATE_SOURCE_LANG,
                            "target_lang_code": TRANSLATE_TARGET_LANG,
                            "text": text,
                        }
                    ],
                }
            ],
            "temperature": 0.2,
            "max_tokens": TRANSLATE_MAX_TOKENS,
        }
    )


def translate_chat_batch(
    segments: list[dict], source_lang: str, target_lang: str
) -> list[str]:
    """Standard chat format — translate a batch as a numbered list."""
    lines = [f"{i + 1}. {seg['src']}" for i, seg in enumerate(segments)]
    keep = as_keep_list()
    keep_line = f"{keep}\n" if keep else ""
    src_label = LANG_LABELS.get(source_lang, source_lang)
    tgt_label = LANG_LABELS.get(target_lang, target_lang)
    style_hint = LANG_STYLE_HINTS.get(target_lang, "")
    prompt = (
        f"Translate each numbered line from {src_label} to {tgt_label}.\n"
        "Keep English proper nouns, brand names, and technical terms unchanged.\n"
        f"{keep_line}"
        f"{style_hint}"
        "Return ONLY the numbered translations.\n\n" + "\n".join(lines)
    )
    content = _call(
        {
            "model": TRANSLATE_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": TRANSLATE_MAX_TOKENS,
        }
    )
    result: dict[int, str] = {}
    for line in content.splitlines():
        m = re.match(r"^(\d+)[.)]\s*(.+)$", line.strip())
        if m:
            result[int(m.group(1))] = m.group(2).strip()
    return [result.get(i + 1, "") for i in range(len(segments))]


def translate_one(text: str, max_retries: int = MAX_RETRIES) -> str:
    last_err = None
    for attempt in range(max_retries):
        try:
            return translate_native(text)
        except (ValueError, TimeoutError, ConnectionError) as e:
            last_err = e
            if attempt < max_retries - 1:
                wait_time = RETRY_BACKOFF_BASE**attempt
                print(
                    f"(retry {attempt + 1}, wait {wait_time}s)...", end=" ", flush=True
                )
                time.sleep(wait_time)
    raise RuntimeError(f"Translation failed: {last_err}")


def load_segments(segments_dir: Path) -> list[dict]:
    all_segments = []
    i = 0
    while True:
        p = segments_dir / f"_segments_result_{i}.json"
        if not p.exists():
            break
        with open(p, encoding="utf-8") as f:
            all_segments.extend(json.load(f))
        i += 1
    return all_segments


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # Parse positional and optional args
    positional = []
    source_lang = TRANSLATE_SOURCE_LANG
    target_lang = TRANSLATE_TARGET_LANG
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--source-lang" and i + 1 < len(sys.argv):
            source_lang = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--target-lang" and i + 1 < len(sys.argv):
            target_lang = sys.argv[i + 1]
            i += 2
        else:
            positional.append(sys.argv[i])
            i += 1

    segments_dir = Path(positional[0]).resolve()
    output_dir = Path(positional[1]) if len(positional) > 1 else segments_dir

    segments = load_segments(segments_dir)
    if not segments:
        print("ERROR: No _segments_result_*.json found in directory.", file=sys.stderr)
        sys.exit(1)

    total = len(segments)
    mode = (
        "TranslateGemma native (1 call/segment)"
        if TRANSLATE_USE_NATIVE
        else f"chat batch ({TRANSLATE_CHAT_BATCH_SIZE}/call)"
    )
    print(f"  Segments: {total}  |  Model: {TRANSLATE_MODEL}  |  Mode: {mode}")
    print(f"  {source_lang} → {target_lang}\n")

    results = []

    if TRANSLATE_USE_NATIVE:
        for i, seg in enumerate(segments):
            print(f"  [{i + 1}/{total}] {seg['src'][:55]}... ", end="", flush=True)
            tgt = translate_one(seg["src"])
            print(tgt[:40])
            results.append(
                {
                    "src": seg["src"],
                    "tgt": tgt,
                    "start": seg["start"],
                    "end": seg["end"],
                }
            )
    else:
        for offset in range(0, total, TRANSLATE_CHAT_BATCH_SIZE):
            batch = segments[offset : offset + TRANSLATE_CHAT_BATCH_SIZE]
            end_idx = offset + len(batch) - 1
            print(f"  Batch (segments {offset}–{end_idx})...", end=" ", flush=True)

            last_err = None
            translations = []
            success = False
            for attempt in range(MAX_RETRIES):
                try:
                    translations = translate_chat_batch(batch, source_lang, target_lang)
                    filled = sum(1 for t in translations if t)
                    if filled < len(batch) * MIN_SUCCESS_RATE:
                        raise ValueError(f"Only {filled}/{len(batch)} parsed")
                    success = True
                    break
                except (ValueError, TimeoutError, ConnectionError) as e:
                    last_err = e
                    if attempt < MAX_RETRIES - 1:
                        wait_time = RETRY_BACKOFF_BASE**attempt
                        print(
                            f"(retry {attempt + 1}, wait {wait_time}s)...",
                            end=" ",
                            flush=True,
                        )
                        time.sleep(wait_time)
            if not success:
                raise RuntimeError(f"Batch failed: {last_err}")

            print("done")
            for seg, tgt in zip(batch, translations):
                results.append(
                    {
                        "src": seg["src"],
                        "tgt": tgt,
                        "start": seg["start"],
                        "end": seg["end"],
                    }
                )

    out_path = output_dir / "_translated_result_0.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\n  Step B done: {total} segments → {out_path}")


if __name__ == "__main__":
    main()
