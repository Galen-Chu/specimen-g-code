# 開發優化盤點 Backlog

> 2026-11-16 盤點（Phase 1 完成後歸檔）。本文件是**跨階段**的開發與優化清單：README 的 Roadmap 是階段骨架，這裡收集具體工作項、設計輸入與工程債；設計層的未決問題在 [DESIGN.md](DESIGN.md) §8。

## 1. Phase 2：assay 協議與第一號真實標本

- **I1/I2 執行期閘門**：契約已宣告 `availability_lag_days`（I2）與時間切分（I1 結構）；Phase 2 要在 assay 入口真正執行——切分點掃描（train 不得晚於 test）與特徵可用時間檢查（目標及其同期衍生欄排除）。
- **assay 協議**：`specimen assay <dir> --protocol time-split-baseline`——在登記的切分上跑基準模型比較表（logistic／決策樹／KNN／常數基準），超參數＋種子＋指標寫回 manifest 的 `[[assays]]`（只加不寫）。評測指標從分類 ROC-AUC／PR-AUC 起步（[ml] 選配相依只進 assay 層）。
- **`stock_1101` 食譜**：依 [CASE-STUDY-1101TW.md](CASE-STUDY-1101TW.md) §4 落地。**前置決定**：原料來源——補齊評測環境的原始 JSON，或以 repo 現有 CSV 當「已製備 v0」原料（案例研究 §1 的待決項）。
- **切分應用 API**：manifest 已登記邊界；Phase 2 給 assay 一個讀取器（哪段屬 train/valid/test），杜絕各實驗自切。

## 2. staining 程式庫（Phase 3 設計輸入）

- 欄位算術的**宣告式程度**（DESIGN 開放問題 2）：從「具名步驟＋參數」開始，DSL 語法後議；第一步是把 CASE-STUDY PDF 第三題的運算（和、差、比、變換）做成可登記的步驟類型。
- 特徵選取協議（相關分析／MI／RFE）：登記化＝結果（入選欄位＋統計量）寫進 manifest，不可匿名挑欄。

## 3. 生態整合

- **Unbodysoma 行為標本**：其 `runs/*/signals.csv`＋`events.jsonl` 的契約適配器——M1「N 個體 × M 世界」實驗的資料直接成為可檢驗標本（血緣：個體參數抽樣＋世界 provenance 都已在對方的 manifest/meta）。
- **sanctuary 世界群標本**：跨種子世界統計（其 Phase 2 輸出）→ 世界標本。
- 依賴方向不變：適配器讀對方的檔案格式，零程式相依。

## 4. 工程與基礎設施

- **`py.typed`** 標記（mypy strict 已綠）。
- **parquet 判準**（DESIGN 開放問題 1）：欄數 > ~500 或型別保真需求出現時引入 `[etl]` 輸出選項；CSV＋golden 是 v0.x 基準。
- **環境記錄 UI**：`prepare --annotate-environment`（決定論優先——環境是註記不是重現輸入，DESIGN §5）。
- **v0.1.0 tag**：Phase 1 已完成、golden 釘死格式——可直接打 tag； Phase 2 前若有生態消費者（Unbodysoma M1）會需要穩定介面。

## 5. 已回答的設計問題（歸檔）

| 舊問題 | 答案 |
|---|---|
| 表格式 CSV vs parquet 起手？ | CSV（零相依、hash 友善）；parquet 依 §4 判準（DESIGN 開放問題 1 的範圍收窄） |
| manifest 的 `created`／environment 要自動記錄嗎？ | **不**——決定論優先：兩者皆 opt-in 註記，避免跨機／跨版本破壞逐位元重現（golden 測試把關） |
| manifest 格式 | 已凍結為 `render_manifest` 的輸出（欄位序、LF、無時鐘），golden 標本 `tests/golden/demo-vitals-s7/` 逐位元釘死 |
| 缺值行怎麼辦（demo 食譜的清潔規則） | 已宣告：季頻＝帶 note 的行；日頻缺 close＝不完整、丟棄；重複鍵保留最後——規則寫進食譜 docstring 與 manifest steps |
