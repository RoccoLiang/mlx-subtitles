---
description: "讀取 .words.json 單字時間碼，分句翻譯並輸出雙語 ASS 字幕"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# 影片字幕翻譯技能

讀取 mlx-whisper 產生的 `.words.json` 單字時間碼檔案，由 Claude 自行決定自然分句邊界，翻譯成正體中文（台灣用語），輸出雙語 ASS 字幕。輸出檔名與影片主檔名一致，方便播放器自動載入。

**輸入格式**: `$ARGUMENTS`

**語法**: `<影片路徑或 words.json 路徑> [來源語言>目標語言]`

**範例**:
- `/translate-ass input/video.mp4` → 自動找到對應 words.json，翻譯成繁體中文
- `/translate-ass output/video.words.json` → 直接指定 words.json
- `/translate-ass input/video.mp4 en>zh` → 明確指定語言對

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

記下總單字數 `TOTAL_WORDS`。

### 步驟 3：分批分句翻譯

將單字陣列以 **200 個單字** 為一批，依序處理每批。

**翻譯前置作業（僅第一批執行）**：
掃描前 400 個單字，識別重複出現的專有名詞（人名、地名、節目名、唱片名等），建立統一譯名表，後續批次沿用。

**每批操作**：

將本批單字以空格串接成原文，請 Claude 完成：

1. **分句**：將連續單字組合成自然字幕段落
   - 以標點符號、語意停頓為優先邊界
   - **英文來源（en）**：每句 **不超過 12 個單字**；超過時必須在語意完整處拆成兩條；避免在介詞、連接詞、冠詞後斷句
   - **日文來源（ja）**：每句目標 15–30 個字符；`src` 欄位輸出自然日文句子（字符間不加空格）
   - **中文譯文**：每條 `tgt` **不超過 20 個字**（含夾雜的英文字符）；超過時將該句拆成兩條分別輸出

2. **翻譯**：將每個分句翻譯成正體中文（台灣用語）

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

3. **輸出格式**（JSON 陣列）：
```json
[
  {
    "src": "Hey there, welcome to a brand new episode of Music Express.",
    "tgt": "大家好，歡迎收看全新一集的 Music Express。",
    "word_start": 0,
    "word_end": 9
  }
]
```
`word_start` / `word_end` 為本批次內的單字索引（0-based，含頭含尾）。

4. 用 Write 工具將結果寫入 `/tmp/_words_result_<批次編號>.json`（從 0 開始）。每批完成立即寫入，不等全部完成。

### 步驟 4：組裝 ASS 輸出

所有批次完成後，執行組裝腳本：

```bash
PYTHON="python3"
[ -f "<PROJECT_ROOT>/.venv/bin/python" ] && PYTHON="<PROJECT_ROOT>/.venv/bin/python"

"$PYTHON" "<PROJECT_ROOT>/scripts/assemble_ass.py" "/tmp" "$WORDS_JSON" "<INPUT_FILE>"
```

### 步驟 5：清理暫存檔案

```bash
rm -f /tmp/_words_result_*.json
```

### 步驟 6：報告結果

告知用戶：
- 輸出檔案路徑（`.ass`）
- 總字幕條數
- 翻譯方向
- 提醒：字幕檔與影片同名、同目錄

---

## ASS 樣式說明

| Style | 字體 | 大小 | 顏色 | 位置（MarginV）|
|-------|------|------|------|----------------|
| ZH    | Noto Sans CJK TC | 52 | 白色 | 62px（中文，上方）|
| EN    | Noto Sans | 26 | 淡灰 | 14px（原文，底部）|

畫面效果（底部）：
```
│  中文字幕在這裡（白色大字）  │
│  English subtitle (灰色小字) │
└──────────────────────────────┘
```
