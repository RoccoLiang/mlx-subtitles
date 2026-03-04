"""Load glossary terms and corrections from local/glossary.txt.

Line formats:
    正確詞          plain term — used for initial_prompt and translation keep-list
    錯誤=正確       correction pair — used to fix words.json after transcription
    # 註解          ignored
"""

from pathlib import Path

GLOSSARY_PATH = Path(__file__).parent / "glossary.txt"


def _parse() -> tuple[list[str], dict[str, str]]:
    """Return (terms, corrections) from glossary.txt."""
    terms: list[str] = []
    corrections: dict[str, str] = {}
    if not GLOSSARY_PATH.exists():
        return terms, corrections
    for line in GLOSSARY_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            wrong, _, correct = line.partition("=")
            corrections[wrong.strip()] = correct.strip()
        else:
            terms.append(line)
    return terms, corrections


def load_terms() -> list[str]:
    """Return plain terms (no corrections)."""
    terms, _ = _parse()
    return terms


def load_corrections() -> dict[str, str]:
    """Return {wrong: correct} mapping for words.json post-processing."""
    _, corrections = _parse()
    return corrections


def as_initial_prompt(terms: list[str] | None = None) -> str:
    """Build a whisper initial_prompt string from glossary terms."""
    if terms is None:
        terms = load_terms()
    if not terms:
        return ""
    return "Proper nouns: " + ", ".join(terms) + "."


def as_keep_list(terms: list[str] | None = None) -> str:
    """Build a one-line instruction for the translation prompt."""
    if terms is None:
        terms = load_terms()
    if not terms:
        return ""
    return "Keep these terms unchanged (do not translate): " + ", ".join(terms) + "."
