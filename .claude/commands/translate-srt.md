---
description: "讀取 .words.json 單字時間碼，分句翻譯並輸出雙語 ASS 字幕"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# 影片字幕翻譯技能

讀取 mlx-whisper 產生的 `.words.json` 單字時間碼檔案，由 Claude 自行決定自然分句邊界，翻譯成正體中文（台灣用語），輸出雙語 ASS 字幕。輸出檔名與影片主檔名一致，方便播放器自動載入。

**輸入格式**: `$ARGUMENTS`

**語法**: `<影片路徑或 words.json 路徑> [來源語言>目標語言]`

**範例**:
- `/translate-srt input/video.mp4` → 自動找到對應 words.json，翻譯成繁體中文
- `/translate-srt output/video.words.json` → 直接指定 words.json
- `/translate-srt input/video.mp4 en>zh` → 明確指定語言對

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
   - **英文來源（en）**：每句目標 8–15 個單字；避免在介詞、連接詞、冠詞後斷句
   - **日文來源（ja）**：每句目標 15–40 個字符；`src` 欄位輸出自然日文句子（字符間不加空格）

2. **翻譯**：將每個分句翻譯成正體中文（台灣用語）

   **通用翻譯規範**：
   - 影視翻譯風格，口語自然流暢
   - 保持語意準確，不過度意譯
   - 同一人名全片保持一致譯法
   - 專有名詞（品牌、技術術語）可保留原文

   **繁體中文（zh）額外規範**：
   - 使用台灣慣用繁體中文及口語表達
   - 絕對不可在人名音譯中使用「乘」（U+4E58）
   - 人名音譯標準用字：D→德/戴/迪，T→特/泰，W→威/溫，B→布/博，M→馬/曼，R→羅/瑞，Ch→查/奇

   **日文來源（ja）額外規範**：
   - 以中文重述日文意思，不直譯語序
   - 日文人名、地名優先使用台灣慣用漢字或譯名；漢字人名可直接保留
   - 日文敬語（です、ます等）翻成自然流暢中文，不保留敬語語氣詞
   - 不確定的人名直接保留日文原名

   **音樂術語標準譯名**：
   chord→和弦、scale→音階、arpeggio→琶音、melody→旋律、harmony→和聲、
   rhythm→節奏、beat→拍子、bar/measure→小節、key→調性、tempo→速度、
   pitch→音高、timbre→音色、transpose→移調、modulation→轉調、
   cadence→終止式、progression→和弦進行、syncopation→切分音、
   loop→循環、DAW→數位音樂工作站、MIDI→MIDI、plugin→插件、
   mix→混音、master→母帶後製、EQ→等化器、reverb→殘響、
   delay→延遲效果、compression→壓縮、sample→取樣、track→音軌、
   synth→合成器、producer→製作人、DJ→DJ、record→唱片、release→發行

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

所有批次完成後，執行以下 Python 腳本：

```bash
python3 -c '
import json, os, sys, re, bisect

TMPDIR     = sys.argv[1]
WORDS_JSON = sys.argv[2]
INPUT_FILE = sys.argv[3] if len(sys.argv) > 3 else ""

HOLD_TIME = 0.4   # 字幕結束後額外停留秒數

with open(WORDS_JSON, encoding="utf-8") as f:
    words = json.load(f)

# 收集所有批次結果（word_start/word_end 僅供參考，不直接用於時間碼）
all_sentences = []
i = 0
while True:
    p = os.path.join(TMPDIR, f"_words_result_{i}.json")
    if not os.path.exists(p):
        break
    with open(p, encoding="utf-8") as f:
        batch = json.load(f)
    all_sentences.extend(batch)
    i += 1

# 清理單字：保留 ASCII 英數 及 Unicode 文字（支援日文 / 中文）
def wclean(w):
    return re.sub(r"[^\w]", "", w, flags=re.UNICODE).lower()

wc = [wclean(w["word"]) for w in words]

def wc2(i):
    """合併相鄰兩個 token（處理 'JP' + '-8000' → 'jp8000' 的情形）"""
    return wc[i] + (wc[i+1] if i+1 < len(wc) else "")

# 預先建立連接字串與起始位置表（供 CJK 字符級比對使用）
wcat = "".join(wc)
wcat_starts = []
pos = 0
for tok in wc:
    wcat_starts.append(pos)
    pos += len(tok)

def is_cjk(text):
    """判斷文字是否以 CJK（日文 / 中文）為主。"""
    cjk = sum(1 for c in text if "\u3040" <= c <= "\u9fff")
    asc = sum(1 for c in text if c.isascii() and c.isalnum())
    return cjk > max(asc, 2)

def find_start(src_text, search_from, window=150):
    """在 words.json 中順序比對 src_text 的起始位置。"""
    src_clean = wclean(src_text)
    if not src_clean:
        return None

    if is_cjk(src_clean):
        # CJK 模式：以字符子串比對
        anchor = src_clean[:6]
        lo = wcat_starts[max(0, search_from - 3)]
        hi = wcat_starts[min(search_from + window, len(wc) - 1)] + 10
        idx = wcat.find(anchor, lo, hi)
        if idx == -1:
            anchor = src_clean[:3]
            idx = wcat.find(anchor, max(0, lo - 30), hi + 30)
        if idx == -1:
            return None
        return max(0, bisect.bisect_right(wcat_starts, idx) - 1)

    else:
        # 英文模式：以空格分詞比對
        toks = [wclean(w) for w in src_text.split() if wclean(w)]
        anchor = toks[:3]
        if not anchor:
            return None
        best_score, best_pos = 0, None
        for j in range(max(0, search_from - 3), min(search_from + window, len(wc))):
            score = 0
            for k, a in enumerate(anchor):
                idx = j + k
                if idx >= len(wc):
                    break
                w = wc[idx]
                # 允許：精確比對、前綴比對、或合併兩 token 後比對
                if a and w and (w == a
                                or (len(a) >= 4 and (w.startswith(a[:4]) or wc2(idx).startswith(a[:4])))
                                or (len(w) >= 4 and a.startswith(w[:4]))):
                    score += 1
            if score > best_score:
                best_score, best_pos = score, j
            if score == len(anchor):
                break
        return best_pos if best_score >= min(2, len(anchor)) else None

def find_end(start, src_text, extra=12):
    """從 start 往後找 src_text 最後幾個字的結束位置。"""
    src_clean = wclean(src_text)

    if is_cjk(src_clean):
        # CJK 模式：以末尾字符子串比對
        anchor = src_clean[-4:]
        lo = wcat_starts[start]
        hi = min(lo + len(src_clean) + 30, len(wcat))
        idx = wcat.rfind(anchor, lo, hi)
        if idx == -1:
            return min(start + max(1, len(src_clean) // 2), len(words) - 1)
        return min(max(start, bisect.bisect_right(wcat_starts, idx) - 1), len(words) - 1)

    else:
        # 英文模式
        last_toks = [wclean(w) for w in src_text.split()[-3:] if wclean(w)]
        end_pos = start
        n = len(src_text.split())
        for j in range(start, min(start + n + extra, len(wc))):
            w = wc[j]
            for lw in last_toks:
                if lw and w and (w == lw
                                 or wc2(j) == lw
                                 or (len(lw) >= 4 and (w.startswith(lw[:4]) or lw.startswith(w[:4])))):
                    end_pos = j
        return min(end_pos, len(words) - 1)

def sec_to_ass(s):
    ms = int(round(s * 1000))
    h  = ms // 3_600_000; ms %= 3_600_000
    m  = ms // 60_000;    ms %= 60_000
    sc = ms // 1000;      ms %= 1000
    return f"{h}:{m:02d}:{sc:02d}.{ms//10:02d}"

def clean_zh(text):
    # 移除字幕不適用的句末標點
    text = text.strip()
    text = re.sub(r"[。！？]+$", "", text)
    # 雙破折號統一為單破折號
    text = text.replace("——", "—")
    return text

# 對每條字幕做順序文字比對，取得精確時間碼
# （不依賴 word_start/word_end 索引，避免 token 拆分造成的累積偏移）
timings = []
search_from = 0
WATERMARK = re.compile(r"amara\.org|subtitles by the|opensubtitles", re.I)
for entry in all_sentences:
    src = entry.get("src", "")
    pos = find_start(src, search_from)
    if pos is not None:
        end_pos = find_end(pos, src)
        t_s = words[pos]["start"]
        t_e = words[end_pos]["end"]
        if t_e <= t_s:
            t_e = t_s + 0.5
        search_from = max(search_from, pos + max(1, len(src.split()) // 2))
    else:
        # fallback：沿用上一條的結束時間
        t_s = timings[-1][1] if timings else 0
        t_e = t_s + 1.5
    timings.append((t_s, t_e))

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ZH,Noto Sans CJK TC,60,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,10,10,80,1
Style: EN,Noto Sans,36,&H00CCCCCC,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,10,10,38,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""

lines = [ASS_HEADER]
for idx, entry in enumerate(all_sentences):
    if WATERMARK.search(entry.get("src","")) or WATERMARK.search(entry.get("tgt","")):
        continue
    t_s, t_e = timings[idx]

    # hold time：延長結束時間，但不超過下一條的開始時間
    next_start = timings[idx + 1][0] if idx + 1 < len(timings) else t_e + HOLD_TIME
    t_e = min(t_e + HOLD_TIME, next_start)

    s = sec_to_ass(t_s)
    e = sec_to_ass(t_e)

    zh = clean_zh(entry["tgt"]).replace("\n", "\\N")
    en = entry["src"].strip().replace("\n", "\\N")

    # ZH 行中的 ASCII 片段強制套用同字體，確保中英混排大小一致
    zh_ass = re.sub(r"([A-Za-z0-9][A-Za-z0-9 \-\.\']*[A-Za-z0-9]|[A-Za-z0-9])",
                    r"{\\fnNoto Sans CJK TC}\1{\\fnNoto Sans CJK TC}", zh)

    lines.append(f"Dialogue: 0,{s},{e},ZH,,0,0,0,,{zh_ass}")
    lines.append(f"Dialogue: 0,{s},{e},EN,,0,0,0,,{en}")

if INPUT_FILE:
    out = os.path.splitext(INPUT_FILE)[0] + ".ass"
else:
    out = os.path.join(TMPDIR, "output.ass")

with open(out, "w", encoding="utf-8-sig") as f:
    f.write("\n".join(lines) + "\n")

print(f"ASS 輸出至: {out}")
print(f"共 {len(all_sentences)} 條字幕")
' "/tmp" "$WORDS_JSON" "<INPUT_FILE>"
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
- 提醒：檔名與影片主檔名一致，IINA / VLC / mpv 會自動載入

---

## ASS 樣式說明

| Style | 字體 | 大小 | 顏色 | 位置（MarginV）|
|-------|------|------|------|----------------|
| ZH    | Noto Sans CJK TC | 60 | 白色 | 80px（中文，上方）|
| EN    | Noto Sans | 36 | 淡灰 | 38px（原文，底部）|

畫面效果（底部）：
```
│  中文字幕在這裡（白色大字）  │
│  English subtitle (灰色小字) │
└──────────────────────────────┘
```
