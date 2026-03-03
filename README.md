# mlx-subtitles

從影片自動生成英文字幕，並翻譯為正體中文，輸出雙語 ASS 字幕。

- **轉錄**：[mlx-whisper](https://github.com/ml-explore/mlx-examples)（Apple Silicon 最佳化）
- **翻譯**：[Claude Code](https://claude.ai/code) `/translate-srt` skill（由 Claude 在對話中直接完成，無需另外設定 API Key）
- **輸出**：雙語 ASS 字幕，中文大字 / 英文小字，IINA / VLC / mpv 自動載入

---

## 需求

| 工具 | 用途 | 備註 |
|------|------|------|
| Apple Silicon Mac | 轉錄（mlx-whisper） | 僅支援 Apple Silicon |
| [uv](https://docs.astral.sh/uv/) | Python 環境管理 | |
| [Claude Code](https://claude.ai/code) | **翻譯（必要）** | 翻譯步驟透過 Claude Code 的 `/translate-srt` skill 執行，缺少 Claude Code 則無法翻譯 |

安裝 uv：
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 使用方式

### Step 1：轉錄

將影片放入 `input/`，執行：

```bash
./transcribe                              # 處理 input/ 下所有影片
./transcribe input/my_video.mp4          # 單一檔案
./transcribe input/my_video.mp4 large-v3-turbo  # 指定模型
```

第一次執行會自動建立 `.venv` 並安裝套件。
輸出：`output/my_video.words.json`、`output/my_video.en.srt`

### Step 2：翻譯（在 Claude Code 中執行）

```
/translate-srt input/my_video.mp4
```

輸出：`input/my_video.ass`（雙語 ASS 字幕，與影片同目錄自動載入）

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
