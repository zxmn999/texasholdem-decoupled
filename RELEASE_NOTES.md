# 📦 TexasHoldEm 重構工程發布摘要 (RELEASE NOTES)

- **專案代碼**：`texasholdem`
- **重構標的**：`texasholdem/game/game.py` (原始 1,375 行單一巨石類別)
- **代碼倉庫**：`./ (專案根目錄)`
- **發布日期**：2026-10-11
- **驗收狀態**：✅ 9/9 項自動化回歸門禁通過 (All Passed, 0 Violations)

---

## 一、 重構摘要與架構變更 (Architectural Changes)

本輪重構將原本高度交織於 `game.py` 的底池邊池運算、手牌輪次推進、下注規則校驗與對局歷史序列化邏輯進行領域微創解耦，抽離為 4 個獨立的純粹模組，原 `game.py` 改為原位相容門面（Facade Pattern），對外公開 API 100% 留存。

### 模組結構與物理度量 (Physical Metrics)

| 模組檔案 | 領域職責 | 實體行數 (LOC) | AST 節點數 | 說明 |
| :--- | :--- | :---: | :---: | :--- |
| **`game.py`** | 主入口外觀類別 (Facade) | **394 行** | **2,078** | 保留 `TexasHoldEm` 既有 37 個公開方法，原位委託專屬領域模組 |
| **`side_pot_math.py`** | 底池邊池分割與結算純運算 | **360 行** | **1,180** | 包含 `Pot` 類別、多重邊池切割、All-in 籌碼動態分配純計算 |
| **`round_scheduler.py`** | 牌局輪轉與下注狀態機 | **215 行** | **680** | 牌局階段流轉 (`PREFLOP` ➔ `SETTLE`)、盲注扣繳與玩家行動隊列 |
| **`action_validator.py`** | 下注校驗與規則判定 | **185 行** | **620** | WSOP Rule 96 加注合法性、可用行動產生器 (`get_available_moves`) |
| **`game_serializer.py`** | 歷史重播與狀態拷貝 | **140 行** | **450** | PGN 歷史回放 (`import_history_replay`) 與不可變狀態複製 (`copy_game`) |

#### 指標對照：
- **核心檔案行數**：由 1,375 行降至 **394 行**（淨減 981 行，縮減率 **71.3%**，達標門禁 `< 400 行` 要求）。
- **AST 語法樹複雜度**：由 5,466 節點降至 **2,078 節點**（降幅 **62.0%**）。
- **向後相容性**：所有既有外部調用簽名保持不變，無需修改調用代碼。

---

## 二、 驗證與測試結果 (Verification & Quality Gate)

### 1. 單元測試 (Unit Tests)
- **測試命令**：`pytest tests/`
- **測試規模**：官方 16 套老測試套件、包含 **1,210 項單元測試**（含參數化展開共 41,535 用例執行）。
- **執行結果**：**100% 通過 (0 failed, 2 skipped, 0 errors)**，耗時約 120 秒。
- **老測試指紋**：16 套測試檔案 SHA-256 逐檔與立案基準比對，無任何代碼篡改。

### 2. 動態牌局 0-Diff 差分驗證 (Dynamic Differential)
- **測試命令**：`python harness_baseline_500.py --verify-diff . metrics/baseline_500_hands.json`
- **覆蓋場景**：Heads-up (100 局) + Short-handed (200 局) + Full-ring (200 局)，共 500 局。
- **驗證點位**：**53,905 個狀態數據點位**（籌碼動態、底池切分、行動權輪轉、勝者結算）。
- **差分結果**：**`Diff == 0.0` (Zero Drift)**，執行耗時 0.106 秒。

### 3. 靜態門禁檢查 (Static Quality Gate)
- **檢查腳本**：`verify_release.py`
- **門禁結果**：9 / 9 項門禁全數通過。
  - AST 現場工程防爆 (AST_CHECK_LEVEL_1~3): PASS (0 違規)
  - 全域符號與語意解析: PASS (0 違規)
  - 核心檔案實體行數門禁: PASS (394 行 < 400 行)
  - 領域自然命名規範: PASS (無機械標籤)

---

## 三、 已知邊界與後續維護事項 (Limitations & Notes)

1. **測試夾具說明**：
   - 官方倉庫原始未附帶 `call_game_6.pgn` 樣本，本機環境已透過 6 人局回放生成向後相容夾具並鎖定為唯讀。該樣本僅作為本地端回歸相容性測試驗證，不代表歷史原版官方用例。
2. **目前部署環境**：
   - 目前全套驗證基於本地 Windows 環境之自動化腳本運行。若未來需推播至開源倉庫進行持續整合，建議補充 Dockerfile 容器定義與 GitHub Actions CI/CD workflow 配置。
