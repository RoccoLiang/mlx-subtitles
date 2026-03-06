#!/usr/bin/env python3
"""
Step A: Segment words.json into subtitle segments via LM Studio.

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
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not found. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    LMSTUDIO_BASE_URL,
    SEGMENT_MODEL,
    SEGMENT_BATCH_SIZE,
    SEGMENT_MAX_TOKENS,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_BACKOFF_BASE,
    validate_lmstudio_url,
)

SYSTEM_PROMPT = (
    "You are a subtitle segmentation assistant. "
    "Group consecutive words into natural subtitle segments. "
    "Return ONLY a valid JSON array — no explanation, no markdown fences."
)

# Validation schema for API responses
REQUIRED_SEGMENT_FIELDS = {"src", "word_start", "word_end"}


def build_user_prompt(words: list[dict]) -> str:
    lines = [
        f'[{i}] "{w["word"]}" ({w["start"]}-{w["end"]})' for i, w in enumerate(words)
    ]
    return (
        "Segment these words into natural subtitle segments.\n\n"
        "Rules:\n"
        "- Each segment must be a complete, natural phrase or sentence\n"
        "- English source: max 12 words per segment; split at semantic boundaries\n"
        "- Do NOT split after a preposition, conjunction, or article\n"
        "- word_start and word_end are indices into this word list (0-based, inclusive)\n\n"
        "Words:\n" + "\n".join(lines) + "\n\nReturn format:\n"
        '[{"src": "sentence text", "word_start": 0, "word_end": 5}, ...]'
    )


def call_api(messages: list[dict]) -> str:
    validate_lmstudio_url()  # Lazy validation on first API call
    url = f"{LMSTUDIO_BASE_URL}/chat/completions"
    payload = {
        "model": SEGMENT_MODEL,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": SEGMENT_MAX_TOKENS,
    }
    try:
        resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("choices"):
            raise ValueError("API response missing 'choices'")
        content = data["choices"][0].get("message", {}).get("content", "")
        if not content:
            raise ValueError("API response has empty content")
        return content
    except requests.exceptions.Timeout:
        raise TimeoutError(f"API request timed out after {REQUEST_TIMEOUT}s")
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"API request failed: {e}")


def extract_json_array(text: str) -> list[dict]:
    """Extract and validate JSON array from API response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text.strip())

    m = re.search(r"\[[\s\S]*?\{[\s\S]*\}[\s\S]*?\]", text)
    if m:
        text = m.group(0)

    try:
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError(f"Expected JSON array, got {type(data).__name__}")
        for i, seg in enumerate(data):
            if not isinstance(seg, dict):
                raise ValueError(f"Segment {i} is not a dict")
            missing = REQUIRED_SEGMENT_FIELDS - set(seg.keys())
            if missing:
                raise ValueError(f"Segment {i} missing fields: {missing}")
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


def segment_batch(
    words: list[dict], batch_num: int, max_retries: int = MAX_RETRIES
) -> list[dict]:
    prompt = build_user_prompt(words)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    last_err = None
    for attempt in range(max_retries):
        try:
            content = call_api(messages)
            raw_segments = extract_json_array(content)

            result = []
            skipped = 0
            for seg in raw_segments:
                try:
                    ws = int(seg["word_start"])
                    we = int(seg["word_end"])
                    if ws < 0 or we >= len(words) or ws > we:
                        skipped += 1
                        continue
                    result.append(
                        {
                            "src": seg["src"].strip(),
                            "start": words[ws]["start"],
                            "end": words[we]["end"],
                            "word_start": ws,
                            "word_end": we,
                        }
                    )
                except (KeyError, ValueError, TypeError):
                    skipped += 1

            if skipped:
                print(f" ⚠ {skipped} invalid segment(s) skipped", end="", flush=True)
            return result

        except (ValueError, TimeoutError, ConnectionError) as e:
            last_err = e
            if attempt < max_retries - 1:
                wait_time = RETRY_BACKOFF_BASE**attempt
                print(
                    f" (retry {attempt + 1}, wait {wait_time}s)...", end=" ", flush=True
                )
                time.sleep(wait_time)

    raise RuntimeError(
        f"Batch {batch_num} failed after {max_retries} attempts: {last_err}"
    )


def process_batch_wrapper(args: tuple) -> tuple[int, list[dict]]:
    """Wrapper for parallel batch processing."""
    words, batch_num = args
    segments = segment_batch(words, batch_num)
    return batch_num, segments


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    words_path = Path(sys.argv[1]).resolve()
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(tempfile.gettempdir())

    if not words_path.exists():
        print(f"ERROR: File not found: {words_path}", file=sys.stderr)
        sys.exit(1)

    with open(words_path, encoding="utf-8") as f:
        words = json.load(f)

    if not words:
        print("ERROR: words.json is empty", file=sys.stderr)
        sys.exit(1)

    total = len(words)
    print(f"  Words: {total}  |  Model: {SEGMENT_MODEL}")

    # Prepare batches
    batches = []
    for offset in range(0, total, SEGMENT_BATCH_SIZE):
        batch = words[offset : offset + SEGMENT_BATCH_SIZE]
        batches.append((batch, len(batches)))

    # Process in parallel
    max_workers = min(4, len(batches))
    results = {}
    errors = []

    print(f"  Processing {len(batches)} batches with {max_workers} workers...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_batch_wrapper, args): args[1] for args in batches
        }

        for future in as_completed(futures):
            batch_num = futures[future]
            try:
                batch_num, segments = future.result()
                results[batch_num] = segments

                out_path = output_dir / f"_segments_result_{batch_num}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(segments, f, ensure_ascii=False, separators=(",", ":"))

                print(
                    f"  Batch {batch_num}: {len(segments)} segments → {out_path.name}"
                )
            except Exception as e:
                errors.append((batch_num, e))
                print(f"  ERROR: Batch {batch_num} failed: {e}", file=sys.stderr)

    # Report all errors after processing completes
    if errors:
        raise RuntimeError(f"{len(errors)}/{len(batches)} batches failed")

    print(f"  Step A done: {len(results)} batch(es) written")


if __name__ == "__main__":
    main()
