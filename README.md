# TexasHoldEm (Decoupled & Modernized)

An industrial-grade, fully decoupled Python Texas Hold\'em game engine and simulator.

---

## 🚀 Clean-Room Independent Audit & Red-Team Replication (獨立審計與紅隊復現)

本專案提供第三方開箱即用、無人值守、零外部專有路徑相依的獨立驗證跑跑包與紅隊對抗套件。任何審計官皆可在乾淨環境下一鍵檢驗重構真實性與防線剛性：

### 1. 極速獨立驗收 (0.25 秒一鍵全量驗收)
在專案根目錄執行單一指令，自動於 0.25 秒內執行 Gate 1 (AST 瘦身)、Gate 2 (SHA-256 法定白名單零篡改，防掏空) 與 Gate 3 (500 局 53,905 點動態 0-Diff 即時比對)，並落盤物理收據：
\\ash
python run_independent_audit.py
\- **可選：實時動態跑測**：可加上 \--run-tests\ 參數，現場實時執行 1,215 項 Pytest 單元測試並動態記錄實測指標：
\\ash
python run_independent_audit.py --run-tests
\- **物理收據存證**：[INDEPENDENT_AUDIT_RECEIPT.md](INDEPENDENT_AUDIT_RECEIPT.md) / [INDEPENDENT_AUDIT_RECEIPT.json](INDEPENDENT_AUDIT_RECEIPT.json)

### 2. 紅隊對抗作弊攻擊 (真實 OS 子進程 100% 熔斷攔截自證)
執行自動化紅隊對抗套件，現場於隔離沙箱中以真實作業系統子進程 (\subprocess.run\) 模擬 5 大代表性作弊攻擊，驗證系統 100% 剛性觸發真實 OS Exit Code 1 熔斷擊斃：
\\ash
python run_redteam_attacks.py
\| 編號 | 攻擊類型與手法 | 注入目標與負載 | 觸發防禦門禁 | 真實 OS Exit Code | 熔斷判定 |
| :---: | :--- | :--- | :--- | :---: | :---: |
| **ATK-01** | 老測試斷言篡改攻擊 | tests/game/test_game.py 注入非法斷言 | Gate 2 (SHA-256 Lock) | **1** | 🛡️ **BLOCKED** |
| **ATK-02** | 單檔 400 行卡規突破攻擊 | texasholdem/game/game.py 注入假代碼至 404 行 | Gate 1 (AST Monolith) | **1** | 🛡️ **BLOCKED** |
| **ATK-03** | 靜態例外吞噬作弊攻擊 | texasholdem/game/game.py 注入 try...except: pass | Gate 1 (AST Safe-Rails) | **1** | 🛡️ **BLOCKED** |
| **ATK-04** | 第 342 局微量籌碼漂移攻擊 | baseline_500_hands.json 竄改 Hand #342 籌碼 +1 | Gate 3 (0-Diff Replay) | **1** | 🛡️ **BLOCKED** |
| **ATK-05** | 指紋清單掏空繞過攻擊 | test_fingerprints.json 清空為 {} 試圖繞過 | Gate 2 (Canonical Whitelist) | **1** | 🛡️ **BLOCKED** |
- **紅隊實況戰報**：[REDTEAM_ATTACK_REPORT.md](REDTEAM_ATTACK_REPORT.md) / [REDTEAM_ATTACK_REPORT.json](REDTEAM_ATTACK_REPORT.json)

### 3. 工程治理適用邊界與失敗清冊
完整公開記錄重構歷史中所有實體駁回案例（包含 Step #06 1,153 行超標被 VETO 的 Commit a324477a7ecfc40c，以及 Gate 2 指紋清單掏空 Fail-Open 白箱修復歷程），並明確定義防禦承諾與適用邊界：
- **實體規約清冊**：[SPEC_BOUNDARY_AND_FAILURES.md](SPEC_BOUNDARY_AND_FAILURES.md)

---

## Highlights of Architectural Refactoring
- **Monolith Decoupled**: The legacy 1,375-line game.py monolith has been surgically partitioned into 5 single-responsibility domain modules, reducing game.py to **394 lines** (-71.3% LOC) acting as a clean, GoF Facade.
- **AST Complexity Halved**: AST node count reduced from 5,466 to 2,078 nodes (-62.0%).
- **Dynamic 0-Diff Verified**: 500 hands, 53,905 state points verified across 3 game variants with Diff == 0.000% (Zero behavioral drift).
- **100% Backwards Compatible**: All 38 original methods and signatures remain identical. 1,215 official unit tests pass 100%.

## Architecture Overview
\\	ext
texasholdem/game/
├── game.py              # Clean Facade (< 400 LOC), routes calls to domain engines
├── side_pot_math.py     # Pure functional side pot settlement & WSOP pot math
├── round_scheduler.py   # Hand phase transitions & betting action queue
├── action_validator.py  # WSOP Rule 96 raise bounds & legal move validator
└── game_serializer.py   # PGN history replay & deep copy engine
\
## Quick Start

### 1. Clean-Room Independent Verification (New!)
\\ash
python run_independent_audit.py
\
### 2. Adversarial Red-Team Injection Test (New!)
\\ash
python run_redteam_attacks.py
\
### 3. Show Refactoring Proof & Metrics
\\ash
python show_refactor_proof.py
\
### 4. Verify Dynamic 0-Diff
\\ash
python harness_baseline_500.py --verify-diff . metrics/baseline_500_hands.json
\
### 5. Run Release Quality Gate
\\ash
python verify_release.py --project-root . --golden-dataset metrics/baseline_500_hands.json
\
### 6. Play Texas Hold'em (CLI)
\\ash
python play_poker.py
\Or run the precompiled native executable:
\\ash
texasholdem.exe
\
## License
MIT License. See [LICENSE](LICENSE) for details.
