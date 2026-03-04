# LM Studio server
LMSTUDIO_BASE_URL = "http://localhost:1234/v1"

# Model identifiers — verify via: curl http://localhost:1234/v1/models
SEGMENT_MODEL   = "google/gemma-3-27b"

# Translation model options:
#   "translategemma"  — use TranslateGemma structured API (may not work in all LM Studio versions)
#   any other string  — use standard chat completions format (works with Gemma 3 or any instruct model)
TRANSLATE_MODEL      = "google/gemma-3-27b"
TRANSLATE_USE_NATIVE = False  # True = TranslateGemma structured format, False = standard chat

# Language settings
TRANSLATE_SOURCE_LANG = "en"
TRANSLATE_TARGET_LANG = "zh-TW"

# Batch sizes — tuned for 4096-token context window (input + output share the budget)
SEGMENT_BATCH_SIZE       = 100  # words per segmentation batch  (200 was too close to 4096 limit)
TRANSLATE_CHAT_BATCH_SIZE = 20  # segments per call in standard chat mode (unused in native mode)

# Max output tokens per API call (leave room for input within 4096 total)
SEGMENT_MAX_TOKENS   = 2048
TRANSLATE_MAX_TOKENS = 1024

# Request timeout (seconds) — 27B models on local hardware may be slow
REQUEST_TIMEOUT = 300
