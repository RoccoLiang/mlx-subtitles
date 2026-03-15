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
4. 計算暫存路徑：
   - `VIDEO_STEM`：`INPUT_FILE`（或 `WORDS_JSON`）的主檔名（去掉副檔名和路徑）
   - `TMP_DIR`：`<PROJECT_ROOT>/tmp`
   - `SEG_PREFIX`：`<VIDEO_STEM>_seg`
   - `TR_PREFIX`：`<VIDEO_STEM>_tr`
   - 建立暫存目錄：`mkdir -p "<TMP_DIR>"`

顯示：
```
輸入：<INPUT_FILE>
翻譯方向：<SRC_LANG 全名> → <TGT_LANG 全名>
暫存目錄：<TMP_DIR>
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

**斷點續傳檢查（Step A 開始前）**：

```bash
python3 -c "
import json, glob, os

tmpdir = '<TMP_DIR>'
prefix = '<SEG_PREFIX>'
batch_size = 200
total_words = <TOTAL_WORDS>

files = sorted(glob.glob(os.path.join(tmpdir, prefix + '_*.json')),
               key=lambda x: int(x.rsplit('_', 1)[-1].replace('.json','')))

covered_words = 0
last_good_batch = -1
for f in files:
    n = int(f.rsplit('_', 1)[-1].replace('.json',''))
    expected_start = n * batch_size
    try:
        segs = json.load(open(f, encoding='utf-8'))
        if not segs:
            print(f'EMPTY: batch {n} — will redo')
            os.remove(f)
            break
        # Verify last segment's word_end is within expected range
        last_word_end = segs[-1]['word_end'] + expected_start
        expected_end = min(expected_start + batch_size - 1, total_words - 1)
        if last_word_end < expected_end - 5:  # allow small tolerance
            print(f'INCOMPLETE: batch {n} ends at word {last_word_end}, expected ~{expected_end} — will redo')
            os.remove(f)
            break
        covered_words = last_word_end + 1
        last_good_batch = n
    except Exception as e:
        print(f'INVALID: batch {n} ({e}) — will redo')
        os.remove(f)
        break

next_batch = last_good_batch + 1
next_word = next_batch * batch_size
print(f'Covered words: {covered_words}/{total_words}')
print(f'Next batch: {next_batch} (starting at word {next_word})')
if covered_words >= total_words:
    print('Step A COMPLETE — proceed to Step B')
"
```

從「Next batch」繼續；若輸出 `Step A COMPLETE`，直接進入 Step B。

將單字陣列以 **200 個單字** 為一批，依序處理每批，輸出含時間碼的分句 JSON。

**前置作業（僅第一批執行）**：
掃描前 400 個單字，識別重複出現的專有名詞（人名、地名、節目名、唱片名等），建立統一術語表，後續批次沿用。

**每批操作**：

取本批第 `[global_offset]` 到 `[global_offset + 199]` 個單字（最後一批可能更少）。

1. **分句**：將連續單字組合成自然字幕段落
   - 以標點符號、語意停頓為優先邊界
   - 每句 **不超過 12 個單字**；超過時必須在語意完整處拆成兩條；避免在介詞、連接詞、冠詞後斷句

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

4. 用 Write 工具將結果寫入 `<TMP_DIR>/<SEG_PREFIX>_<批次編號>.json`（從 0 開始）。每批完成立即寫入，不等全部完成。

**Step A 全部批次完成後，才開始 Step B。**

> **Context 提示**：若剛完成 Step A 且批次數超過 15，建議在**新對話**中重新執行相同指令。斷點續傳會自動偵測 Step A 已完成並直接進入 Step B，確保翻譯過程有足夠的 context 空間。

---

## Step B：翻譯

**計算 Step A 總句數**（用 Bash，不把所有 seg 檔載入 context）：

```bash
python3 -c "
import json, glob, os
files = sorted(glob.glob(os.path.join('<TMP_DIR>', '<SEG_PREFIX>_*.json')),
               key=lambda x: int(x.rsplit('_', 1)[-1].replace('.json','')))
total = sum(len(json.load(open(f))) for f in files)
print(f'TOTAL_SENTENCES: {total}')
print(f'Step B 批次數: {-(-total // 200)}')
"
```

記下 `TOTAL_SENTENCES`。

**斷點續傳檢查（Step B 開始前）**：

```bash
python3 -c "
import json, glob, os, sys

tmpdir = '<TMP_DIR>'
prefix = '<TR_PREFIX>'
batch_size = 200
total = <TOTAL_SENTENCES>

files = sorted(glob.glob(os.path.join(tmpdir, prefix + '_*.json')),
               key=lambda x: int(x.rsplit('_', 1)[-1].replace('.json','')))

translated = 0
last_good_batch = -1
for f in files:
    n = int(f.rsplit('_', 1)[-1].replace('.json',''))
    expected = min(batch_size, total - n * batch_size)
    try:
        segs = json.load(open(f, encoding='utf-8'))
        if len(segs) == expected:
            translated += len(segs)
            last_good_batch = n
        else:
            print(f'INCOMPLETE: batch {n} has {len(segs)}/{expected} entries — will redo')
            os.remove(f)
            break
    except Exception as e:
        print(f'INVALID: batch {n} ({e}) — will redo')
        os.remove(f)
        break

print(f'Translated so far: {translated}/{total} sentences')
print(f'Next batch to process: {last_good_batch + 1}')
"
```

從上面輸出的「Next batch to process」編號繼續，跳過已完整的批次。若所有批次都完整（translated == TOTAL_SENTENCES），直接進入步驟 3。

將分句以 **200 句** 為一批，依序翻譯（批次按「句數」計算）。

**每批翻譯操作**：

0. **用 Bash 取出本批資料**（每批各自提取，避免累積大量 context）：

```bash
python3 -c "
import json, glob, os
files = sorted(glob.glob(os.path.join('<TMP_DIR>', '<SEG_PREFIX>_*.json')),
               key=lambda x: int(x.rsplit('_', 1)[-1].replace('.json','')))
all_segs = []
for f in files:
    all_segs.extend(json.load(open(f)))
s = <BATCH_N> * 200
batch = all_segs[s:s+200]
print(json.dumps(
    [{'src': x['src'], 'start': x['start'], 'end': x['end']} for x in batch],
    ensure_ascii=False, indent=2
))
"
```

   對此 Bash 輸出的 JSON 進行翻譯。

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
   - 每條 `tgt` **單行 12–16 字為佳，上限 20 字**（英文保留詞不計入）；最多 2 行；超過時從語意停頓處拆成兩條，各自複製相同的 `start`/`end`
   - **標點符號規範（中文 SRT 業界慣例）**：
     - **刪除**：句尾不加句號（。）；行中不加逗號（，）
     - **替代**：逗號（，）、頓號（、）位置改用**全形空格**（　）分隔語意段落
     - **保留**：語意必要的問號（？）、感嘆號（！）、書名號（《》）、省略號（…）；冒號（：）可視情況保留
     - 例：`這是範例` 而非 `這是範例。`；`他說　今天天氣很好` 而非 `他說，今天天氣很好。`

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

3. 用 Write 工具將結果寫入 `<TMP_DIR>/<TR_PREFIX>_<批次編號>.json`（從 0 開始）。每批完成立即寫入。

---

### 步驟 3：組裝 SRT 輸出

所有翻譯批次完成後，執行組裝腳本：

```bash
PYTHON="python3"
[ -f "<PROJECT_ROOT>/.venv/bin/python" ] && PYTHON="<PROJECT_ROOT>/.venv/bin/python"

"$PYTHON" "<PROJECT_ROOT>/scripts/assemble_srt.py" \
  "<TMP_DIR>" "<INPUT_FILE>" \
  --prefix "<TR_PREFIX>"
```

### 步驟 4：清理暫存檔案

```bash
rm -f "<TMP_DIR>/<SEG_PREFIX>"_*.json "<TMP_DIR>/<TR_PREFIX>"_*.json
```

### 步驟 5：報告結果

告知用戶：
- 輸出檔案路徑（`.en.srt` 和 `.cht.srt`）
- 總字幕條數
- 翻譯方向
- 提醒：字幕檔與影片同名、同目錄，可直接用 VLC 或播放器載入
