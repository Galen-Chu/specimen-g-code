# 標準作業流程 SOP · The General SOP

> 狀態：v1（2026-11-18，Phase 2 中旬制定）。本文件是**通用作業流程**：五階段＋
> 四不變量＋登錄機制跨領域不變；領域差異只落在四個擴充點（§6）。[DESIGN.md](DESIGN.md)
> 是「為什麼」的章程（設計決定與開放問題），本文件是「怎麼跑」的章程——兩者
> 修訂規則見 §8。

## 1. 適用範圍與承諾 · Scope and Promise

適用於任何「把原始資料變成可檢驗證據、並在其上做可比較訓練」的工作：

- **有時間軸的資料**（股價、生理訊號、模擬世界群）——四不變量全額適用。
- **無時間軸的資料**（橫斷面資料）——I1／I3 退化為自動通過：閘門照跑，SOP 不打折。
- 不適用：即時／串流、任意實驗追蹤（DESIGN §1 非目標——那是 cron 與 MLflow 的職位）。

對消費者的承諾（任何領域的標本一體適用）：

| 承諾 | 兌現機制 |
|---|---|
| 標本自描述 | manifest＋契約即可解讀，不需要本專案的程式碼 |
| 逐位元重現 | （原料 hash＋食譜＋種子）→ 相同輸出；食譜原始碼 hash 入冊，程式碼漂移會被 verify 識破 |
| 檢驗可比較 | 切分屬標本（所有 assay 共用）；紀錄含 protocol／model／seed／切分身分／指標 |
| 登錄即不可變 | 封存後輸出不得改動；檢驗紀錄只加不寫；要改＝新版本＋diff |

## 2. 總覽 · Five Stages, Four Gates

```
原料 ──acquisition──► data/raw/（原樣）──preparation──► 單粒度淨表
                                                        │
特徵表 ◄──staining（登記步驟）──┘                        │
   │                                                    │
   ▼                                                    ▼
assay（閘門→訓練→[[assays]] 紀錄）◄──catalog（封存＋verify 四項全綠）◄──┘
```

| # | 階段 | 進入條件 | 離開條件（DoD） | 工具 | 閘門 |
|---|------|---------|----------------|------|------|
| 1 | **acquisition** 擷取 | 原料源確定（端點可重爬） | 原樣位元落地 `data/raw/`；檔名即食譜 inputs | `scripts/acquire_*.py` | 無——原料只進不改 |
| 2 | **preparation** 製備 | 原料 hash 齊 | 單粒度乾淨表；去重規則宣告；缺值規則宣告 | 食譜（領域） | I3 |
| 3 | **staining** 染色 | 分表完成 | 衍生欄全部是**具名登記步驟**；availability 宣告 | 食譜步驟庫 | I2（宣告面） |
| 4 | **catalog** 登錄 | 表＋契約完備 | `verify` 四項全綠（manifest／integrity／contract／reproduce）；golden 釘死 | `prepare`／`verify`／`catalog` | 全部：manifest＝I3 結構、integrity＋reproduce＝I4 |
| 5 | **assay** 檢驗 | 標本已封存 | 基準比較表寫入 `[[assays]]`（只加不寫）；寫入後仍可 verify | `assay`（[ml]） | **入口逐一檢查**（§4） |

## 3. 階段細則 · Stage Rules

每一階段的鐵律——「禁止」欄是 SOP 的靈魂，違反任何一條＝該階段未完成。

**acquisition 擷取**
- 禁止轉換：位元原樣入庫（民國日期、千分位逗號原封不動——轉換屬於食譜）。
- hash 即身分：原料檔名與 sha256 由 manifest 登記，之後任何比對都以 hash 為準。
- 擷取腳本可以重跑、可以增量（已存在檔案跳過）；資料源更新＝新原料＝新標本版本。

**preparation 製備**
- 禁止匿名合併：去重（保留最後？加總？）必須是宣告的規則，寫進食譜 docstring 與 steps。
- 禁止跨粒度 join：不同粒度分表存放（I3）；合併只准 as-of（染色階段的登記步驟）。
- 輸出表必須能通過自己的契約——鍵唯一、型別、範圍。

**staining 染色**
- 禁止匿名 lambda：每個衍生欄位是具名步驟＋參數（欄位算術 DSL 的粒度是 Phase 3 議題）。
- 每個非鍵欄位宣告 `availability_lag_days`——assay 門口對未宣告欄位直接拒絕。
- 目標欄位（label）本身也是宣告的步驟產物（例如「90 天後報酬 ≥10%」），可追溯。

**catalog 登錄**
- 封存＝不可變：輸出與契約自此不得改動；要改＝新版本目錄＋diff 報告。
- manifest 完備性由 `validate_manifest` 把關（結構、hash 長度、粒度一致性＝I3 結構面）。
- 驗收：`verify <dir> --raw <dir>` 四項全綠；CI 對 golden 標本逐位元釘死。

**assay 檢驗**
- 禁止自切：train/valid/test 只能來自 `read_split`＋manifest 登記的邊界。
- 禁止目標入特徵；禁止匿名可用性（I2）；禁止粒度漂移的 manifest（I3）。
- 轉換器只在 train 段 fit（I1）：尺度敏感模型（logistic／knn）的標準化包在管線內，
  紀錄以 `scaled` 超參數自述。
- 紀錄只加不寫：`[[assays]]` 不可覆寫或刪改；重跑＝新紀錄。
- 指標是「一次執行的註記」：同環境可重現，跨環境僅供參考（[ml] 版本敏感）。

## 4. 四不變量＝四道閘門 · Invariants as Gates

| # | 不變量 | 檢查器（程式） | 執行時點 | 拒絕方式 |
|---|--------|---------------|---------|---------|
| I1 | 時間安全 | `read_split`＋`check_time_safety` | assay 入口 | 任何 train 列晚於邊界即拒 |
| I2 | 目標純淨 | `check_target_purity` | assay 入口 | 目標入特徵／未宣告 availability／負 lag 即拒 |
| I3 | 粒度分離 | `check_grain_separation`（＋`validate_manifest` 結構面） | 封存時＋assay 入口 | 契約與輸出粒度不一致／粒度名不合格即拒 |
| I4 | 逐位元重現 | `verify`（integrity＋reproduce）；golden 測試 | 封存後任何時點；CI | hash 不符／重跑輸出相異／程式碼漂移即拒（具名） |

assay 入口的完整順序（拒絕而非警告）：
`protocol 查表 → table 查表 → I2 純淨 → I3 粒度 → 表 hash 完整性 →［協議內：契約驗證 → 數值特徵／二元目標 → I1 切分 → 訓練］`

## 5. 登錄機制 · The Registry

manifest 各節的填寫者與不變性（格式由 `render_manifest` 決定論輸出，golden 釘死）：

| 節 | 內容 | 填寫者 | 不變性 |
|---|------|--------|--------|
| `[specimen]` | 名稱、版本、種子 | `prepare` | 封存後不可變 |
| `[recipe]` | 模組、步驟清單、**原始碼 hash** | 食譜註冊表 | 封存後不可變；漂移由 verify 識破 |
| `[[recipe.inputs]]` | 原料檔名＋sha256 | `prepare` | 封存後不可變 |
| `[splits]` | 切分法＋邊界 | 食譜宣告 | 封存後不可變——所有 assay 共用 |
| `[[outputs]]` | 表名、粒度、檔名、hash、列數 | `prepare` | 封存後不可變 |
| `[contracts.*]` | 鍵、欄位型別、範圍、availability | 食譜宣告 | 封存後不可變 |
| `[[assays]]` | protocol／model／seed／切分身分／超參數／指標 | `assay` | **只加不寫** |
| `created`／`environment` | 註記 | opt-in | 註記，非重現輸入 |

## 6. 領域擴充點 · The Four Extension Points

通用骨架不因領域改動；領域差異**只准**落在以下四處（刀片層）：

| 擴充點 | 領域差異所在 | 機制 | 既有實例 |
|---|---|---|---|
| **食譜包** recipe pack | 清洗與轉換邏輯 | `specimen/recipes/<domain>/`＋`REGISTRY` 登記 | `demo_vitals`（demo）；`stock_1101`（金融，已落地——日頻） |
| **契約詞彙** vocabulary | 欄位語義（揭露延遲 vs 取樣延遲；未來的事件區間等） | `ColumnSpec` 詞彙擴充，不另起系統 | `availability_lag_days` |
| **assay 協議** protocol | 評測形態（分類／迴歸／其他） | `PROTOCOLS` 登記制，同一 `[[assays]]` 章節收紀錄 | `time-split-baseline` |
| **擷取適配器** adapter | 各資料源的抓取 | `scripts/acquire_*.py`（純 stdlib） | `acquire_1101.py` |

三條判斷規則：

1. **第二領域落地前不抽象**——新領域適配時，凡是「不改核心就撐不住」的地方才是
   真正的通用化邊界；屆時才抽離，並以 DESIGN 章節更新記錄。預先設計通用框架
   幾乎一定猜錯。
2. **差異只在刀片層**——若某領域需求必須改 manifest 格式或四不變量定義本身，
   那是重大設計事件：先 ADR（DESIGN 開放問題 6），再動工。
3. **同套驗收**——領域模組是「用 SOP 的模組」，不是「SOP 的分身」；下節清單
   一體適用。

## 7. 新領域模組驗收清單 · Domain Acceptance Checklist

一個領域模組（食譜包）落地＝以下六項全綠，缺一不可：

1. **契約先行**：每張表宣告鍵（含 date 型別鍵欄）、粒度、欄位型別與範圍；
   非鍵欄位宣告 `availability_lag_days`。
2. **食譜登記**：`REGISTRY` 條目齊全（module／source hash／steps 具名／inputs／
   contracts／splits）；清洗與缺值規則寫進 docstring。
3. **製備可封存**：`prepare` 成功且 `validate_manifest` 零問題。
4. **verify 四項全綠**：manifest／integrity／contract／reproduce（帶 `--raw`）。
5. **golden 釘死**：提交 golden 標本（或 CI 可重跑的 fixture 子集）逐位元比對。
6. **assay 過門**：入口四閘門通過後跑 `time-split-baseline`，`[[assays]]` 寫入
   且事後 `verify` 仍 PASS。

## 8. 指令對照 · CLI Reference

```bash
specimen prepare <recipe> --seed N --raw <dir> --out <dir>   # 製備＋封存
specimen verify  <dir> [--raw <dir>]                          # 四項檢查；exit 0/1
specimen catalog <root>                                       # 標本清單（壞標本會被點名）
specimen assay   <dir> --table T --target Y --features a,b [--seed N]   # 需 [ml]；拒跑 exit 2
```

`verify` 報告的四種結果行：`manifest:`（結構＋I3）、`integrity:`（I4 封存面）、
`contract:`（契約）、`reproduce:`（I4 重現面——含「recipe code changed since
sealing」的程式碼漂移具名診斷）。

## 9. 修訂規則 · Revision

- 動**四不變量定義**或**五階段結構**：先 ADR（DESIGN 開放問題 6 的機制），
  再改本文件並註明日期。
- 動階段細則、閘門順序、擴充點：直接更新本文件＋日期。
- 本文件的每一條「檢查器」欄必須指向真實存在的函數——文件與程式碼同時修訂，
  不允許文件承諾程式沒有的閘門。
