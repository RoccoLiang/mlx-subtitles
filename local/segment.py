#!/usr/bin/env python3
"""
Step A: Segment words.json into subtitle segments via LM Studio (Gemma 3 27B).

Usage:
    python local/segment.py <words.json> [output_dir]

Output:
    <output_dir>/_segments_result_0.json
    <output_dir>/_segments_result_1.json
    ...
"""

import json
import re
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not found. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from config import LMSTUDIO_BASE_URL, SEGMENT_MODEL, SEGMENT_BATCH_SIZE, SEGMENT_MAX_TOKENS, REQUEST_TIMEOUT

SYSTEM_PROMPT = (
    "You are a subtitle segmentation assistant. "
    "Group consecutive words into natural subtitle segments. "
    "Return ONLY a valid JSON array — no explanation, no markdown fences."
)


def build_user_prompt(words: list[dict]) -> str:
    lines = [f"[{i}] \"{w['word']}\" ({w['start']}-{w['end']})" for i, w in enumerate(words)]
    return (
        "Segment these words into natural subtitle segments.\n\n"
        "Rules:\n"
        "- Each segment must be a complete, natural phrase or sentence\n"
        "- English source: max 12 words per segment; split at semantic boundaries\n"
        "- Do NOT split after a preposition, conjunction, or article\n"
        "- word_start and word_end are indices into this word list (0-based, inclusive)\n\n"
        "Words:\n"
        + "\n".join(lines)
        + "\n\nReturn format:\n"
        '[{"src": "sentence text", "word_start": 0, "word_end": 5}, ...]'
    )


def call_api(messages: list[dict]) -> str:
    url = f"{LMSTUDIO_BASE_URL}/chat/completions"
    payload = {
        "model": SEGMENT_MODEL,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": SEGMENT_MAX_TOKENS,
    }
    resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def extract_json_array(text: str) -> list[dict]:
    text = text.strip()
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text.strip())
    # Find outermost JSON array (match [ followed by { to avoid grabbing bracket-only text)
    m = re.search(r"\[[\s\S]*?\{[\s\S]*\}[\s\S]*?\]", text)
    if m:
        text = m.group(0)
    return json.loads(text)


def segment_batch(words: list[dict], batch_num: int, max_retries: int = 2) -> list[dict]:
    prompt = build_user_prompt(words)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    last_err = None
    for attempt in range(max_retries + 1):
        try:
            content = call_api(messages)
            raw_segments = extract_json_array(content)
            break
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                print(f" (retry {attempt + 1})...", end=" ", flush=True)
    else:
        raise RuntimeError(f"Batch {batch_num} failed after {max_retries + 1} attempts: {last_err}")

    result = []
    skipped = 0
    for seg in raw_segments:
        ws = int(seg["word_start"])
        we = int(seg["word_end"])
        if ws < 0 or we >= len(words) or ws > we:
            skipped += 1
            continue
        result.append({
            "src":        seg["src"].strip(),
            "start":      words[ws]["start"],
            "end":        words[we]["end"],
            "word_start": ws,
            "word_end":   we,
        })
    if skipped:
        print(f" ⚠ {skipped} invalid segment(s) skipped", end="", flush=True)
    return result


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    words_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/tmp")

    if not words_path.exists():
        print(f"ERROR: File not found: {words_path}", file=sys.stderr)
        sys.exit(1)

    with open(words_path, encoding="utf-8") as f:
        words = json.load(f)

    total = len(words)
    print(f"  Words: {total}  |  Model: {SEGMENT_MODEL}")

    batch_num = 0
    for offset in range(0, total, SEGMENT_BATCH_SIZE):
        batch = words[offset: offset + SEGMENT_BATCH_SIZE]
        end_idx = offset + len(batch) - 1
        print(f"  Batch {batch_num} (words {offset}–{end_idx})...", end=" ", flush=True)

        segments = segment_batch(batch, batch_num)

        out_path = output_dir / f"_segments_result_{batch_num}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)

        print(f"{len(segments)} segments → {out_path}")
        batch_num += 1

    print(f"  Step A done: {batch_num} batch(es) written")


if __name__ == "__main__":
    main()
