# mlx-subtitles

Video → Bilingual Subtitles (Auto-transcription + Translation)

Two translation workflows supported:

| Workflow | Transcription | Translation | Requires |
|----------|---------------|-------------|----------|
| **Claude Code** | Apple Silicon Local | Claude API | Claude Code |
| **Local End-to-End** | Apple Silicon Local | LM Studio Local | LM Studio |

---

## Requirements

**Common Requirements**
- Apple Silicon Mac
- [uv](https://docs.astral.sh/uv/): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- OpenCC (optional, for Chinese translation enhancement): `pip install OpenCC`

**Claude Code Workflow**
- [Claude Code](https://claude.ai/code)

**Local End-to-End Workflow**
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

## OpenCC Enhancement (Optional)

OpenCC converts Simplified Chinese to Traditional Chinese (Taiwan), enhancing translation quality and filling in potentially missed terminology.

### Usage

**Interactive Mode:**
```bash
./subtitle_processor
# Select "2) Use OpenCC" when prompted
```

**Command Line Mode:**
```bash
./subtitle_processor input/your-video.mp4 --opencc
```

**Configuration:**
Set default in `local/config.py`:
```python
USE_OPENCC = True  # Enable by default
```

### Notes
- Requires: `pip install OpenCC`
- Uses `s2tw` conversion (Simplified → Traditional Taiwan)
- Applied after translation, before SRT assembly

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
- See **OpenCC Enhancement** section for translation enhancement options

---

# mlx-subtitles

影片 → 雙語字幕（自動轉錄 + 翻譯）

支援兩種翻譯工作流程：

| 工作流程 | 轉錄 | 翻譯 | 需要 |
|----------|------|------|------|
| **Claude Code** | Apple Silicon 本地 | Claude API | Claude Code |
| **本地全端** | Apple Silicon 本地 | LM Studio 本地 | LM Studio |

---

## 環境需求

**共同需求**
- Apple Silicon Mac
- [uv](https://docs.astral.sh/uv/)：`curl -LsSf https://astral.sh/uv/install.sh | sh`
- OpenCC（可選，用於中文翻譯增強）：`pip install OpenCC`

**Claude Code 工作流程**
- [Claude Code](https://claude.ai/code)

**本地全端工作流程**
- [LM Studio](https://lmstudio.ai/)，載入一個 Instruct 模型（可用於分段和翻譯）

---

## Claude Code 工作流程

**步驟 1 — 轉錄**

將影片放入 `input/`，執行：

```bash
./transcribe
```

首次執行會自動偵測硬體、安裝環境，並推薦合適的模型。

**步驟 2 — 翻譯（在 Claude Code 中執行）**

```
/subtitles-srt input/your-video.mp4
```

---

## 本地全端工作流程

所有步驟皆在本地端執行，無需 Claude API。

**步驟 1 — 轉錄**（同上）

```bash
./transcribe
```

**步驟 2 — 啟動 LM Studio 並載入模型**

確認 `local/config.py` 中的模型 ID 與 LM Studio 載入的模型相同（同一模型可用於分段和翻譯）：

```python
SEGMENT_MODEL   = "your-model-id"   # 用於分段
TRANSLATE_MODEL = "your-model-id"   # 用於翻譯（可使用相同模型）
```

執行以下命令來檢查 LM Studio 目前載入的模型 ID：

```bash
curl -s http://localhost:1234/v1/models
```

**步驟 3 — 執行本地端 Pipeline**

```bash
./subtitle_processor
```

或跳過互動，直接指定影片：

```bash
./subtitle_processor input/your-video.mp4
```

---

## 輸出檔案

| 檔案 | 內容 |
|------|---------|
| `output/video-name.words.json` | 單字級時間戳記（轉錄的中間產物）|
| `video-name.en.srt` | 英文原始字幕 |
| `video-name.cht.srt` | 繁體中文翻譯字幕 |

字幕檔案會輸出到與影片相同的目錄。

---

## OpenCC 增強翻譯（可選）

OpenCC 將簡體中文轉換為繁體中文（台灣），可提升翻譯品質，補正可能遺漏的用語。

### 使用方式

**互動模式：**
```bash
./subtitle_processor
# 出現選單時選擇「2) 使用 OpenCC」
```

**指令模式：**
```bash
./subtitle_processor input/your-video.mp4 --opencc
```

**設定預設：**
在 `local/config.py` 中設定：
```python
USE_OPENCC = True  # 預設啟用
```

### 備註
- 需要安裝：`pip install OpenCC`
- 使用 `s2tw` 轉換（簡體→繁體台灣）
- 在翻譯後、SRT 組裝前應用

---

## 專有名詞 Glossary

將專有名詞（人名、品牌、節目名稱等）加入 `local/glossary.txt`：

| 格式 | 說明 |
|--------|-------------|
| `correct-term` | 加入翻譯排除清單，要求模型不要翻譯 |
| `incorrect->correct` | 在分段前自動修正 words.json 中的拼寫錯誤 |

```
# local/glossary.txt 範例
Ferry Corsten
Gouryella
Guriela->Gouryella
System F
Muzikxpress
```

---

## 注意事項

- 支援格式：`.mp4` `.mov` `.mkv` `.avi` `.m4v` `.webm` `.flv` `.wmv`
- 硬體重設或重新偵測：`./transcribe --reset`
- 跳過互動直接執行（轉錄）：`./transcribe input/video.mp4 [model] [language]`
- 跳過互動直接執行（字幕）：`./subtitle_processor input/video.mp4`
- 本地 Pipeline 上下文限制：預設批次為 100 字詞/次，符合 4096 token 上下文視窗
- 參考「OpenCC 增強翻譯」章節了解翻譯強化選項
