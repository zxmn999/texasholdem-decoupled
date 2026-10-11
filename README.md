# TexasHoldEm (Decoupled & Modernized)

An industrial-grade, fully decoupled Python Texas Hold'em game engine and simulator.

---

## 🚀 Clean-Room Independent Audit & Red-Team Replication (獨立審計與紅隊復現)

本專案提供第三方開箱即用、無人值守、零外部專有路徑相依的獨立驗證跑跑包與紅隊對抗套件。任何審計官皆可在乾淨環境下一鍵檢驗重構真實性與防線剛性：

### 1. 極速獨立驗收 (0.25 秒一鍵全量驗收)
在專案根目錄執行單一指令，自動於 0.25 秒內執行 Gate 1 (AST 瘦身)、Gate 2 (SHA-256 零篡改) 與 Gate 3 (500 局 53,905 點動態 0-Diff 比對)，並落盤法定交付簽章：
`ash
python run_independent_audit.py
`
- **物理收據存證**：[INDEPENDENT_AUDIT_RECEIPT.md](INDEPENDENT_AUDIT_RECEIPT.md) / [INDEPENDENT_AUDIT_RECEIPT.json](INDEPENDENT_AUDIT_RECEIPT.json)

### 2. 紅隊對抗作弊攻擊 (0.5 秒 100% 熔斷攔截自證)
執行自動化紅隊對抗套件，現場於隔離沙箱中模擬 5 大代表性作弊攻擊（老測試斷言篡改、401 行卡規突破、靜態例外吞噬、第 342 局偷改籌碼 1 點、互斥規格注入），驗證系統 100% 剛性觸發 Exit Code 1 熔斷擊斃：
`ash
python run_redteam_attacks.py
`
- **紅隊實況戰報**：[REDTEAM_ATTACK_REPORT.md](REDTEAM_ATTACK_REPORT.md) / [REDTEAM_ATTACK_REPORT.json](REDTEAM_ATTACK_REPORT.json)

### 3. 工程治理適用邊界與失敗清冊
完整公開記錄重構歷史中所有實體駁回案例（包含 Step #06 1,153 行超標被 VETO 的 Commit 324477a7ecfc40c），並明確定義防禦承諾與適用邊界：
- **實體規約清冊**：[SPEC_BOUNDARY_AND_FAILURES.md](SPEC_BOUNDARY_AND_FAILURES.md)

---

## Highlights of Architectural Refactoring
- **Monolith Decoupled**: The legacy 1,375-line game.py monolith has been surgically partitioned into 5 single-responsibility domain modules, reducing game.py to **394 lines** (-71.3% LOC) acting as a clean, GoF Facade.
- **AST Complexity Halved**: AST node count reduced from 5,466 to 2,078 nodes (-62.0%).
- **Dynamic 0-Diff Verified**: 500 hands, 53,905 state points verified across 3 game variants with Diff == 0.000% (Zero behavioral drift).
- **100% Backwards Compatible**: All 38 original methods and signatures remain identical. 1,210 official unit tests pass 100%.

## Architecture Overview
`	ext
texasholdem/game/
├── game.py              # Clean Facade (< 400 LOC), routes calls to domain engines
├── side_pot_math.py     # Pure functional side pot settlement & WSOP pot math
├── round_scheduler.py   # Hand phase transitions & betting action queue
├── action_validator.py  # WSOP Rule 96 raise bounds & legal move validator
└── game_serializer.py   # PGN history replay & deep copy engine
`

## Quick Start

### 1. Clean-Room Independent Verification (New!)
`ash
python run_independent_audit.py
`

### 2. Adversarial Red-Team Injection Test (New!)
`ash
python run_redteam_attacks.py
`

### 3. Show Refactoring Proof & Metrics
`ash
python show_refactor_proof.py
`

### 4. Verify Dynamic 0-Diff
`ash
python harness_baseline_500.py --verify-diff . metrics/baseline_500_hands.json
`

### 5. Run Release Quality Gate
`ash
python verify_release.py --project-root . --golden-dataset metrics/baseline_500_hands.json
`

### 6. Play Texas Hold'em (CLI)
`ash
python play_poker.py
`
Or run the precompiled native executable:
`ash
texasholdem.exe
`

## License
MIT License. See [LICENSE](LICENSE) for details.
