---
description: "讀取 .words.json 單字時間碼，兩階段分句翻譯，輸出 .en.srt 和 .cht.srt"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# 影片字幕翻譯技能（SRT 輸出）

讀取 mlx-whisper 產生的 `.words.json` 單字時間碼檔案，分兩個階段處理：Step A 負責分句並確定時間碼，Step B 負責翻譯。最後輸出 `.en.srt`（英文原文）和 `.cht.srt`（正體中文）。

**輸入格式**: `$ARGUMENTS`

**語法**: `<影片路徑或 words.json 路徑> [來源語言>目標語言]`

**範例**:
- `/subtitles-srt input/video.mp4` → 自動找到對應 words.json，翻譯成繁體中文
- `/subtitles-srt output/video.words.json` → 直接指定 words.json
- `/subtitles-srt input/video.mp4 en>zh` → 明確指定語言對

---

## 工作流程

### 步驟 0：解析參數

從 `$ARGUMENTS` 解析：

1. 檢查最後一個 token 是否符合 `XX>YY` 格式
   - 符合：語言對 = 該 token，輸入路徑 = 剩餘字串
   - 不符合：語言對 = `en>zh`（預設），輸入路徑 = 整個 `$ARGUMENTS`
2. 記為：
   - `SRC_LANG`：來源語言（`>` 左側）
   - `TGT_LANG`：目標語言（`>` 右側）
   - `INPUT_FILE`：輸入路徑
   - `INPUT_IS_WORDS_JSON`：若副檔名為 `.words.json`，設為 `true`
3. 推導 `PROJECT_ROOT`：從 `INPUT_FILE` 所在目錄向上找到含 `scripts/generate_subtitles.py` 的目錄；找不到則設為 `INPUT_FILE` 所在目錄

顯示：
```
輸入：<INPUT_FILE>
翻譯方向：<SRC_LANG 全名> → <TGT_LANG 全名>
```

### 步驟 1：定位 words.json

確認輸入檔案存在：
```bash
ls -la "<INPUT_FILE>"
```
找不到時嘗試 Glob 搜尋；仍找不到則停止。

**如果 `INPUT_IS_WORDS_JSON` 為 `true`**：直接設 `WORDS_JSON="<INPUT_FILE>"`，跳到步驟 2。

**如果輸入是影片**：
```bash
ls -la "<PROJECT_ROOT>/output/<主檔名>.words.json"
```
- 存在 → 設 `WORDS_JSON` 為該路徑，顯示 `✓ 找到 words.json`，跳到步驟 2
- 不存在 → 執行步驟 1.5 產生 words.json

### 步驟 1.5：產生 words.json（尚未轉錄時執行）

```bash
PYTHON="python3"
[ -f "<PROJECT_ROOT>/.venv/bin/python" ] && PYTHON="<PROJECT_ROOT>/.venv/bin/python"

"$PYTHON" "<PROJECT_ROOT>/scripts/generate_subtitles.py" \
  --file "<INPUT_FILE>" \
  --output "<PROJECT_ROOT>/output"
```

完成後設 `WORDS_JSON="<PROJECT_ROOT>/output/<主檔名>.words.json"`，繼續步驟 2。

### 步驟 2：讀取 words.json

用 Read 工具讀取 `WORDS_JSON`，取得單字陣列：
```json
[{"word": "Hey", "start": 0.54, "end": 0.72}, ...]
```

> **注意：大型 words.json（> 256 KB）可能超過 Read 工具的限制。**
> 遇到此情況，改用 Bash 搭配 Python 讀取：
> ```bash
> cat "<WORDS_JSON>" | python3 -c "
> import json, sys
> words = json.load(sys.stdin)
> print(f'總字數：{len(words)}')
> for i, w in enumerate(words[:5]):
>     print(i, w)
> "
> ```
> 分批處理時，同樣用 Bash + Python slice 取得各批次的 JSON 片段。

記下總單字數 `TOTAL_WORDS`。

---

## Step A：分句並記錄時間碼

將單字陣列以 **200 個單字** 為一批，依序處理每批，輸出含時間碼的分句 JSON。

**前置作業（僅第一批執行）**：
掃描前 400 個單字，識別重複出現的專有名詞（人名、地名、節目名、唱片名等），建立統一術語表，後續批次沿用。

**每批操作**：

取本批第 `[global_offset]` 到 `[global_offset + 199]` 個單字（最後一批可能更少）。

1. **分句**：將連續單字組合成自然字幕段落
   - 以標點符號、語意停頓為優先邊界
   - **英文來源（en）**：每句 **不超過 12 個單字**；超過時必須在語意完整處拆成兩條；避免在介詞、連接詞、冠詞後斷句
   - **日文來源（ja）**：每句目標 15–30 個字符；`src` 欄位輸出自然日文句子（字符間不加空格）

2. **時間碼**：每個分句的時間碼**直接從 words.json 中讀取**：
   - `start` = `words[word_start_global_index].start`（第一個單字的開始時間）
   - `end` = `words[word_end_global_index].end`（最後一個單字的結束時間）
   - 其中 `word_start_global_index` 和 `word_end_global_index` 是該分句首尾單字在整個 words.json 中的全域索引

3. **輸出格式**（JSON 陣列）：
```json
[
  {
    "src": "Hey there, welcome to a brand new episode of Music Express.",
    "start": 0.54,
    "end": 3.20,
    "word_start": 0,
    "word_end": 9
  }
]
```
`word_start` / `word_end` 為本批次內的單字索引（0-based，含頭含尾）。
`start` / `end` 為秒數浮點數，直接來自 words.json。

4. 用 Write 工具將結果寫入 `/tmp/_segments_result_<批次編號>.json`（從 0 開始）。每批完成立即寫入，不等全部完成。

**Step A 全部批次完成後，才開始 Step B。**

---

## Step B：翻譯

**讀取所有 Step A 結果**：依序讀取 `/tmp/_segments_result_0.json`、`_segments_result_1.json`...，合併為完整分句列表。

將分句列表以 **200 句** 為一批，依序翻譯（注意：這裡的批次是按「句數」而非「單字數」）。

**每批翻譯操作**：

1. **翻譯**：將每個分句的 `src` 翻譯成正體中文（台灣用語）

   **通用翻譯規範**：
   - 影視翻譯風格，口語自然流暢
   - 保持語意準確，不過度意譯

   **英文保留規則（優先於一切）**：
   以下類型**一律保留英文原文**，不音譯、不翻譯：
   - 人名、藝名（Ferry Corsten、Nick Warren、Pete Tong、Tiësto…）
   - 品牌名、產品型號（Roland、Yamaha、JP-8000、Jupiter-8、Akai…）
   - 專業技術術語（SuperSaw、A&R、white label、DAW、EQ、MIDI、BPM…）
   - 節目名、廠牌名、企劃名（Music Express、Armada、System F、Gouryella…）
   - 地名可用台灣通用譯名（Rotterdam→鹿特丹、Netherlands→荷蘭），無通用譯名則保留英文

   **繁體中文（zh）額外規範**：
   - 使用台灣慣用繁體中文及口語表達
   - 每條 `tgt` 的**漢字數控制在 13–35 字**（英文保留詞不計入）；超過時從語意停頓處拆成兩條，各自複製相同的 `start`/`end`
   - **標點符號規範（中文 SRT 慣例）**：
     - 句尾**不加句號**（。）
     - 逗號（，）、頓號（、）改用**半形空格**分隔語意段落
     - 僅在語意必要時保留 ？！…《》「」；冒號（：）可視情況保留
     - 例：`這是範例` 而非 `這是範例。`；`他說 今天天氣很好` 而非 `他說，今天天氣很好。`

   **日文來源（ja）額外規範**：
   - 以中文重述日文意思，不直譯語序
   - 日文人名、地名：有台灣通用譯名者使用譯名，漢字人名可直接保留，不確定者保留日文原名
   - 日文敬語（です、ます等）翻成自然流暢中文，不保留敬語語氣詞

   **音樂術語**：有公認中文譯名者使用中文，無者保留英文：
   chord→和弦、scale→音階、arpeggio→琶音、melody→旋律、harmony→和聲、
   rhythm→節奏、beat→拍子、bar/measure→小節、key→調性、tempo→速度、
   pitch→音高、timbre→音色、transpose→移調、modulation→轉調、
   cadence→終止式、progression→和弦進行、syncopation→切分音、
   loop→循環、mix→混音、master→母帶後製、reverb→殘響、
   delay→延遲效果、compression→壓縮、sample→取樣、track→音軌、
   synth→合成器、producer→製作人、record→唱片、release→發行

2. **輸出格式**（JSON 陣列）：
```json
[
  {
    "src": "Hey there, welcome to a brand new episode of Music Express.",
    "tgt": "大家好，歡迎收看全新一集的 Music Express。",
    "start": 0.54,
    "end": 3.20
  }
]
```
不需要 `word_start`/`word_end`（時間碼已直接是秒數）。

3. 用 Write 工具將結果寫入 `/tmp/_translated_result_<批次編號>.json`（從 0 開始）。每批完成立即寫入。

---

### 步驟 3：組裝 SRT 輸出

所有翻譯批次完成後，執行組裝腳本：

```bash
PYTHON="python3"
[ -f "<PROJECT_ROOT>/.venv/bin/python" ] && PYTHON="<PROJECT_ROOT>/.venv/bin/python"

"$PYTHON" "<PROJECT_ROOT>/scripts/assemble_srt.py" "/tmp" "<INPUT_FILE>"
```

### 步驟 4：清理暫存檔案

```bash
rm -f /tmp/_segments_result_*.json /tmp/_translated_result_*.json
```

### 步驟 5：報告結果

告知用戶：
- 輸出檔案路徑（`.en.srt` 和 `.cht.srt`）
- 總字幕條數
- 翻譯方向
- 提醒：字幕檔與影片同名、同目錄，可直接用 VLC 或播放器載入
