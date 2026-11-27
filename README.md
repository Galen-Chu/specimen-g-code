# 🔬 Specimen G-Code

> **"Data you can testify about."** · 「經得起檢驗的資料，才叫標本。」

---

## 🧭 這是什麼？ · What It Is

Specimen 是一條**決定論的資料製備與檢驗管線**：把原始資料變成
**標本（specimen）**——一個登記在冊、防洩漏、逐位元可重現的資料束，並在其上
執行可比較的模型訓練協議。

G-Code 生態系的分工三部曲：**Unbodysoma 給身體與心智，Sanctuary 給世界，
Specimen 給標本與檢驗。** 沒有製備的資料只是原料；經得起交叉詰問的資料才是
證據。

Specimen is a deterministic preparation-and-assay pipeline: raw data in, a
**specimen** out — a registered, leakage-safe, bit-reproducible data bundle —
plus a comparable model-training protocol run on it.

## 🧬 隱喻 · The Metaphor

整條管線就是製作標本的實驗室流程，一比一映射：

| 標本實驗室 | 管線階段 | 內容 |
|-----------|---------|------|
| 採集 **acquisition** | 原料擷取 | 多來源資料入库（API dump、CSV、`signals.csv`），hash 入冊 |
| 製備 **preparation** | 前處理／清洗 | 格式統一、去重、補值策略——標本的固定（fixation） |
| 切片染色 **staining** | 預處理／特徵工程 | 欄位算術、轉換、衍生特徵——登記在食譜裡的宣告式步驟 |
| 登錄 **catalog** | 封存與契約 | manifest（原料 hash＋食譜＋輸出 hash）、schema 契約、版本——標本自此不可變 |
| 檢驗 **assay** | 訓練與選模 | 洩漏安全的切分、模型比較協議、評估紀錄——結果回寫登錄冊 |

```
inputs ──hash──► acquisition ──► preparation ──► staining ──► catalog(封存)
 (raw)                                │                          │
                                      │   四不變量全程把關 ◄──────┤
                                      ▼                          ▼
                                  assay(訓練/選模/評估) ──results──► catalog
```

## 🛡️ 四不變量 · The Four Invariants

本專案的存在理由。每一條都是測試類別，assay 執行前逐一檢查，未過即拒跑：

| # | 不變量 | 內容 |
|---|--------|------|
| I1 | **時間安全** time safety | 切分一律按時間序；任何填充／標準化只在 train 段 fit，絕不看未來 |
| I2 | **目標純淨** target purity | 特徵不得含與目標同期且取得時間因果上不可得的欄位；目標的衍生欄一律排除 |
| I3 | **粒度分離** grain separation | 日頻與季頻等不同粒度分表存放；合併一律 as-of join（取不晚於當時點的最近值） |
| I4 | **逐位元重現** bit-reproducibility | （原料 hash＋食譜＋種子＋食譜原始碼 hash）→ 相同輸出，golden 測試釘死；程式碼漂移會被 verify 具名拒絕 |

四不變量來自真實案例的方法學缺口分析：[docs/CASE-STUDY-1101TW.md](docs/CASE-STUDY-1101TW.md)。

## 🔒 設計原則 · Design Principles

| 原則 | 意義 |
|------|------|
| **Deterministic by default** | 種子決定一切；manifest 是重現的唯一依據（[DESIGN.md](docs/DESIGN.md) §2） |
| **Specimens are immutable** | 登錄後不可修改；要改就製作 v2，並留下 diff 報告 |
| **Contracts at every boundary** | 每張表有 schema 契約；每個階段有輸入輸出契約——schema 是本專案的登錄章節，不是全部 |
| **Leakage is a first-class enemy** | 四不變量是執行期的閘門，不是文件裡的建議 |
| **Zero-dependency core, optional blades** | manifest／契約／登錄／assay 協議零相依；食譜按需選用 `[etl]`、`[ml]` |

五階段的作業流程章程——進出條件（DoD）、閘門對照、領域擴充點、新領域驗收清單——
見 **[docs/SOP.md](docs/SOP.md)**；階段進度見下方 [Roadmap](#-roadmap)。

## 🚀 Quick Start · 快速開始

```bash
git clone https://github.com/Galen-Chu/specimen-g-code.git
cd specimen-g-code && pip install -e ".[dev]"   # 核心零相依；dev = pytest/mypy/ruff

PYTHONPATH=src python -m specimen prepare demo_vitals --seed 7 --raw tests/fixtures --out specimens/demo-vitals-s7
PYTHONPATH=src python -m specimen verify  specimens/demo-vitals-s7 --raw tests/fixtures   # I4 逐位元驗證
PYTHONPATH=src python -m specimen catalog specimens
python -m pytest                                    # 97 tests, 含兩個 golden 標本逐位元比對（assay/selection 測試需 [ml]，未裝則略過）
```

（Windows PowerShell：`$env:PYTHONPATH="src"`。`specimen prepare` 封存的標本是自描述的——manifest＋契約即可解讀，不需要本專案的程式碼。）

## 📦 Module Map · 模組地圖

| Module | Focus | 狀態 |
|--------|-------|------|
| `specimen/manifest.py` | 標本登錄：inputs／recipe（含原始碼 hash）／outputs／contracts／splits；決定論 TOML 序列化＋結構驗證 | ✅ |
| `specimen/contract.py` | 表契約：型別、範圍、鍵唯一性（schema 章節） | ✅ |
| `specimen/catalog.py` | prepare（封存）／verify（完整性＋契約＋I4 重現）／catalog（清單） | ✅ |
| `specimen/recipes/` | 食譜註冊表（`REGISTRY`）＋`demo_vitals`（髒資料→雙粒度表的機械證明）＋`sanctuary_worlds`（第二領域：世界群→無時間軸標本）＋`unbodysoma_signals`（第三領域：行為時間序列→訓練語料標本）——領域食譜包的登記處 | ✅ |
| `specimen/__main__.py` | CLI：prepare／verify／catalog／assay | ✅ |
| `specimen/staining.py` | 染色步驟庫（Phase 3）：`asof_join`（I3 營運面——季→日 as-of，lag ≥ 90、丟棄不填充）＋欄位算術（`diff`／`ratio`／`pct_change`）；註冊制具名步驟，`step_call` 正準紀錄入 manifest | ✅ |
| `specimen/selectors.py` | 特徵選取協議（Phase 3，`SELECTORS` 登記制）：correlation-filter／MI top-k／RFE top-k——一律 fit-on-train（I1） | ✅ |
| `specimen/invariants.py` | 執行期閘門：`read_split`（切分讀取器——切分屬標本，實驗不得自切）、`check_time_safety`（I1）、`check_target_purity`（I2／availability 必須宣告）、`check_grain_separation`（I3 結構面） | ✅ |
| `specimen/assay.py` | 檢驗協議（`PROTOCOLS` 登記制）：入口閘門 I2→I3→完整性→〔協議內〕契約→數值／二元→I1；`time-split-baseline`＝constant／logistic／decision_tree／knn＋ROC-AUC／PR-AUC；`[[assays]]` 只加不寫；[ml] 刀片，核心零相依 | ✅ |
| `specimen/recipes/stock_1101` | 第一號真實標本（1101.TW）雙粒度：daily（TWSE 日頻＋90 天前瞻目標）＋quarterly（官方快照血緣＋yfinance 歷史回補，單位諧調以重疊季交叉驗證釘死）；宣告式清潔規則、availability 全宣告、golden 釘死、assay 過門 | ✅ |
| `scripts/acquire_1101.py` | 原料擷取：TWSE 日頻逐月重爬＋MOPS 官方季報快照（向前累積）＋yfinance 歷史季回補——原樣入 `data/raw/`，僅此階段碰網路 | ✅ |

## 🔄 Related Projects · 關聯專案

| Repository | Relationship · 關係 |
|-----------|-------------------|
| [Unbodysoma](https://github.com/Galen-Chu/Unbodysoma) | 標本來源之一：每次 run 的 `signals.csv`／`events.jsonl` 即內生標本（其 Phase 3 學習心智的輸入） |
| [sanctuary-g-code](https://github.com/Galen-Chu/sanctuary-g-code) | 標本來源之一：跨種子世界群的統計驗收資料 |
| [ZZZPython-data-engineer](https://github.com/Galen-Chu/ZZZPython-data-engineer) | 起源案例：資料前處理＋模型訓練評測，其方法學缺口即本專案的價值主張（[案例研究](docs/CASE-STUDY-1101TW.md)） |
| [Health-Inbody-System](https://github.com/Galen-Chu/Health-Inbody-System) | 未來消費者：M6 預測分析的訓練協議 |

## 🗺️ Roadmap

- [x] **Phase 0（2026-11-16）**：設計定案（DESIGN.md）、案例研究、manifest 草案、套件骨架
- [x] **Phase 1（2026-11-16）**：manifest＋contract＋catalog 核心與 golden 重現（零相依；CSV 表）；demo_vitals 食譜證明全鏈；CLI＋CI
- [x] **Phase 2（2026-11-16～18）**：manifest 釘住食譜原始碼 hash（v0.2.0——verify 具名識破程式碼漂移）；四不變量閘門與切分讀取器（`invariants.py`）；assay 協議（`PROTOCOLS` 登記制、標準化基準比較表、`[[assays]]` 只加不寫）；通用作業流程定案（SOP.md）；第一號真實標本 `stock_1101` 雙粒度落地——daily（TWSE 開放資料重爬、宣告式清潔規則、90 天前瞻目標）＋quarterly（官方 MOPS 快照作血緣與向前累積；歷史季 2025Q3–2026Q3 以 yfinance 宣告式回補，重疊季交叉驗證精確命中）
- [x] **Phase 3（2026-11-27 完成，v0.3.0）**：**staining 步驟庫**（`staining.py`：`asof_join`／`diff`／`ratio`／`pct_change` 註冊制具名步驟＋`step_call` 正準紀錄；as-of join 是 I3 營運面的兌現——季→日 lag ≥ 90 天、未達可得日丟棄不填充）＋**特徵選取協議登記化**（`selectors.py`：correlation-filter／MI top-k／RFE top-k，一律 fit-on-train＝I1；`[[assays]]` 紀錄帶 selector／params／features）；`stock_1101` 落地第三張表 **daily_enriched**（季報 as-of 進日頻＋兩個宣告比率，契約全宣告 availability）
- [x] **Phase 4a（2026-11-27 完成，v0.4.0）**：**生態適配器——sanctuary 世界群**（第二領域 `sanctuary_worlds`：`population.toml`＋N 份世界 TOML → `worlds` 表，grain `world`；**第一個無時間軸標本**——integer-ordered 切分（[ADR-0001](docs/adr/ADR-0001-atemporal-specimens.md)：整數鍵切分法＋split_column 分派；I1/I3 依 SOP 退化為種子序）、count/seed 交叉檢查、golden 釘死。assay 對世界群暫緩（無學習問題不強造 target，ADR-0001 consequences）
- [x] **Phase 4b（2026-11-27 完成，v0.5.0）**：**生態適配器——Unbodysoma 行為標本**（第三領域 `unbodysoma_signals`：fear run 的 `signals.csv`（95 通道時間序列）＋`meta.json` → `signals` 表，grain `signal`，300 列整數秒軸；drop_incomplete 丟棄 t=0 空欄列；run_identity 帶 scenario＋generator 版本；contract 通道名含點→manifest TOML 鍵加引號渲染）。assay 暫緩（訓練語料屬 Unbodysoma Phase 3 學習心智，本標本即其語料）
- [ ] **Phase 5**：漂移偵測與標本升級（v1→v2 diff；schema 章節是否獨立為模組的評估點）
- [ ] **Phase 4**：生態適配器——Unbodysoma `signals.csv`、sanctuary 世界群（SOP 通用化的第一次實戰考驗）
- [ ] **Phase 5**：漂移偵測與標本升級（v1→v2 diff；schema 章節是否獨立為模組的評估點）

跨階段的具體工作項與工程債見 **[docs/BACKLOG.md](docs/BACKLOG.md)**（2026-11-18 第二次盤點歸檔）。

## 🌐 Global Constraints

繼承自 G-Code 生態系：

- **Bilingual Imperative**：輸出雙語（English + 繁體中文）
- **CLI-First**：headless、終端可跑、cron 相容
- **Rational Grounding**：技術語言，不神祕主義——每個不變量有失敗案例支撐
- **Reproducibility Required**：任何輸出都能由（原料 hash＋食譜＋種子）重建

## 📄 License

MIT — see [LICENSE](LICENSE)。
