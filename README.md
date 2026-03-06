# mlx-subtitles

影片 → 雙語字幕（自動轉錄 + 翻譯）

支援兩種翻譯工作流程：

| 工作流程 | 轉錄 | 翻譯 | 需要 |
|----------|------|------|------|
| **Claude Code** | Apple Silicon 本地 | Claude API | Claude Code |
| **本地全端** | Apple Silicon 本地 | LM Studio 本地 | LM Studio |

---

## Requirements

**Common Requirements**
- Apple Silicon Mac
- [uv](https://docs.astral.sh/uv/)：`curl -LsSf https://astral.sh/uv/install.sh | sh`

**Claude Code 工作流程**
- [Claude Code](https://claude.ai/code)

**本地全端工作流程**
- [LM Studio](https://lmstudio.ai/), load an Instruct model (shared for segmentation and translation)

---

## Claude Code Workflow

**Step 1 — Transcription**

Place video in `input/`, execute:

```bash
./transcribe
```

First run automatically detects hardware, installs environment, and recommends model.

**Step 2 — Translation (Run in Claude Code)**

```
/subtitles-srt input/your-video.mp4
```

---

## Local End-to-End Workflow

All steps run locally, no Claude API required.

**Step 1 — Transcription** (same as above)

```bash
./transcribe
```

**Step 2 — Start LM Studio and Load Model**

Confirm model ID in `local/config.py` matches what LM Studio loaded (same model can be used for both segmentation and translation):

```python
SEGMENT_MODEL   = "your-model-id"   # For segmentation
TRANSLATE_MODEL = "your-model-id"   # For translation (can be same)
```

Run the following command to check current model ID loaded in LM Studio:

```bash
curl -s http://localhost:1234/v1/models
```

**Step 3 — Run Local Pipeline**

```bash
./subtitle_processor
```

Or skip interaction and specify video directly:

```bash
./subtitle_processor input/your-video.mp4
```

---

## Output Files

| File | Content |
|------|---------|
| `output/video-name.words.json` | Word-level timestamps (transcription intermediate product) |
| `video-name.en.srt` | English original subtitles |
| `video-name.cht.srt` | Traditional Chinese translated subtitles |

Subtitle files are output in the same directory as the video.

---

## Glossary for Proper Nouns

Add proper nouns (names, brands, show titles, etc.) to `local/glossary.txt`:

| Format | Description |
|--------|-------------|
| `correct-term` | Add to translation exclusion list, tell model not to translate |
| `incorrect->correct` | Automatically correct misspellings in words.json before segmentation |

```
# local/glossary.txt example
Ferry Corsten
Gouryella
Guriela->Gouryella
System F
Muzikxpress
```

---

## Notes

- Supported formats: `.mp4` `.mov` `.mkv` `.avi` `.m4v` `.webm` `.flv` `.wmv`
- Hardware reset or re-detection: `./transcribe --reset`
- Skip interaction and run directly (transcription): `./transcribe input/video.mp4 [model] [language]`
- Skip interaction and run directly (subtitles): `./subtitle_processor input/video.mp4`
- Local Pipeline context limit: Default batch is 100 words/iteration, fits 4096 token context window
