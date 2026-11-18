# 設計文件 Design

> 狀態：Phase 1 已實作（2026-11-16）——§2 的 manifest 格式即 `render_manifest` 的
> 實際輸出，由 golden 標本（`tests/golden/demo-vitals-s7/`）逐位元釘死；`created`
> 與 `environment` 為 **opt-in 註記**（自動記錄會破壞跨機逐位元重現）。v0.2.0
> （2026-11-18）：manifest 增 `[recipe].source_sha256`（食譜原始碼身分），verify
> 對程式碼漂移拒絕出具 I4 證明。Phase 2 進行中（2026-11-18）：`invariants.py`
> 閘門、`assay.py`（time-split-baseline）與 `[[assays]]` 登記已實作。難以反悔的
> 決定以本文件章節更新並註明日期；工作項清單見 [BACKLOG.md](BACKLOG.md)。

## 1. 目標與非目標

**目標**

- 原始資料 → **標本**：登記在冊、防洩漏、逐位元可重現的資料束（表＋契約＋
  血緣＋切分），並在其上執行**可比較**的訓練／選模協議。
- 四不變量（§4）是執行期閘門：assay 在不變量未過時拒絕執行，而不是事後告警。
- 服務整個 G-Code 生態：外生標本（股市資料等）與內生標本（Unbodysoma 的
  `signals.csv`、sanctuary 的世界群）同一套登錄與檢驗標準。

**非目標**

- 不是資料庫、不是排程器（ETL orchestration 交給 cron／GitHub Actions——
  CLI-first 生態約束）。
- 不是視覺化工具（評估報告是登記的資料檔，不是儀表板）。
- 不做即時／串流：標本是批次製備的產物，天然不可變。
- 不是通用 ML 平台：assay 協議收斂於「時間切分＋基準比較表」，不是任意
  實驗追蹤（那是 MLflow 的職位）。

## 2. 標本資料模型 The Specimen Model

一個標本是一個目錄，核心是 `manifest.toml`（登錄即不可變；改內容＝製作新版本）：

```toml
# specimens/stock-1101/v1/manifest.toml（草案）
[specimen]
name = "stock-1101"
version = 1
created = "2026-11-16"        # 資訊性；重現不依賴時間戳
seed = 0

[recipe]                       # 重跑此清單應逐位元重建 outputs
module = "specimen.recipes.stock_1101"
steps = ["flatten", "split_grains", "normalize_dates", "dedupe", "asof_align"]
source_sha256 = "…"            # 食譜原始碼身分；verify 據此識破程式碼漂移（v0.2.0）
inputs = [
  { path = "data/raw/1101.json", sha256 = "…" },
]

[[outputs]]
name = "daily"                 # 日頻價格＋技術指標
grain = "daily"                # 每列＝一個 (symbol, date)
file = "daily.csv"
sha256 = "…"
rows = 248

[[outputs]]
name = "quarterly"             # 季頻財報成長／比率
grain = "quarterly"            # 每列＝一個 (symbol, quarter)
file = "quarterly.csv"
sha256 = "…"

# 每張表附帶契約（schema 章節；see §3）
[outputs.daily.contract]
key = ["symbol", "date"]
columns.date = { type = "date", unique = true }
columns.close = { type = "float", range = [0.0, null] }
# …

[splits]                       # 切分是標本的一部分，不是 assay 的自由裁量
method = "time-ordered"
train_end = "2023-01-01"
valid_end = "2023-07-01"

[[assays]]                     # 檢驗紀錄：可累加，永不覆寫（assay runner 寫入）
protocol = "time-split-baseline"
model = "logistic"
seed = 7
train_end = "2023-01-01"       # 切分身分隨紀錄走（開放問題 3 的最低要求）
valid_end = "2023-07-01"
[assays.hyperparams]
C = 1.0
[assays.metrics]
roc_auc = 0.0
pr_auc = 0.0
```

規則：

- **不可變**：`catalog` 封存後任何檔案不得改動；新版本＝新目錄＋diff 報告。
- **血緣完備**：原料帶 hash、輸出帶 hash、食譜帶模組、步驟清單與原始碼 hash
  （v0.2.0）——重現的依據只剩「當時的程式碼與環境」本身，而程式碼漂移由
  `verify` 對照 source_sha256 識破（見 §5）。
- **切分屬於標本**：train/valid/test 邊界登記在 manifest，所有 assay 共用，
  杜絕「每個實驗自己切、結果不可比」。
- 表格式 v0.1 用 CSV（零相依、hash 友善）；parquet 列為開放問題 1。

## 3. 管線五階段與契約

| 階段 | 輸入 | 輸出 | 契約要點 |
|---|---|---|---|
| acquisition | 外部資料 | `data/raw/`＋hash | 原料只進不改；hash 即身分 |
| preparation | 原料 | 乾淨的粒度分表 | 格式統一、去重有語意（合併規則宣告，不是隱含）；粒度混拌在此終結 |
| staining | 分表 | 特徵表 | 衍生欄位全部是登記的宣告式步驟（欄位算術 DSL）；禁止匿名 lambda |
| catalog | 表＋契約 | 封存標本 | schema 驗證通過才可封存；manifest 完備性檢查 |
| assay | 標本 | 評估紀錄 | 四不變量閘門→時間切分訓練→基準比較表→結果回寫 |

## 4. 四不變量 The Four Invariants

來源：[CASE-STUDY-1101TW.md](CASE-STUDY-1101TW.md) 的缺口分析。每一條對應
一個測試模組與一個執行期檢查器（`invariants.py`）：

| # | 不變量 | 失敗案例（評測 code 實例） | 檢查方式 |
|---|--------|--------------------------|---------|
| I1 | 時間安全：切分按時間序；填充／標準化只在 train 段 fit | 全資料 `ffill().bfill()` 後隨機 `train_test_split` | 切分點掃描：任一 train 列的時間戳必須早於任一 test 列；轉換器宣告 fit 範圍 |
| I2 | 目標純淨：特徵不含同期不可得欄位 | 以同季 `growthNetIncome` 等預測 `netIncomeGrowth` | 欄位可用時間（availability lag）登記於契約；assay 前掃描目標及其衍生欄 |
| I3 | 粒度分離：不同粒度分表；合併一律 as-of | 日頻行的季報欄位被 `fillna(0)` 灌成假值 | manifest 的 outputs 各帶 grain；join 只允許 as-of 算子 |
| I4 | 逐位元重現：（原料＋食譜＋種子）→ 相同輸出 | 可重現性只有 `random_state=42` | `specimen verify` 重跑食譜比對輸出 hash；CI golden 釘死 |

## 5. 決定論與相依政策

- **核心零相依**（manifest／contract／catalog／invariants／assay 協議）：
  純 stdlib。食譜按需選用 `[etl]`（pandas）、`[ml]`（scikit-learn）。
- **種子決定一切**：同一（原料 hash＋食譜＋種子）必須產出逐位元相同的標本——
  浮點格式化沿用 sanctuary 的定位輸出策略；CSV 以 LF 寫出。
- **環境是註記，不是輸入**：`created`／`environment` 皆 opt-in——自動記錄會破壞
  跨機逐位元重現。程式碼身分釘在食譜層（2026-11-18, v0.2.0）：manifest 記錄
  食譜模組原始碼的 sha256，`verify` 比對不符即判定「程式碼已漂移」，拒絕出具
  逐位元重現證明——逐位元重現在 Python 生態是版本敏感的，誠實面對比假裝不敏感好。

## 6. 與生態系的介面

| 方向 | 介面 |
|---|---|
| 吃 sanctuary | 世界群（N 顆種子的 world TOML／統計量）→ 世界標本 |
| 吃 Unbodysoma | `runs/*/signals.csv`、`events.jsonl` → 行為標本（Phase 3 學習心智的訓練語料） |
| 吐 Health-Inbody | M6 預測模型以 assay 協議訓練與比較 |
| 吐 任何專案 | 標本是自描述的：manifest＋契約即可解讀，不需要本專案的程式碼 |

## 7. 命名與隱喻

「specimen」的選擇（相對於 schema／simulation）記錄於設計討論：本專案的本體
是**產物與流程**（名詞＋生命週期），不是**契約**（schema 只覆蓋登錄章節，
是 §2 的 `[outputs.*.contract]`）；也不是**模擬**（那是 Unbodysoma 與
sanctuary 的職掌）。schema 作為章節名保留在契約層，未來若需獨立，從
`contract.py` 分離（開放問題 5）。

## 8. 開放問題

1. **表格式**：CSV（零相依）起手，何時引入 parquet（`[etl]` extra）？判準：
   欄數超過多少或型別保真需求出現時。
2. **staining DSL 的宣告式程度**：欄位算術登記到什麼粒度（表達力 vs 可審查性）？
   先從「具名步驟＋參數」開始，DSL 語法 Phase 3 再議。
3. **assay 登記深度**：模型係數／超參數／指標要存多少才叫可重現？最低要求：
   超參數＋種子＋評估指標＋切分版本。
4. **標本命名與版本政策**：比照 sanctuary 的 `name@version` provenance？
   （傾向：是——manifest 已有 version 欄。）
5. **schema 章節獨立化**：`contract.py` 是否在成熟後獨立成模組（保留
   schema-g-code 名）？判準：出現契約層的非標本消費者時。
6. **ADR 文化**：本專案是否採用 Unbodysoma 式 ADR？Phase 1 第一個難以反悔
   的決定出現時決定。
