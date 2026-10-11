# TexasHoldEm (Decoupled & Modernized)

An industrial-grade, fully decoupled Python Texas Hold'em game engine and simulator.

## Highlights of Architectural Refactoring
- **Monolith Decoupled**: The legacy 1,375-line `game.py` monolith has been surgically partitioned into 5 single-responsibility domain modules, reducing `game.py` to **394 lines** (-71.3% LOC) acting as a clean, GoF Facade.
- **AST Complexity Halved**: AST node count reduced from 5,466 to 2,078 nodes (-62.0%).
- **Dynamic 0-Diff Verified**: 500 hands, 53,905 state points verified across 3 game variants with `Diff == 0.000%` (Zero behavioral drift).
- **100% Backwards Compatible**: All 38 original methods and signatures remain identical. 1,210 official unit tests pass 100%.

## Architecture Overview
```text
texasholdem/game/
├── game.py              # Clean Facade (< 400 LOC), routes calls to domain engines
├── side_pot_math.py     # Pure functional side pot settlement & WSOP pot math
├── round_scheduler.py   # Hand phase transitions & betting action queue
├── action_validator.py  # WSOP Rule 96 raise bounds & legal move validator
└── game_serializer.py   # PGN history replay & deep copy engine
```

## Quick Start

### 1. Show Refactoring Proof & Metrics
```bash
python show_refactor_proof.py
```

### 2. Verify Dynamic 0-Diff
```bash
python harness_baseline_500.py --verify-diff . metrics/baseline_500_hands.json
```

### 3. Run Release Quality Gate
```bash
python verify_release.py --project-root . --golden-dataset metrics/baseline_500_hands.json
```

### 4. Play Texas Hold'em (CLI)
```bash
python play_poker.py
```
Or run the precompiled native executable:
```bash
texasholdem.exe
```

## License
MIT License. See [LICENSE](LICENSE) for details.
