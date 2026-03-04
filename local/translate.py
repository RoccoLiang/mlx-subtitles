#!/usr/bin/env python3
"""
Step B: Translate subtitle segments via LM Studio (TranslateGemma 27B).

Usage:
    python local/translate.py <segments_dir> [output_dir]

Reads:  <segments_dir>/_segments_result_*.json
Writes: <output_dir>/_translated_result_*.json
"""

import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not found. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    LMSTUDIO_BASE_URL, TRANSLATE_MODEL, TRANSLATE_USE_NATIVE,
    TRANSLATE_SOURCE_LANG, TRANSLATE_TARGET_LANG,
    TRANSLATE_CHAT_BATCH_SIZE, TRANSLATE_MAX_TOKENS, REQUEST_TIMEOUT,
)
from glossary import as_keep_list


def _call(payload: dict) -> str:
    url = f"{LMSTUDIO_BASE_URL}/chat/completions"
    resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
    if not resp.ok:
        raise RuntimeError(f"API error {resp.status_code}: {resp.text[:400]}")
    return resp.json()["choices"][0]["message"]["content"].strip()


def translate_native(text: str) -> str:
    """TranslateGemma structured content format (one segment per call)."""
    return _call({
        "model": TRANSLATE_MODEL,
        "messages": [{
            "role": "user",
            "content": [{
                "type": "text",
                "source_lang_code": TRANSLATE_SOURCE_LANG,
                "target_lang_code": TRANSLATE_TARGET_LANG,
                "text": text,
            }],
        }],
        "temperature": 0.2,
        "max_tokens": TRANSLATE_MAX_TOKENS,
    })


def translate_chat_batch(segments: list[dict]) -> list[str]:
    """Standard chat format — translate a batch as a numbered list."""
    import re
    lines = [f"{i + 1}. {seg['src']}" for i, seg in enumerate(segments)]
    keep = as_keep_list()
    keep_line = f"{keep}\n" if keep else ""
    prompt = (
        f"Translate each numbered line from {TRANSLATE_SOURCE_LANG} to Traditional Chinese (Taiwan).\n"
        "Keep English proper nouns, brand names, and technical terms unchanged.\n"
        f"{keep_line}"
        "Use natural spoken style. Return ONLY the numbered translations.\n\n"
        + "\n".join(lines)
    )
    content = _call({
        "model": TRANSLATE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": TRANSLATE_MAX_TOKENS,
    })
    result: dict[int, str] = {}
    for line in content.splitlines():
        m = re.match(r"^(\d+)[.)]\s*(.+)$", line.strip())
        if m:
            result[int(m.group(1))] = m.group(2).strip()
    return [result.get(i + 1, "") for i in range(len(segments))]


def translate_one(text: str, max_retries: int = 2) -> str:
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            return translate_native(text)
        except Exception as e:
            last_err = e
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

    segments_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else segments_dir

    segments = load_segments(segments_dir)
    if not segments:
        print("ERROR: No _segments_result_*.json found in directory.", file=sys.stderr)
        sys.exit(1)

    total = len(segments)
    mode = "TranslateGemma native (1 call/segment)" if TRANSLATE_USE_NATIVE else f"chat batch ({TRANSLATE_CHAT_BATCH_SIZE}/call)"
    print(f"  Segments: {total}  |  Model: {TRANSLATE_MODEL}  |  Mode: {mode}")
    print(f"  {TRANSLATE_SOURCE_LANG} → {TRANSLATE_TARGET_LANG}\n")

    results = []

    if TRANSLATE_USE_NATIVE:
        for i, seg in enumerate(segments):
            print(f"  [{i + 1}/{total}] {seg['src'][:55]}... ", end="", flush=True)
            tgt = translate_one(seg["src"])
            print(tgt[:40])
            results.append({"src": seg["src"], "tgt": tgt, "start": seg["start"], "end": seg["end"]})
    else:
        for offset in range(0, total, TRANSLATE_CHAT_BATCH_SIZE):
            batch = segments[offset: offset + TRANSLATE_CHAT_BATCH_SIZE]
            end_idx = offset + len(batch) - 1
            print(f"  Batch (segments {offset}–{end_idx})...", end=" ", flush=True)

            last_err = None
            translations = None
            success = False
            for attempt in range(3):
                try:
                    translations = translate_chat_batch(batch)
                    filled = sum(1 for t in translations if t)
                    if filled < len(batch) * 0.8:
                        raise ValueError(f"Only {filled}/{len(batch)} parsed")
                    success = True
                    break
                except Exception as e:
                    last_err = e
                    if attempt < 2:
                        print(f"(retry {attempt + 1})...", end=" ", flush=True)
            if not success:
                raise RuntimeError(f"Batch failed: {last_err}")

            print("done")
            for seg, tgt in zip(batch, translations):
                results.append({"src": seg["src"], "tgt": tgt, "start": seg["start"], "end": seg["end"]})

    out_path = output_dir / "_translated_result_0.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n  Step B done: {total} segments → {out_path}")


if __name__ == "__main__":
    main()
