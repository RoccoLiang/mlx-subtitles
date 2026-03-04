# mlx-subtitles

影片 → 雙語字幕（自動轉錄 + 翻譯）

---

## 需要什麼

- Apple Silicon Mac
- [uv](https://docs.astral.sh/uv/)（Python 套件管理）：`curl -LsSf https://astral.sh/uv/install.sh | sh`
- [Claude Code](https://claude.ai/code)（翻譯步驟用）

---

## 怎麼用

**Step 1 — 將影片放入 `input/`，執行：**

```bash
./transcribe
```

第一次執行會自動偵測你的 Mac 硬體、安裝環境、推薦模型。
之後每次執行都是互動式選單，選影片、確認設定，就開始跑。

**Step 2 — 在 Claude Code 執行：**

```
/subtitles-srt input/你的影片.mp4
```

完成。字幕檔會輸出到和影片相同的資料夾。

---

## 輸出檔案

| 檔案 | 內容 |
|------|------|
| `影片名.en.srt` | 英文原文字幕 |
| `影片名.cht.srt` | 正體中文翻譯字幕 |

---

## 備注

- 支援格式：`.mp4` `.mov` `.mkv` `.avi` `.m4v` `.webm` `.flv` `.wmv`
- 換機器或想重新偵測硬體：`./transcribe --reset`
- 想跳過互動直接跑：`./transcribe input/video.mp4 [模型] [語言]`
