# -*- coding: utf-8 -*-
"""
harness_baseline_500.py
=======================
Dynamic Differential Verification Harness:
Executes 500 high-intensity, deterministic Texas Hold'em hands on SirRender00/texasholdem:
- Suite 1: Heads-up (2 players)     - 100 hands (High-frequency heads-up chip shifts)
- Suite 2: Short-handed (4 players) - 200 hands (Multi-way call & pot escalation)
- Suite 3: Full-ring (6 players)    - 200 hands (Extreme side pots & multi-way all-ins)

Strict Requirements:
- Mandatory random.seed(42) lock
- Serializes complete hand progression, chip trajectories, side pots, and board cards
- Computes SHA-256 hash and exact data point counts
- Supports --verify-diff for 0-Diff verification in 3 seconds

Usage:
    python harness_baseline_500.py [target_dir] [output_json]
    python harness_baseline_500.py --verify-diff [target_dir] [baseline_json]
"""

import sys
import os
import io
import json
import time
import random
import hashlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Standard relative repository defaults (Zero host-specific path leakages)
DEFAULT_TARGET = os.environ.get("TARGET_DIR", ".")
DEFAULT_OUTPUT = os.path.join("metrics", "baseline_500_hands.json")


def run_hand(game, agent_fn):
    """Executes a single hand to completion, capturing step-by-step state."""
    game.start_hand()
    actions_taken = []
    phases_visited = [game.hand_phase.name]

    while game.is_hand_running():
        current_phase = game.hand_phase.name
        if not phases_visited or phases_visited[-1] != current_phase:
            phases_visited.append(current_phase)

        curr_player = game.current_player
        action, total = agent_fn(game)
        actions_taken.append({
            "player": curr_player,
            "action": action.name,
            "total": total
        })
        game.take_action(action, total=total)

    final_phase = game.hand_phase.name
    if not phases_visited or phases_visited[-1] != final_phase:
        phases_visited.append(final_phase)

    # Capture pot details
    pots_data = []
    for idx, p in enumerate(game.pots):
        pots_data.append({
            "pot_id": idx,
            "amount": p.get_amount(),
            "player_amounts": {str(k): int(v) for k, v in p.player_amounts.items()},
            "players_in_pot": sorted(list(p.players_in_pot())) if callable(p.players_in_pot) else sorted(list(p.players_in_pot))
        })

    # Capture settle / winner details
    settle_str = str(game.hand_history.settle) if hasattr(game.hand_history, "settle") else ""
    pot_winners = {}
    if hasattr(game.hand_history, "settle") and hasattr(game.hand_history.settle, "pot_winners"):
        raw_pw = getattr(game.hand_history.settle, "pot_winners", {})
        for pot_id, win_tuple in raw_pw.items():
            pot_winners[str(pot_id)] = {
                "amount": win_tuple[0],
                "rank": win_tuple[1],
                "winners": list(win_tuple[2])
            }

    board_cards = [str(c) for c in game.board]
    player_chips = [p.chips for p in game.players]
    player_states = [p.state.name for p in game.players]

    return {
        "board": board_cards,
        "phases": phases_visited,
        "actions_count": len(actions_taken),
        "actions": actions_taken,
        "pots": pots_data,
        "settle": settle_str,
        "pot_winners": pot_winners,
        "chips": player_chips,
        "states": player_states
    }


def execute_suite(TexasHoldEm, agent_fn, num_players, target_hands, start_hand_id, suite_name):
    """Executes a tournament/cash table session until target_hands quota is satisfied."""
    hands = []
    hands_completed = 0
    game = TexasHoldEm(buyin=500, big_blind=5, small_blind=2, max_players=num_players)

    table_resets = 0
    while hands_completed < target_hands:
        if not game.is_game_running():
            table_resets += 1
            game = TexasHoldEm(buyin=500, big_blind=5, small_blind=2, max_players=num_players)

        hand_id = start_hand_id + hands_completed
        pre_chips = [p.chips for p in game.players]
        hand_data = run_hand(game, agent_fn)

        record = {
            "hand_id": hand_id,
            "suite": suite_name,
            "num_players": num_players,
            "table_resets": table_resets,
            "pre_chips": pre_chips,
            **hand_data
        }
        hands.append(record)
        hands_completed += 1

        if hands_completed % 50 == 0 or hands_completed == target_hands:
            print(f"    [{suite_name:<12}] Hand #{hands_completed:>3}/{target_hands} completed. Table Resets={table_resets}")

    return hands


def count_data_points(data):
    """Recursively counts primitive data values in payload."""
    count = 0
    if isinstance(data, dict):
        for k, v in data.items():
            count += 1
            count += count_data_points(v)
    elif isinstance(data, list):
        for item in data:
            count += 1
            count += count_data_points(item)
    else:
        count += 1
    return count


def load_engine(target_dir: str):
    """
    Dynamically configures search paths and loads TexasHoldEm engine.
    Eliminates static unresolved import warnings in IDEs while supporting arbitrary target directories.
    """
    abs_target = os.path.abspath(target_dir)
    if abs_target not in sys.path:
        sys.path.insert(0, abs_target)

    import importlib
    try:
        game_module = importlib.import_module("texasholdem.game.game")
        agents_module = importlib.import_module("texasholdem.agents.basic")
        return game_module.TexasHoldEm, agents_module.random_agent
    except ImportError as e:
        raise ImportError(
            f"Cannot locate 'texasholdem' package in target directory: {target_dir}. "
            f"Ensure the path contains 'texasholdem/'. Details: {e}"
        )


def verify_diff_detailed(target_dir: str, baseline_json: str) -> dict:
    """
    Verifies that target_dir produces 100% 0-Diff results against baseline_json.
    Strict Fail-Closed Preconditions:
    - Baseline file must exist and be valid JSON.
    - Baseline hands list must be present and contain EXACTLY 500 hands.
    - Current simulation must produce EXACTLY 500 hands.
    - Total data points must be >= 50,000 and match baseline data points exactly.
    - Bitwise per-hand deep equality assertion with sequential hand_id check.
    """
    print("=" * 70)
    print("[*] 0-DIFF DYNAMIC VERIFICATION HARNESS")
    print(f"[*] Target Codebase  : {target_dir}")
    print(f"[*] Baseline Dataset : {baseline_json}")
    print("=" * 70)

    if not os.path.exists(baseline_json):
        err = f"Baseline dataset not found at {baseline_json}"
        print(f"[ERROR] {err}")
        return {"success": False, "exit_code": 1, "msg": err, "data_points": 0}

    try:
        with open(baseline_json, "r", encoding="utf-8") as f:
            baseline_data = json.load(f)
    except Exception as e:
        err = f"Failed to parse baseline JSON: {e}"
        print(f"[ERROR] {err}")
        return {"success": False, "exit_code": 1, "msg": err, "data_points": 0}

    if not isinstance(baseline_data, dict):
        err = "Baseline dataset root must be a JSON object"
        print(f"[ERROR] {err}")
        return {"success": False, "exit_code": 1, "msg": err, "data_points": 0}

    baseline_hands = baseline_data.get("hands", [])
    if not isinstance(baseline_hands, list):
        err = "Baseline dataset 'hands' must be a list"
        print(f"[ERROR] {err}")
        return {"success": False, "exit_code": 1, "msg": err, "data_points": 0}

    # Strict invariant 1: Exactly 500 hands requirement (rejects empty or partial datasets)
    if len(baseline_hands) != 500:
        err = f"Baseline dataset must contain exactly 500 hands! Found {len(baseline_hands)} hands."
        print(f"[ERROR] {err}")
        return {"success": False, "exit_code": 1, "msg": err, "data_points": 0}

    print(f"[*] Loaded baseline with {len(baseline_hands)} hands.")
    print("[*] Locking entropy generator: random.seed(42)...")
    random.seed(42)

    # Dynamic import of target codebase without static IDE errors
    TexasHoldEm, random_agent = load_engine(target_dir)

    t0 = time.time()
    current_hands = []

    print("[+] Running Suite 1/3: Heads-up (2 Players) - 100 hands...")
    current_hands.extend(execute_suite(TexasHoldEm, random_agent, 2, 100, 1, "heads_up"))

    print("[+] Running Suite 2/3: Short-handed (4 Players) - 200 hands...")
    current_hands.extend(execute_suite(TexasHoldEm, random_agent, 4, 200, 101, "short_handed"))

    print("[+] Running Suite 3/3: Full-ring (6 Players) - 200 hands...")
    current_hands.extend(execute_suite(TexasHoldEm, random_agent, 6, 200, 301, "full_ring"))

    duration = time.time() - t0

    # Strict invariant 2: Current execution must also produce exactly 500 hands
    if len(current_hands) != 500:
        err = f"Current simulation must produce exactly 500 hands! Got {len(current_hands)} hands."
        print(f"[ERROR] {err}")
        return {"success": False, "exit_code": 1, "msg": err, "data_points": 0}

    current_hands = json.loads(json.dumps(current_hands))
    total_data_points = count_data_points({"hands": current_hands})
    baseline_data_points = count_data_points({"hands": baseline_hands})

    # Strict invariant 3: Data points count integrity
    if total_data_points < 50000:
        err = f"Total state points too low ({total_data_points} < 50,000), aborting."
        print(f"[ERROR] {err}")
        return {"success": False, "exit_code": 1, "msg": err, "data_points": total_data_points}

    if total_data_points != baseline_data_points:
        err = f"Data point count mismatch: current={total_data_points}, baseline={baseline_data_points}"
        print(f"[ERROR] {err}")
        return {"success": False, "exit_code": 1, "msg": err, "data_points": total_data_points}

    print(f"\n[*] Comparing {len(current_hands)} hands against baseline ({total_data_points:,} data points)...")

    # Strict invariant 4: Deep per-hand bitwise equality
    mismatches = []
    for idx in range(500):
        b_hand = baseline_hands[idx]
        c_hand = current_hands[idx]
        if b_hand.get("hand_id") != idx + 1 or c_hand.get("hand_id") != idx + 1:
            mismatches.append((idx + 1, "hand_id sequence mismatch"))
        elif b_hand != c_hand:
            mismatches.append((idx + 1, "state divergence"))
        if len(mismatches) >= 5:
            break

    if mismatches:
        print("\n" + "!" * 70)
        print(f"[FAIL] 0-DIFF VERIFICATION FAILED! {len(mismatches)} hand discrepancies detected:")
        for m in mismatches:
            print(f"   [-] Hand #{m[0]}: {m[1]}")
        print("!" * 70)
        return {"success": False, "exit_code": 1, "msg": f"{len(mismatches)} hand discrepancies detected", "data_points": total_data_points}

    print("\n" + "=" * 70)
    print("[PASS] 0-DIFF DYNAMIC VERIFICATION: 100% MATCH! (Diff == 0.0)")
    print("=" * 70)
    print(f"  * Verification Duration : {duration:.3f} s")
    print(f"  * Total Hands Replayed  : {len(current_hands)} / 500 hands (0 drift)")
    print(f"  * Verified Data Points  : {total_data_points:,} points (100% exact match)")
    print(f"  * Difference Metric     : 0.000% (Zero Drift)")
    print("=" * 70)

    return {
        "success": True,
        "exit_code": 0,
        "msg": "0-Diff verified",
        "data_points": total_data_points,
        "total_hands": 500,
        "duration": duration
    }


def verify_diff(target_dir: str, baseline_json: str) -> int:
    """CLI backward-compatible wrapper returning integer exit code."""
    res = verify_diff_detailed(target_dir, baseline_json)
    return res.get("exit_code", 1)


def main():
    if "--verify-diff" in sys.argv or (len(sys.argv) == 1 and os.path.exists(DEFAULT_OUTPUT)):
        args = [a for a in sys.argv[1:] if a != "--verify-diff"]
        target = args[0] if len(args) > 0 else DEFAULT_TARGET
        baseline = args[1] if len(args) > 1 else DEFAULT_OUTPUT
        sys.exit(verify_diff(target, baseline))

    target_dir = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET)
    output_json = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUTPUT)

    print("=" * 70)
    print("🚀 500-HAND DIFFERENTIAL VERIFICATION HARNESS")
    print(f"[*] Target Codebase : {target_dir}")
    print(f"[*] Output JSON Path: {output_json}")
    print("=" * 70)

    # 1. Force strict deterministic random seed
    print("[*] Locking entropy generator: random.seed(42)...")
    random.seed(42)

    # 2. Dynamic import of target codebase without static IDE errors
    TexasHoldEm, random_agent = load_engine(target_dir)

    t0 = time.time()
    all_hands = []

    # Suite 1: Heads-up (100 hands)
    print("\n[+] Starting Suite 1/3: Heads-up (2 Players) - 100 hands...")
    s1_hands = execute_suite(TexasHoldEm, random_agent, 2, 100, 1, "heads_up")
    all_hands.extend(s1_hands)

    # Suite 2: Short-handed (200 hands)
    print("\n[+] Starting Suite 2/3: Short-handed (4 Players) - 200 hands...")
    s2_hands = execute_suite(TexasHoldEm, random_agent, 4, 200, 101, "short_handed")
    all_hands.extend(s2_hands)

    # Suite 3: Full-ring (200 hands)
    print("\n[+] Starting Suite 3/3: Full-ring (6 Players) - 200 hands...")
    s3_hands = execute_suite(TexasHoldEm, random_agent, 6, 200, 301, "full_ring")
    all_hands.extend(s3_hands)

    duration = time.time() - t0
    assert len(all_hands) == 500, f"Expected 500 hands, got {len(all_hands)}"

    # 3. Assemble complete metadata payload with relative path & upstream repo
    payload = {
        "metadata": {
            "generator": "harness_baseline_500.py",
            "seed": 42,
            "target_dir": "texasholdem",
            "upstream_repo": "https://github.com/SirRender00/texasholdem",
            "total_hands": 500,
            "suite_breakdown": {
                "heads_up": 100,
                "short_handed": 200,
                "full_ring": 200
            },
            "duration_seconds": round(duration, 3),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        },
        "hands": all_hands
    }

    # Count physical verified data points
    print("\n[*] Calculating verification data points across 500 hands...")
    total_data_points = count_data_points(payload)

    # 4. Serialize to JSON
    json_bytes = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    file_size_bytes = len(json_bytes)
    sha256_hash = hashlib.sha256(json_bytes).hexdigest()

    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    with open(output_json, "wb") as f:
        f.write(json_bytes)

    # Write summary receipt alongside the output
    receipt_path = os.path.join(os.path.dirname(output_json), "baseline_500_receipt.json")
    receipt = {
        "duration_seconds": round(duration, 3),
        "total_hands": 500,
        "total_data_points": total_data_points,
        "file_size_bytes": file_size_bytes,
        "sha256": sha256_hash,
        "target_dir": "texasholdem",
        "upstream_repo": "https://github.com/SirRender00/texasholdem"
    }
    with open(receipt_path, "w", encoding="utf-8") as rf:
        json.dump(receipt, rf, indent=2)

    print("\n" + "=" * 70)
    print("✅ 500-HAND BASELINE CAPTURE SUCCESSFULLY COMPLETED!")
    print("=" * 70)
    print(f"  • 執行總耗時 (Duration)      : {duration:.3f} 秒")
    print(f"  • 總手牌數 (Total Hands)     : {len(all_hands)} 局 (100 HU + 200 4-Max + 200 6-Max)")
    print(f"  • 總驗證數據點 (Data Points) : {total_data_points:,} 點")
    print(f"  • JSON 檔案大小 (File Size)  : {file_size_bytes:,} 位元組 ({file_size_bytes / 1024:.2f} KB)")
    print(f"  • SHA-256 數位指紋 (Hash)   : {sha256_hash}")
    print("=" * 70)


if __name__ == "__main__":
    main()
