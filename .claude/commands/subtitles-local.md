---
description: "使用本地 LM Studio 模型進行字幕分句與翻譯，輸出 .en.srt 和 .cht.srt"
allowed-tools: Bash, Read, Glob
---

# 本地字幕翻譯（LM Studio）

使用本地 LM Studio 模型處理字幕：
- **Step A 分句**：`mlx-community/gemma-3-27b-it-4bit`
- **Step B 翻譯**：`mlx-community/translategemma-27b-4bit`

模型 ID 可在 `local/config.py` 中修改。

**輸入格式**: `$ARGUMENTS`

**語法**: `<影片路徑或 words.json 路徑>`

**範例**:
- `/subtitles-local input/video.mp4`
- `/subtitles-local output/video.words.json`

---

## 步驟 0：解析參數

從 `$ARGUMENTS` 取得 `INPUT_FILE`。

推導 `PROJECT_ROOT`：從 `INPUT_FILE` 所在目錄向上找到含 `scripts/generate_subtitles.py` 的目錄；找不到則設為 `INPUT_FILE` 所在目錄。

若副檔名為 `.words.json`，設 `INPUT_IS_WORDS_JSON=true`。

---

## 步驟 1：確認 LM Studio 運行中

```bash
curl -s http://localhost:1234/v1/models | head -c 200
```

若失敗，停止並告知用戶：「請先啟動 LM Studio 並載入模型」。

顯示可用模型列表，提醒用戶確認 `local/config.py` 中的模型 ID 是否正確。

---

## 步驟 2：定位 words.json

若 `INPUT_IS_WORDS_JSON` 為 `true`：直接設 `WORDS_JSON="<INPUT_FILE>"`，跳到步驟 3。

若輸入是影片：
```bash
ls -la "<PROJECT_ROOT>/output/<主檔名>.words.json"
```
- 存在 → 設 `WORDS_JSON` 為該路徑，跳到步驟 3
- 不存在 → 執行步驟 2.5

### 步驟 2.5：產生 words.json（尚未轉錄時執行）

```bash
PYTHON="python3"
[ -f "<PROJECT_ROOT>/.venv/bin/python" ] && PYTHON="<PROJECT_ROOT>/.venv/bin/python"

"$PYTHON" "<PROJECT_ROOT>/scripts/generate_subtitles.py" \
  --file "<INPUT_FILE>" \
  --output "<PROJECT_ROOT>/output"
```

完成後設 `WORDS_JSON="<PROJECT_ROOT>/output/<主檔名>.words.json"`。

---

## 步驟 3：Step A — 分句

```bash
PYTHON="python3"
[ -f "<PROJECT_ROOT>/.venv/bin/python" ] && PYTHON="<PROJECT_ROOT>/.venv/bin/python"

"$PYTHON" "<PROJECT_ROOT>/local/segment.py" "<WORDS_JSON>" "/tmp"
```

等待完成。若失敗（非零退出碼），停止並顯示錯誤。

---

## 步驟 4：Step B — 翻譯

```bash
"$PYTHON" "<PROJECT_ROOT>/local/translate.py" "/tmp" "/tmp"
```

等待完成。若失敗，停止並顯示錯誤。

---

## 步驟 5：組裝 SRT

```bash
"$PYTHON" "<PROJECT_ROOT>/scripts/assemble_srt.py" "/tmp" "<INPUT_FILE>"
```

---

## 步驟 6：清理暫存檔案

```bash
rm -f /tmp/_segments_result_*.json /tmp/_translated_result_*.json
```

---

## 步驟 7：報告結果

告知用戶：
- 輸出的 `.en.srt` 和 `.cht.srt` 路徑
- 總字幕條數
- 提醒：可直接用 VLC 或播放器載入
