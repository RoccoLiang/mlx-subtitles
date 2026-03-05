"""Load glossary terms and corrections from local/glossary.txt.

Line formats:
    正確詞          plain term — used for translation keep-list
    錯誤->正確      correction pair — used to fix words.json after transcription
    # 註解          ignored
"""

import threading
from pathlib import Path
from typing import Final

GLOSSARY_PATH: Final[Path] = Path(__file__).parent / "glossary.txt"

# Thread-safe module-level cache
_cache: tuple[list[str], dict[str, str]] | None = None
_cache_lock = threading.Lock()


def _parse() -> tuple[list[str], dict[str, str]]:
    """Return (terms, corrections) from glossary.txt. Results are cached."""
    global _cache
    if _cache is not None:
        return _cache

    with _cache_lock:
        # Double-check after acquiring lock
        if _cache is not None:
            return _cache

        terms: list[str] = []
        corrections: dict[str, str] = {}
        if not GLOSSARY_PATH.exists():
            _cache = terms, corrections
            return _cache

        for line in GLOSSARY_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "->" in line:
                wrong, _, correct = line.partition("->")
                corrections[wrong.strip()] = correct.strip()
            else:
                terms.append(line)

        _cache = terms, corrections
        return _cache


def load_terms() -> list[str]:
    """Return plain terms (no corrections)."""
    terms, _ = _parse()
    return terms


def load_corrections() -> dict[str, str]:
    """Return {wrong: correct} mapping for words.json post-processing."""
    _, corrections = _parse()
    return corrections


def as_keep_list(terms: list[str] | None = None) -> str:
    """Build a one-line instruction for the translation prompt."""
    if terms is None:
        terms = load_terms()
    if not terms:
        return ""
    return "Keep these terms unchanged (do not translate): " + ", ".join(terms) + "."
