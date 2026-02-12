# 鑽孔優化計算公式技術文件 (V6.0 最終整合版)

本文件定義 `DrillingAnalysisEngine` 中實作的 V6.0 工業級動態切削優化邏輯。

---

## 1. 風險評估模型 (DRI V6.0)

系統透過 **Drilling Risk Index (DRI)** 自動評估加工風險：
$$DRI = R_{depth} \times R_{material} \times R_{coolant} \times R_{tool}$$

| 因子 | 公式 / 權重 | 備註 |
| :--- | :--- | :--- |
| **深度風險 ($R_{depth}$)** | $1.2 + (L/D)^{1.4}$ | $1.2$ 為淺孔風險偏移，確保基本保護。 |
| **材料風險 ($R_{mat}$)** | 鋁: 0.8, 鋼: 1.0, SUS304: 1.4, 鈦: 1.6, 陶瓷: 2.0 | 根據切削阻力修正。 |
| **冷卻風險 ($R_{cool}$)** | 內冷: 0.75, 水噴: 1.0, 油霧: 1.2, 乾式: 1.6 | 乾式切削具備最高風險係數。 |
| **刀具風險 ($R_{tool}$)** | 硬質合金: 0.9, HSS: 1.4 | - |

### 戰略判定區間
- $DRI < 6$: **DIRECT** (無啄鑽)
- $6 \sim 18$: **Q_MODE** (固定 Peck)
- $18 \sim 40$: **IJK_DYNAMIC** (動態遞減 Peck)
- $DRI \ge 40$: **DEEP_PROTECT** (極深孔保護)

---

## 2. 切削參數優化 (二階修正模型)

### 2a. 主軸轉速 S
$$S_{calc} = \frac{(V_{ref,mat} \times F_{cool}) \times 1000}{\pi \times D}$$
$$S_{final} = S_{calc} \times \frac{1}{1 + 0.035 \times (L/D)}$$
- $V_{ref,mat}$: 材質基準速度。
- $F_{cool}$: 冷卻係數 (內冷 `1.1`, 油霧 `0.8`, 乾式 `0.6`)。

### 2b. 進給速度 F
$$F_{final} = S_{final} \times (F_{ref,mat} \times D) \times \frac{1}{1 + 0.02 \times (L/D)} \times F_{micro}$$
- $F_{micro}$: 直徑 < 1.0mm 時之微鑽處罰 (`0.8`)。

---

## 3. 動態啄鑽模式 (冪次模型 & 單調化)

針對深孔加工，系統生成動態遞減之進刀序列：
$$P(z) = K + (I - K) \times \left(1 - \left(\frac{z}{L}\right)^{0.6}\right)$$
$$P_n = \min(P(z), P_{n-1})$$
- **穩定性保護**: 計算 I, J, K 基礎值時採用 $R_{eff} = \min(L/D, 10)$。
- **單調性守衛**: 確保啄鑽量絕對單調遞減，不反增。

---

## 4. 刀具壽命評估 (Taylor 模型，語味化)

$$LifeIndex = \left(\frac{V_{ref}}{V_{c,final}}\right)^{1/n} \times \frac{1}{1 + 0.08(L/D)^{1.3}} \times \left(\frac{1}{f_{ratio}}\right)^{0.4}$$
- 基準對齊：LifeIndex 基於材質 $V_{ref}$ 計算。
- $n$ 值：Carbide (0.22), HSS (0.10)。

---

## 5. 幾何補償

依據刀尖夾角 (Included Angle) 自動補償：
$$\Delta Z = \frac{ExitChamfer / 2}{\tan(TipAngle / 2)} + 0.2mm$$
