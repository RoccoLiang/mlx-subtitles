"""Load glossary terms from local/glossary.txt."""

from pathlib import Path

GLOSSARY_PATH = Path(__file__).parent / "glossary.txt"


def load_terms() -> list[str]:
    """Return non-empty, non-comment lines from glossary.txt."""
    if not GLOSSARY_PATH.exists():
        return []
    terms = []
    for line in GLOSSARY_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms.append(line)
    return terms


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
