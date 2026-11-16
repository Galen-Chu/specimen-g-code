# 案例研究：1101.TW —— 第一號標本

> 狀態：分析完成（2026-11-16），食譜待 Phase 2 實作。
> 來源：[ZZZPython-data-engineer](https://github.com/Galen-Chu/ZZZPython-data-engineer)
> （鷹翔有限公司 Stark Tech——Python 數據工程師評測；評測者：商研院 朱靖文）。
> 本文件把該評測的資料與流程拆解成標本語言，並列出四不變量各自對應的
> 失敗實例——這是 Specimen 專案的起源文件。

## 1. 原料盤點

| 項目 | 內容 |
|---|---|
| 標的 | 1101.TW（台泥） |
| 來源格式 | 單一 JSON 檔（FMP 風格多端點合併：`historicalPriceFull`、財報成長率、財務比率、現金流成長、技術指標） |
| 粒度 | **兩種混在一起**：日頻（價格 OHLCV、`sma/ema/rsi/adx` 等技術指標）與季頻（`*Growth`、比率類約 200 欄，帶 `calendarYear`/`period`） |
| 合併後寬度 | 約 230 欄 |
| repo 現況 | 有清洗後輸出 `output_clean_date_technical.csv`（1.4 MB）；**原始 JSON 不在 repo 內**——第一號標本的原料需從評測環境補齊，或以該 CSV 為「已製備 v0」原料（Phase 2 第一個決定） |

## 2. 評測流程拆解（現狀）

**code_01（前處理）**：巢狀 JSON 攤平 → 補 `symbol` 與來源標籤 →
DataFrame → 數值欄 `fillna(0)`／字串欄 `fillna('')` → 日期正規化
（regex 去 ` 00:00:00` 尾巴）→ `groupby(['date','symbol'])` 合併
（字串串接＋**數值加總**）→ 季度 `period` 轉日期區間 → 欄序重排 → CSV。

**code_02（預處理＋訓練）**：同源重寫的清洗（`groupby().first()`）→
季／日行交錯排列 → **全資料 `ffill().bfill()`** → 刪全 NaN 欄 →
`select_dtypes(number)` → `LinearRegression` 預測 `netIncomeGrowth` → MSE。

**題目答（PDF）**：90 天後是否成長 10% 的分類／迴歸選型、相關分析／相互
資訊／RFE 的特徵選取、欄位算術衍生新特徵——三者的制度化版本分別對應本
專案的 assay 協議、Phase 3 特徵選取協議、staining 步驟庫。

## 3. 四不變量的失敗實例（→ 設計輸入）

| # | 不變量 | 評測 code 的實例 | 標本化後的規則 |
|---|--------|----------------|---------------|
| I1 | 時間安全 | 全資料 `ffill().bfill()` 在切分**之前**；`train_test_split` 隨機切分時間序列 | 切分按時間序登記於 manifest；填充只在 train 段 fit |
| I2 | 目標純淨 | 特徵含同季財報欄（`growthNetIncome` 等）預測 `netIncomeGrowth`——答案在特徵裡 | 每欄登記可用時間（lag）；目標及其衍生欄在 assay 前自動排除 |
| I3 | 粒度分離 | 日頻行的季報欄位被 `fillna(0)` 灌成假值；`groupby` 數值**加總**合併了不同來源的價格 | `daily`／`quarterly` 分表；跨粒度一律 as-of join；合併規則宣告 |
| I4 | 逐位元重現 | 可重現性僅 `random_state=42`；兩份 code 清洗結果互相不一致（`.first()` vs 加總） | 原料 hash＋食譜＋種子 → golden 逐位元驗證 |

注意：I4 的失敗實例特別有教育意義——**同一份原料、兩支程式、兩種清洗結果**，
而沒有任何機制能說明哪個才是「對的」。標本登錄的存在就是為了讓這個問題
永遠有一個可查的答案。

## 4. 第一號食譜（Phase 2 規劃）

```
acquisition   1101.json → data/raw/（hash 入冊；或以現有 CSV 為 v0 原料）
preparation   flatten → grain 分離（daily / quarterly 兩表）→
              日期正規化 → 去重（宣告式合併規則，廢除匿名加總）
staining      技術指標欄保留；衍生欄：change/changeOverTime 比值、
              high−low 振幅、季報 as-of 對齊到日頻（lag ≥ 90 天，滿足 I2）
catalog       契約：daily (symbol,date) 鍵、quarterly (symbol,quarter) 鍵
assay         目標：90 天後報酬 ≥10%（分類，呼應評測題目）
              切分：時間序（manifest 登記）→ 基準比較表：
              logistic ／決策樹／ KNN ／ 常數基準——評估 ROC-AUC／PR-AUC
```

評測 PDF 的三題作答在此全部落地：選型（assay 的模型清單）、特徵選取
（Phase 3 協議）、衍生欄位（staining 步驟庫）——從「文字說明會怎麼做」
變成「登記在案的執行協議」。
