# mlx-subtitles

影片 → 雙語字幕（自動轉錄 + 翻譯）

支援兩種翻譯工作流程：

| 工作流程 | 轉錄 | 翻譯 | 需要 |
|----------|------|------|------|
| **Claude Code** | Apple Silicon 本地 | Claude API | Claude Code |
| **本地全端** | Apple Silicon 本地 | LM Studio 本地 | LM Studio |

---

## 需要什麼

**共同需求**
- Apple Silicon Mac
- [uv](https://docs.astral.sh/uv/)：`curl -LsSf https://astral.sh/uv/install.sh | sh`

**Claude Code 工作流程**
- [Claude Code](https://claude.ai/code)

**本地全端工作流程**
- [LM Studio](https://lmstudio.ai/)，載入分句模型與翻譯模型（詳見下方）

---

## Claude Code 工作流程

**Step 1 — 轉錄**

將影片放入 `input/`，執行：

```bash
./transcribe
```

第一次執行會自動偵測硬體、安裝環境、推薦模型。

**Step 2 — 翻譯（在 Claude Code 執行）**

```
/subtitles-srt input/你的影片.mp4
```

---

## 本地全端工作流程

所有步驟都在本機執行，不需要 Claude API。

**Step 1 — 轉錄**（同上）

```bash
./transcribe
```

**Step 2 — 啟動 LM Studio，載入模型**

在 `local/config.py` 確認模型 ID 與 LM Studio 一致：

```python
SEGMENT_MODEL   = "google/gemma-3-12b"   # 分句用
TRANSLATE_MODEL = "google/gemma-3-12b"   # 翻譯用
```

可執行以下指令查看目前載入的模型 ID：

```bash
curl -s http://localhost:1234/v1/models
```

**Step 3 — 執行本地 Pipeline**

```bash
.venv/bin/python local/run.py input/你的影片.mp4
```

---

## 輸出檔案

| 檔案 | 內容 |
|------|------|
| `output/影片名.words.json` | 單字級時間碼（轉錄中間產物） |
| `影片名.en.srt` | 英文原文字幕 |
| `影片名.cht.srt` | 正體中文翻譯字幕 |

字幕檔輸出位置與影片同目錄。

---

## 專有名詞術語表

在 `local/glossary.txt` 新增專有名詞（人名、品牌、節目名等），可提升：
- **轉錄準確度**：作為 Whisper `initial_prompt` 偏向正確拼法
- **翻譯保留率**：告知模型哪些詞不可翻譯

```
# local/glossary.txt 範例
Ferry Corsten
Gouryella
System F
Muzikxpress
```

---

## 備注

- 支援格式：`.mp4` `.mov` `.mkv` `.avi` `.m4v` `.webm` `.flv` `.wmv`
- 換機器或重新偵測硬體：`./transcribe --reset`
- 跳過互動直接跑：`./transcribe input/video.mp4 [模型] [語言]`
- 本地 Pipeline context 限制：預設 batch 為 100 詞/次，適配 4096 token context window
