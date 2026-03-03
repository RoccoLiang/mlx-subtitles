# mlx-subtitles

從影片自動生成英文字幕，並翻譯為正體中文，輸出雙語 ASS 字幕。

- **轉錄**：[mlx-whisper](https://github.com/ml-explore/mlx-examples)（Apple Silicon 最佳化，支援字詞級時間碼）
- **翻譯**：[Claude Code](https://claude.ai/code) `/translate-srt` skill（由 Claude 在對話中直接完成，無需另外設定 API Key）
- **輸出**：雙語 ASS 字幕，中文大字 / 英文小字，IINA / VLC / mpv 自動載入

---

## 需求

| 工具 | 用途 | 備註 |
|------|------|------|
| Apple Silicon Mac | 執行 mlx-whisper | 僅支援 Apple Silicon |
| [uv](https://docs.astral.sh/uv/) | Python 環境管理 | |
| [Claude Code](https://claude.ai/code) | **翻譯（必要）** | 翻譯步驟在 Claude Code 內執行，缺少 Claude Code 則無法翻譯 |

安裝 uv：
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 完整工作流程

### Step 1：轉錄

將影片放入 `input/`，執行：

```bash
./transcribe                                          # 處理 input/ 下所有影片
./transcribe input/my_video.mp4                      # 單一檔案
./transcribe input/my_video.mp4 large-v3-turbo       # 指定模型
```

**第一次執行**會自動：
1. 偵測並移除不相容的虛擬環境（例如從其他機器同步過來的）
2. 建立 `.venv` 並安裝 `mlx-whisper` 及其依賴套件（約 200 MB）
3. 首次轉錄時下載 Whisper 模型權重（`large-v3` 約 3 GB，只下載一次）

**轉錄過程**：
mlx-whisper 將影片音訊切割為語音片段，對每個片段進行辨識，並記錄每個字詞的起訖時間（word-level timestamps）。

**輸出**：
```
output/my_video.words.json   ← 字詞級時間碼，供翻譯步驟使用
```

---

### Step 2：翻譯

在 Claude Code 中執行：

```
/translate-srt input/my_video.mp4
```

**翻譯過程**分四個階段：

**① 分批翻譯**
讀取 `words.json` 中的全部字詞，以每批 200 個字詞為單位，由 Claude 完成：
- **分句**：將連續字詞組合為自然的字幕段落（每句目標 8–15 個英文字）
- **翻譯**：譯為正體中文（台灣用語），套用影視翻譯風格與音樂術語標準譯名

**② 術語一致性**
翻譯前先掃描前 400 個字詞，識別重複出現的人名、地名、節目名等，建立統一譯名表並套用至全片。

**③ 時間碼比對**
翻譯完成後，用序列文字比對法將每句字幕對應回 `words.json` 的字詞位置，取得精確的起訖時間。此方式不依賴手動計數的字詞索引，能正確處理 mlx-whisper 的連字符拆分（如 `JP-8000` 被拆為兩個 token）。

**④ 組裝 ASS 字幕**
依照起訖時間輸出雙語 ASS 字幕，中英各自套用獨立樣式。

**輸出**：
```
input/my_video.ass   ← 雙語 ASS 字幕（與影片同目錄，播放器自動載入）
```

---

## ASS 字幕樣式

```
┌─────────────────────────────────┐
│                                 │
│   正體中文字幕（白色，60px）        │
│   English subtitle (灰色，36px)  │
└─────────────────────────────────┘
```

| 層 | 字體 | 大小 | 顏色 |
|----|------|------|------|
| 中文 | Noto Sans CJK TC | 60px | 白色 | MarginV 80 |
| 英文 | Noto Sans | 36px | 淡灰 | MarginV 38 |

---

## 模型選項

| 模型 | 大小 | 說明 |
|------|------|------|
| `large-v3` | ~3 GB | 預設，最高精確度 |
| `large-v3-turbo` | ~1.6 GB | 速度與精確度平衡 |
| `medium` | ~1.5 GB | 較快，精確度略低 |
| `small` | ~500 MB | 測試用 |

| 機型 | 建議模型 |
|------|----------|
| M4 Max 36GB | `large-v3` |
| M1 Pro 16GB | `large-v3-turbo` |

---

## 支援格式

`.mp4` `.mov` `.mkv` `.avi` `.m4v` `.webm` `.flv` `.wmv`
