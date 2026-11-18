# 開發優化盤點 Backlog

> 2026-11-16 盤點（Phase 1 完成後歸檔）。本文件是**跨階段**的開發與優化清單：README 的 Roadmap 是階段骨架，這裡收集具體工作項、設計輸入與工程債；設計層的未決問題在 [DESIGN.md](DESIGN.md) §8。

## 1. Phase 2：assay 協議與第一號真實標本

- **I1/I2 執行期閘門** ✅ 閘門函數落地（2026-11-18，`invariants.py`）：`read_split`（切分讀取器——切分屬標本，實驗不得自切）、`check_time_safety`（I1：切分點掃描，任何標示為 train 的列不得晚於邊界）、`check_target_purity`（I2：目標不得入特徵；非鍵欄位必須宣告 `availability_lag_days`——匿名欄位即拒絕）。**待續**：目標衍生欄偵測隨 Phase 3 staining 登記制落地。
- **assay 協議** ✅（2026-11-18，`assay.py`）：`PROTOCOLS` 登記制——入口順序＝protocol 查表→table 查表→I2 純淨→**I3 粒度**→表完整性（hash）→〔協議內〕契約→數值特徵／二元目標→I1 切分；`time-split-baseline`＝constant／logistic／decision_tree／knn，指標 ROC-AUC／PR-AUC；`[[assays]]` 紀錄（protocol／model／seed／切分身分／超參數／指標）只加不寫，寫入後標本仍可 `verify`。[ml] 相依只進此層；CI 裝 `.[dev,ml]`，未裝 [ml] 時 assay 測試自動略過。
- **通用 SOP** ✅（2026-11-18，[SOP.md](SOP.md)）：五階段進出條件（DoD）、四閘門對照（每條不變量指向真實檢查器）、manifest 登錄責任表、四個領域擴充點（食譜包／契約詞彙／協議登記／擷取適配器）、新領域模組六項驗收清單。配套程式：I3 結構檢查（`grain_problems`＋`check_grain_separation`）入 manifest 驗證與 assay 入口——「assay 前四不變量逐一檢查」自此在程式上完全成立。
- **`stock_1101` 食譜**：依 [CASE-STUDY-1101TW.md](CASE-STUDY-1101TW.md) §4 落地。**原料已定案**（2026-11-18）：opendata 重新爬取——TWSE 官網 `rwd/zh/afterTrading/STOCK_DAY` 逐月 JSON（`scripts/acquire_1101.py`；113/01–115/10 共 34 個月已落地 `data/raw/1101/`，依 .gitignore 政策不入 repo——標本由原料＋食譜＋種子重現）。**待辦**：MOPS 季報 opendata 端點（opendata.tse.com.tw）於作者機器無法解析，可達後擴充爬取腳本；食譜本體（ROC 日期正規化、千分位去逗號、粒度分離、90 天前瞻目標）為下一步。
- ~~**切分應用 API**~~ ✅ `read_split`（2026-11-18）——manifest 登記的邊界是取得 train/valid/test 成員的唯一管道。

## 2. staining 程式庫（Phase 3 設計輸入）

- 欄位算術的**宣告式程度**（DESIGN 開放問題 2）：從「具名步驟＋參數」開始，DSL 語法後議；第一步是把 CASE-STUDY PDF 第三題的運算（和、差、比、變換）做成可登記的步驟類型。
- 特徵選取協議（相關分析／MI／RFE）：登記化＝結果（入選欄位＋統計量）寫進 manifest，不可匿名挑欄。

## 3. 生態整合

- **Unbodysoma 行為標本**：其 `runs/*/signals.csv`＋`events.jsonl` 的契約適配器——M1「N 個體 × M 世界」實驗的資料直接成為可檢驗標本（血緣：個體參數抽樣＋世界 provenance 都已在對方的 manifest/meta）。
- **sanctuary 世界群標本**：跨種子世界統計（其 Phase 2 輸出）→ 世界標本。
- 依賴方向不變：適配器讀對方的檔案格式，零程式相依。

## 4. 工程與基礎設施

- ~~**`py.typed`** 標記~~ ✅ 完成（2026-11-18, v0.2.0；`[tool.setuptools.package-data]` 已配置，CI 打包 job 驗證）。
- **食譜原始碼 hash 入冊** ✅ 完成（2026-11-18, v0.2.0）：manifest 增 `[recipe].source_sha256`；verify 先具名診斷「程式碼漂移／步驟不符／原料 hash 不符」才重跑 I4。
- **驗證與基礎設施強化** ✅ 完成（2026-11-18）：rows 以 csv.reader 計數（引號內換行安全）；catalog 遇壞標本回報不 crash；manifest／integrity 報告旗標解耦；日期改嚴格日曆驗證（`2026-02-31` 不再通過）；CI 增 3.14 矩陣與打包安裝 job。
- **parquet 判準**（DESIGN 開放問題 1）：欄數 > ~500 或型別保真需求出現時引入 `[etl]` 輸出選項；CSV＋golden 是 v0.x 基準。
- **環境記錄 UI**：`prepare --annotate-environment`（決定論優先——環境是註記不是重現輸入，DESIGN §5）。
- ~~**v0.1.0 tag**~~ ✅ v0.1.0 標記於 Phase 1 commit；v0.2.0（manifest 格式增 `source_sha256`）隨後——格式凍結自此起算。

## 5. 已回答的設計問題（歸檔）

| 舊問題 | 答案 |
|---|---|
| 表格式 CSV vs parquet 起手？ | CSV（零相依、hash 友善）；parquet 依 §4 判準（DESIGN 開放問題 1 的範圍收窄） |
| manifest 的 `created`／environment 要自動記錄嗎？ | **不**——決定論優先：兩者皆 opt-in 註記，避免跨機／跨版本破壞逐位元重現（golden 測試把關） |
| manifest 格式 | 已凍結為 `render_manifest` 的輸出（欄位序、LF、無時鐘），golden 標本 `tests/golden/demo-vitals-s7/` 逐位元釘死 |
| 缺值行怎麼辦（demo 食譜的清潔規則） | 已宣告：季頻＝帶 note 的行；日頻缺 close＝不完整、丟棄；重複鍵保留最後——規則寫進食譜 docstring 與 manifest steps |
| 食譜程式碼漂移如何偵測？ | manifest 記錄食譜模組原始碼 sha256（v0.2.0）；verify 比對，不符即「recipe code changed since sealing」——重現證明由**封存時的程式碼**出具，不是今天碰巧裝著的程式碼 |
