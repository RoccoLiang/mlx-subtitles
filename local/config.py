"""
Configuration for mlx-subtitles local pipeline.
"""

import os
import warnings
from pathlib import Path
from typing import Final

# ── Security ───────────────────────────────────────────────────────────────────
# LM Studio server (override via LMSTUDIO_URL env var)
LMSTUDIO_BASE_URL: Final[str] = os.environ.get(
    "LMSTUDIO_URL", "http://localhost:1234/v1"
)

# Lazy validation flag (set to True after first check)
_url_validated = False


def validate_lmstudio_url() -> None:
    """Validate LM Studio URL is localhost. Called on first API request."""
    global _url_validated
    if _url_validated:
        return
    _url_validated = True

    if not LMSTUDIO_BASE_URL.startswith(
        "http://localhost"
    ) and not LMSTUDIO_BASE_URL.startswith("http://127.0.0.1"):
        warnings.warn(
            "LMSTUDIO_BASE_URL should be localhost for security. "
            "Remote URLs may expose API to network attacks.",
            UserWarning,
        )


# ── Model Configuration ───────────────────────────────────────────────────────
SEGMENT_MODEL: Final[str] = "google/gemma-3-27b"
TRANSLATE_MODEL: Final[str] = "google/gemma-3-27b"

# TranslateGemma native format (may not work in all LM Studio versions)
TRANSLATE_USE_NATIVE: Final[bool] = False

# ── Language Settings ─────────────────────────────────────────────────────────
TRANSLATE_SOURCE_LANG: Final[str] = "en"
TRANSLATE_TARGET_LANG: Final[str] = "zh-TW"

# ── OpenCC Settings ───────────────────────────────────────────────────────────
# Use OpenCC to enhance Chinese translation (简→繁)
USE_OPENCC: Final[bool] = False

# ── Batch Sizes ───────────────────────────────────────────────────────────────
# Tuned for 4096-token context window (input + output share the budget)
SEGMENT_BATCH_SIZE: Final[int] = 100  # words per segmentation batch
TRANSLATE_CHAT_BATCH_SIZE: Final[int] = 20  # segments per call in standard chat mode

# ── Token Limits ──────────────────────────────────────────────────────────────
# Max output tokens per API call (leave room for input within 4096 total)
SEGMENT_MAX_TOKENS: Final[int] = 2048
TRANSLATE_MAX_TOKENS: Final[int] = 1024

# ── Timeouts ──────────────────────────────────────────────────────────────────
# Request timeout (seconds) — 27B models on local hardware may be slow
REQUEST_TIMEOUT: Final[int] = 300

# ── Retry Configuration ───────────────────────────────────────────────────────
MAX_RETRIES: Final[int] = 3
RETRY_BACKOFF_BASE: Final[float] = 2.0  # seconds, exponential backoff

# ── Output Settings ───────────────────────────────────────────────────────────
HOLD_TIME: Final[float] = 0.4  # Seconds subtitle lingers after last word ends

# ── Supported Formats ─────────────────────────────────────────────────────────
SUPPORTED_VIDEO_EXTS: Final[tuple[str, ...]] = (
    "mp4",
    "mov",
    "mkv",
    "avi",
    "m4v",
    "webm",
    "flv",
    "wmv",
)

# ── Validation ───────────────────────────────────────────────────────────────
CONTEXT_WINDOW_SIZE: Final[int] = 4096  # LM Studio context window
TARGET_CHARS_PER_LINE: Final[int] = 14  # Ideal Chinese characters per line
MAX_CHARS_PER_LINE: Final[int] = 20  # Hard limit

# ── Translation Quality ───────────────────────────────────────────────────────
MIN_SUCCESS_RATE: Final[float] = 0.9  # Minimum success rate for batch translation
