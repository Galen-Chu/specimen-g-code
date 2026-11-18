# 🔬 Specimen G-Code

> **"Data you can testify about."** · 「經得起檢驗的資料，才叫標本。」

> 📐 **目前狀態：Phase 1 完成（2026-11-16）**——manifest／contract／catalog 核心、
> golden 逐位元重現、CLI 與 CI 已上線；assay 協議與第一號真實標本（stock_1101）見路線圖。
> 🧪 v0.2.0（2026-11-18）：食譜原始碼 hash 入冊——`verify` 能具名識破「封存後程式碼漂移」。

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

## 🚀 Quick Start · 快速開始

```bash
git clone https://github.com/Galen-Chu/specimen-g-code.git
cd specimen-g-code && pip install -e ".[dev]"   # 核心零相依；dev = pytest/mypy/ruff

PYTHONPATH=src python -m specimen prepare demo_vitals --seed 7 --raw tests/fixtures --out specimens/demo-vitals-s7
PYTHONPATH=src python -m specimen verify  specimens/demo-vitals-s7 --raw tests/fixtures   # I4 逐位元驗證
PYTHONPATH=src python -m specimen catalog specimens
python -m pytest                                    # 36 tests, 含 golden 逐位元比對
```

（Windows PowerShell：`$env:PYTHONPATH="src"`。`specimen prepare` 封存的標本是自描述的——manifest＋契約即可解讀，不需要本專案的程式碼。）

## 📦 Module Map · 模組地圖

| Module | Focus | 狀態 |
|--------|-------|------|
| `specimen/manifest.py` | 標本登錄：inputs／recipe（含原始碼 hash）／outputs／contracts／splits；決定論 TOML 序列化＋結構驗證 | ✅ |
| `specimen/contract.py` | 表契約：型別、範圍、鍵唯一性（schema 章節） | ✅ |
| `specimen/catalog.py` | prepare（封存）／verify（完整性＋契約＋I4 重現）／catalog（清單） | ✅ |
| `specimen/recipes/` | 食譜註冊表＋`demo_vitals`（髒資料→雙粒度表的機械證明） | ✅（demo） |
| `specimen/__main__.py` | CLI：prepare／verify／catalog | ✅ |
| `specimen/assay/` | 檢驗協議：時間切分、I1/I2 執行期閘門、模型比較表 | Phase 2 |
| `specimen/recipes/stock_1101` | 第一號真實標本（1101.TW） | Phase 2 |

## 🔄 Related Projects · 關聯專案

| Repository | Relationship · 關係 |
|-----------|-------------------|
| [Unbodysoma](https://github.com/Galen-Chu/Unbodysoma) | 標本來源之一：每次 run 的 `signals.csv`／`events.jsonl` 即內生標本（其 Phase 3 學習心智的輸入） |
| [sanctuary-g-code](https://github.com/Galen-Chu/sanctuary-g-code) | 標本來源之一：跨種子世界群的統計驗收資料 |
| [ZZZPython-data-engineer](https://github.com/Galen-Chu/ZZZPython-data-engineer) | 起源案例：資料前處理＋模型訓練評測，其方法學缺口即本專案的價值主張（[案例研究](docs/CASE-STUDY-1101TW.md)） |
| [Health-Inbody-System](https://github.com/Galen-Chu/Health-Inbody-System) | 未來消費者：M6 預測分析的訓練協議 |

## 🗺️ Roadmap

- [x] **Phase 0（2026-11-16）**：設計定案（DESIGN.md）、案例研究、manifest 草案、套件骨架
- [x] **Phase 1（2026-11-16）**：manifest＋contract＋catalog 核心與 golden 重現（零相依；CSV 表）；demo_vitals 食譜證明全鏈；CLI＋CI；28 tests
- [ ] **Phase 2**：`stock_1101` 食譜完整落地——五階段、四不變量全綠；assay 協議（時間切分＋I1/I2 閘門＋基準模型比較表）
- [ ] **Phase 3**：staining 程式庫（欄位算術 DSL）＋特徵選取協議（相關分析／MI／RFE 的登記化）
- [ ] **Phase 4**：生態適配器——Unbodysoma `signals.csv`、sanctuary 世界群
- [ ] **Phase 5**：漂移偵測與標本升級（v1→v2 diff；schema 章節是否獨立為模組的評估點）

跨階段的具體工作項與工程債見 **[docs/BACKLOG.md](docs/BACKLOG.md)**（2026-11-16 盤點歸檔）。

## 🌐 Global Constraints

繼承自 G-Code 生態系：

- **Bilingual Imperative**：輸出雙語（English + 繁體中文）
- **CLI-First**：headless、終端可跑、cron 相容
- **Rational Grounding**：技術語言，不神祕主義——每個不變量有失敗案例支撐
- **Reproducibility Required**：任何輸出都能由（原料 hash＋食譜＋種子）重建

## 📄 License

MIT — see [LICENSE](LICENSE)。
