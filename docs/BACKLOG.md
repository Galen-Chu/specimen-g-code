# 開發優化盤點 Backlog

> 2026-11-16 首次盤點（Phase 1 後）；**2026-11-18 第二次盤點歸檔（Phase 2 完成後）**。
> README 的 Roadmap 是階段骨架，這裡收集**開放中**的具體工作項與設計輸入（§1–§3）；
> 已完成項歸檔於 §4，已回答的設計問題歸檔於 §5。設計層未決問題在
> [DESIGN.md](DESIGN.md) §8；作業流程章程在 [SOP.md](SOP.md)。

## 1. Phase 3：staining 步驟庫與特徵選取協議（開放）

- **季→日 as-of 對齊步驟（開場第一步）**：[CASE-STUDY-1101TW.md](CASE-STUDY-1101TW.md) §4 排定——季度值經 lag ≥ 90 天 as-of 對齊進日頻特徵表（I3 操作面的第一個登記步驟）。季度原料已備妥：golden `stock-1101-s0` 的 `quarterly` 表（2025Q3–2026Q3）。
- **欄位算術的宣告式程度**（DESIGN 開放問題 2）：從「具名步驟＋參數」開始，DSL 語法後議；第一步是把 CASE-STUDY PDF 第三題的運算（和、差、比、變換）做成可登記的步驟類型。
- **特徵選取協議**（相關分析／MI／RFE）：登記化＝結果（入選欄位＋統計量）寫進 manifest，不可匿名挑欄。
- **目標衍生欄偵測**：I2 閘門的補全——staining 步驟宣告 `derived_from`，閘門掃描目標及其衍生欄（現況：availability 宣告制為閘門，衍生偵測待此處）。

## 2. 生態整合（Phase 4，開放）

- **Unbodysoma 行為標本**：其 `runs/*/signals.csv`＋`events.jsonl` 的契約適配器——M1「N 個體 × M 世界」實驗的資料直接成為可檢驗標本（血緣：個體參數抽樣＋世界 provenance 都已在對方的 manifest/meta）。**SOP 通用化的第一次實戰考驗**（SOP §6 規則一：第二領域落地時，凡是「不改核心就撐不住」之處才是通用化邊界）。
- **sanctuary 世界群標本**：跨種子世界統計（其 Phase 2 輸出）→ 世界標本。
- 依賴方向不變：適配器讀對方的檔案格式，零程式相依。

## 3. 工程與基礎設施（開放）

- **parquet 判準**（DESIGN 開放問題 1）：欄數 > ~500 或型別保真需求出現時引入 `[etl]` 輸出選項；CSV＋golden 是 v0.x 基準。
- **v0.3.0 tag**：Phase 2 完成可標——pyproject／`__version__` 升 0.3.0＋tag；隨 Phase 3 第一個 staining 步驟一併作業亦可。
- **官方季報累積→YTD 差分**：openapi 快照（`--quarterly`，逐季不可變）累積滿兩季後，YTD 差分可得官方單季值，屆時可取代 yfinance 回補（v2 標本）。

## 4. 已完成（歸檔 2026-11-18）

| 項目 | 完成日 | 要點 |
|---|---|---|
| I1/I2/I3 執行期閘門＋切分讀取器 | 2026-11-18 | `invariants.py`：`read_split`（切分屬標本，實驗不得自切）、`check_time_safety`（I1 切分點掃描）、`check_target_purity`（I2：目標不入特徵；非鍵欄位必須宣告 availability——匿名即拒絕）、`check_grain_separation`（I3 結構面，同步入 `validate_manifest` 與 assay 入口） |
| assay 協議 | 2026-11-18 | `assay.py`、`PROTOCOLS` 登記制；入口閘門 protocol→table→I2→I3→hash→〔協議內〕契約→數值／二元→I1；`time-split-baseline`＝constant／logistic／decision_tree／knn（logistic/knn 標準化管線、scaler 只在 train 段 fit，`scaled=1.0` 超參數自述）；`[[assays]]` 只加不寫、寫入後仍可 verify；[ml] 相依只進此層，CI 裝 `.[dev,ml]`、未裝則測試自動略過 |
| 通用 SOP | 2026-11-18 | [SOP.md](SOP.md) v1：五階段 DoD、四閘門對照（每條不變量指向真實檢查器）、manifest 責任表、四領域擴充點、新領域六項驗收清單 |
| `stock_1101` 日頻 | 2026-11-18 | SOP §7 六項驗收全綠：契約先行（availability 全宣告）、七個具名步驟（含無成交日 `--` 丟棄、90 天前瞻缺列丟棄）、切分經標籤分布實測定案（train≤2025-12-31；test＝最後可完整標記窗口，雙類俱全）、34 個月原料副本＋出處註記入 fixtures、golden 釘死、assay 過門（decision_tree ROC-AUC 0.639 最佳；knn 標準化後 0.31→0.52） |
| `stock_1101` 季頻＋歷史季回補 | 2026-11-18 | 原料雙軌：官方快照（openapi.twse.com.tw `t187ap06/07_L_ci`，逐季不可變、向前累積、作血緣與交叉驗證錨點）＋yfinance 回補 2025Q3–2026Q3（宣告式第三方）；三個具名步驟；缺欄季丟棄；單位諧調（TWD→千元）以重疊季 115Q3 交叉驗證釘死（營收／資產總計精確相等）；yf 淨利歸屬口徑較窄，如實宣告。MOPS 舊網域 NXDOMAIN、`mops.twse.com.tw` 查詢端點封鎖非瀏覽器客戶端（存查） |
| 食譜原始碼 hash 入冊（v0.2.0） | 2026-11-18 | manifest 增 `[recipe].source_sha256`；verify 先具名診斷「程式碼漂移／步驟不符／原料 hash 不符」才重跑 I4；golden 曾實抓 ruff format 造成��漂移並重封——機制自證 |
| 驗證與基礎設施強化 | 2026-11-18 | rows 以 csv.reader 計數（引號內換行安全）；catalog 耐壞標本；報告旗標解耦；嚴格日曆日期（`2026-02-31` 拒）；CI 增 3.14 矩陣＋打包安裝 job；`py.typed` 出貨；`prepare --annotate-environment`（opt-in 註記，不影響驗證）；v0.1.0／v0.2.0 tags |

## 5. 已回答的設計問題（歸檔）

| 舊問題 | 答案 |
|---|---|
| 表格式 CSV vs parquet 起手？ | CSV（零相依、hash 友善）；parquet 依 §3 判準（DESIGN 開放問題 1 的範圍收窄） |
| manifest 的 `created`／environment 要自動記錄嗎？ | **不**——決定論優先：兩者皆 opt-in 註記（UI：`prepare --annotate-environment`），避免跨機／跨版本破壞逐位元重現（golden 測試把關） |
| manifest 格式 | 已凍結為 `render_manifest` 的輸出（欄位序、LF、無時鐘），golden 標本逐位元釘死（`tests/golden/demo-vitals-s7/`、`tests/golden/stock-1101-s0/`） |
| 缺值行怎麼辦（demo 食譜的清潔規則） | 已宣告：季頻＝帶 note 的行；日頻缺 close＝不完整、丟棄；重複鍵保留最後——規則寫進食譜 docstring 與 manifest steps |
| 食譜程式碼漂移如何偵測？ | manifest 記錄食譜模組原始碼 sha256（v0.2.0）；verify 比對，不符即「recipe code changed since sealing」——重現證明由**封存時的程式碼**出具，不是今天碰巧裝著的程式碼 |
| MOPS 季報原料哪裡來？ | 官方 opendata 已遷移至 `openapi.twse.com.tw/v1/opendata/`（JSON、快照式、無期間參數）→ 逐季快照向前累積；歷史季以 yfinance 宣告式回補，單位諧調以重疊季交叉驗證（營收／資產精確相等） |
