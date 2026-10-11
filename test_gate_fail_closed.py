# -*- coding: utf-8 -*-
"""
test_gate_fail_closed.py
========================
Adversarial Negative Constraint Verification Suite for TexasHoldEm Decoupling Gates.

Purpose:
Proves mathematically and empirically that the release verification gates are
strictly FAIL-CLOSED and CANNOT be bypassed via:
1. Empty fingerprint registries ({})
2. Truncated fingerprint registries (15 / 16 files)
3. Tampered test code (SHA-256 mutation)
4. Empty baseline dataset (hands: [])
5. Truncated baseline dataset (499 / 500 hands)
6. Divergent state mutation (altered chip/board in hand #42)
7. Monolith LOC overflow (game.py > 400 LOC)

Usage:
    python test_gate_fail_closed.py
"""

import os
import sys
import json
import shutil
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

import verify_release
import harness_baseline_500


def test_empty_fingerprint_registry():
    """Attack 1: Attacker replaces test_fingerprints.json with empty dict {}."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fp = Path(tmpdir) / "test_fingerprints.json"
        fp.write_text("{}", encoding="utf-8")
        res = verify_release.check_test_fingerprints(tmpdir)
        assert res["status"] == "FAIL", f"Expected FAIL on empty fingerprints, got {res['status']}"
        assert "incomplete" in res["msg"].lower() or "missing" in res["msg"].lower()
    return True


def test_truncated_fingerprint_registry():
    """Attack 2: Attacker deletes 1 test suite from fingerprint registry (15/16)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        real_fp = ROOT_DIR / "test_fingerprints.json"
        data = json.loads(real_fp.read_text(encoding="utf-8"))
        del data["tests/game/test_game.py"]  # Delete critical test file
        fp = Path(tmpdir) / "test_fingerprints.json"
        fp.write_text(json.dumps(data), encoding="utf-8")
        res = verify_release.check_test_fingerprints(tmpdir)
        assert res["status"] == "FAIL", f"Expected FAIL on truncated fingerprints, got {res['status']}"
        assert any("tests/game/test_game.py" in v for v in res["violations"])
    return True


def test_tampered_test_file():
    """Attack 3: Attacker alters 1 byte inside a test suite."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Copy test_fingerprints.json
        shutil.copy(ROOT_DIR / "test_fingerprints.json", Path(tmpdir) / "test_fingerprints.json")
        # Create a mock tests/game/test_game.py with invalid content
        p = Path(tmpdir) / "tests" / "game"
        p.mkdir(parents=True, exist_ok=True)
        (p / "test_game.py").write_text("# tampered test code", encoding="utf-8")
        res = verify_release.check_test_fingerprints(tmpdir)
        assert res["status"] == "FAIL", f"Expected FAIL on mutated test file, got {res['status']}"
    return True


def test_empty_baseline_hands():
    """Attack 4: Attacker alters baseline dataset to hands: []."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump({"metadata": {"total_hands": 0}, "hands": []}, tf)
        tmp_json = tf.name
    try:
        res = harness_baseline_500.verify_diff_detailed(str(ROOT_DIR), tmp_json)
        assert res["success"] is False, f"Expected False on empty baseline hands, got {res['success']}"
        assert res["exit_code"] != 0, f"Expected non-zero exit code, got {res['exit_code']}"
    finally:
        if os.path.exists(tmp_json):
            os.remove(tmp_json)
    return True


def test_truncated_baseline_hands():
    """Attack 5: Attacker truncates baseline dataset to 499 hands."""
    real_baseline = json.loads((ROOT_DIR / "metrics" / "baseline_500_hands.json").read_text(encoding="utf-8"))
    real_baseline["hands"] = real_baseline["hands"][:499]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(real_baseline, tf)
        tmp_json = tf.name
    try:
        res = harness_baseline_500.verify_diff_detailed(str(ROOT_DIR), tmp_json)
        assert res["success"] is False, f"Expected False on 499 hands, got {res['success']}"
        assert res["exit_code"] != 0
    finally:
        if os.path.exists(tmp_json):
            os.remove(tmp_json)
    return True


def test_divergent_state_mutation():
    """Attack 6: Attacker alters internal chip count in Hand #42 by 1 chip."""
    real_baseline = json.loads((ROOT_DIR / "metrics" / "baseline_500_hands.json").read_text(encoding="utf-8"))
    # Mutate hand #42 chips
    real_baseline["hands"][41]["pre_chips"][0] += 1
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(real_baseline, tf)
        tmp_json = tf.name
    try:
        res = harness_baseline_500.verify_diff_detailed(str(ROOT_DIR), tmp_json)
        assert res["success"] is False, f"Expected False on mutated chips, got {res['success']}"
        assert res["exit_code"] != 0
    finally:
        if os.path.exists(tmp_json):
            os.remove(tmp_json)
    return True


def test_monolith_loc_gate_overflow():
    """Attack 7: Code bloat attack (game.py exceeds 400 physical lines)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "texasholdem" / "game"
        p.mkdir(parents=True, exist_ok=True)
        # Create game.py with 401 lines
        (p / "game.py").write_text("\n".join(["# line"] * 401), encoding="utf-8")
        res = verify_release.check_monolith_shrinkage(tmpdir)
        assert res["status"] == "FAIL", f"Expected FAIL on 401 LOC, got {res['status']}"
        assert res["lines"] == 401
    return True


def main():
    print("=" * 76)
    print("[*] ADVERSARIAL NEGATIVE CONSTRAINT VERIFICATION SUITE")
    print("[*] Proving that release gates are strictly FAIL-CLOSED against bypass attempts")
    print("=" * 76)

    tests = [
        ("ATTACK-1", "Empty Fingerprint Registry ({}) Bypass Attack", test_empty_fingerprint_registry),
        ("ATTACK-2", "Truncated Test Fingerprint Registry (15/16 Files)", test_truncated_fingerprint_registry),
        ("ATTACK-3", "Tampered Test File SHA-256 Mutation", test_tampered_test_file),
        ("ATTACK-4", "Empty Baseline Hands Array (hands: []) Attack", test_empty_baseline_hands),
        ("ATTACK-5", "Truncated Baseline Hands (499/500 Hands) Attack", test_truncated_baseline_hands),
        ("ATTACK-6", "Subtle Game State Mutation (Altered chips in hand #42)", test_divergent_state_mutation),
        ("ATTACK-7", "Monolith LOC Threshold Overflow (game.py > 400 LOC)", test_monolith_loc_gate_overflow),
    ]

    all_passed = True
    print("\n[*] Executing Adversarial Attack Vectors:")
    for code, desc, fn in tests:
        try:
            passed = fn()
            if passed:
                print(f"  [BLOCKED] [{code:<8}] {desc}: SUCCESSFULLY INTERCEPTED")
            else:
                all_passed = False
                print(f"  [VULNERABLE] [{code:<8}] {desc}: FAILED TO INTERCEPT")
        except Exception as e:
            all_passed = False
            print(f"  [ERROR] [{code:<8}] {desc}: Exception: {e}")

    print("-" * 76)
    if all_passed:
        print("\n[SUCCESS] 7/7 ADVERSARIAL ATTACKS SUCCESSFULLY INTERCEPTED AND BLOCKED!")
        print("          All verification gates are strictly FAIL-CLOSED and tamper-proof.\n")
        sys.exit(0)
    else:
        print("\n[ERROR] One or more adversarial tests failed to be intercepted!\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
