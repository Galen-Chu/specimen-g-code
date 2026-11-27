# ADR-0001：無時間軸標本的切分法 Atemporal Specimen Splits

- 狀態：Accepted（2026-11-27）；**Amended 2026-11-27（同日）**：method 更名
  `seed-ordered` → `integer-ordered`——Phase 4b 的 Unbodysoma 訊號標本以
  「模擬秒」為整數序軸（不是種子），證明此法是通用的整數鍵切分，種子只是
  第一個實例。split key 的選擇規則改為：名為 `seed` 的 int 鍵欄優先（世界群
  案例），否則第一個 int 鍵欄（訊號表＝time）。
- 決策人：Galen Chu（實作：Claude，Phase 4 批次）
- 影響：`manifest.py`（Splits）、`invariants.py`（read_split／check_time_safety）、
  `validate_manifest`

## 背景 Context

Phase 4 的生態適配器把 **sanctuary 世界群**做成標本：一群世界（每列＝一個
world），沒有任何時間軸——世界的身分是種子，不是日期。SOP §1 預言了這條路：
「無時間軸的資料——I1／I3 退化為自動通過：閘門照跑」。實作時撞上第一個
「不改核心就撐不住」的邊界：

- `Splits.method` 只接受 `"time-ordered"`（`validate_manifest` 硬編碼）。
- `read_split` 必須有 `date` 型別的鍵欄才能切——世界群沒有。
- 世界群沒有學習問題（assay 的 target 尚不存在），但**切分屬標本**的契約
  不該因此缺席：切分身分是 manifest 完備性的一部分，實驗到來前就該定案。

## 決策 Decision

1. **`Splits.method` 增加第二個合法值：`"seed-ordered"`**。語意與
   `time-ordered` 同構——把「時間序」換成「種子序」：
   - `train_end`／`valid_end` 是**種子數字的字串形式**（沿用字串欄位，
     校驗改為可解析為整數且嚴格遞增）。
   - `read_split` 對 `seed-ordered` 讀宣告表中名為 `seed` 的 `int` 鍵欄
     （無則退回第一個 `int` 鍵欄）做同構的區間判定：train：
     `seed <= train_end`、valid：`(train_end, valid_end]`、test：其餘。
   - `check_time_safety` 依 method 分派，對 `seed-ordered` 做同構檢查。
2. **不改四不變量的定義**。I1 的本質是「切分按某個聲明的序進行，且閘門
   驗證每個標籤落在聲明的區間」——種子序是時間序的退化實例。對無時間軸
   資料，任何確定論切分都無洩漏可言（沒有「未來」可洩漏），但閘門照跑、
   切分身分照登記——SOP 承諾「閘門照跑，不打折」兌現為「同一套閘門，
   另一種序」。
3. **未來 method 加入仍需新 ADR**。本 ADR 只開 `seed-ordered` 一扇門。

## 後果 Consequences

- 正面：sanctuary 世界群（與任何以種子為身的無時間軸標本）可以完整走
  五階段；切分身分在實驗到來前已釘死，屆時所有 assay 可比較。
- 負面：`read_split`／`check_time_safety`／`validate_manifest` 出現 method
  分支——複雜度小而必要；測試釘死兩種 method 的行為。
- 中性：assay 對世界群**暫緩**——世界沒有學習問題（target 尚不存在），
  強造一個 target（如「危險覆蓋率是否高於中位數」）是為了過門而捏造問題，
  違反 Rational Grounding。assay 待學習問題出現（Phase 5 的指紋預測等）
  再跑；屆時切分身分已在 manifest 裡等著。
