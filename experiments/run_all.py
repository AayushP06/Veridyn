"""Unified Master Runner for All VeriDyn Empirical Experiments.

TOC Concept: Experimental Validation Suite for Formal Language Induction and Adversarial Hardness.
"""

from __future__ import annotations

from pathlib import Path
import time

from experiments import (
    exp_api_leak_check,
    exp_certification,
    exp_coin_flip,
    exp_correctness,
    exp_learner_bots,
    exp_performance,
    exp_replay,
)

RESULTS_DIR = Path(__file__).resolve().parent / "results"

EXPERIMENTS = [
    ("1. Differential Correctness", exp_correctness.run_experiment, "correctness.csv"),
    ("2. Automata Performance & Blow-Up", exp_performance.run_experiment, "performance.csv"),
    ("3. H-Guesser Certification Proof", exp_certification.run_experiment, "certification.csv"),
    ("4. Coin-Flip Baseline Bounds", exp_coin_flip.run_experiment, "coin_flip.csv"),
    ("5. Learner Bots Boundary Analysis", exp_learner_bots.run_experiment, "learner_bots.csv"),
    ("6. Replay & Protocol Abuse Guard", exp_replay.run_experiment, "replay.csv"),
    ("7. Zero-Knowledge API Leak Audit", exp_api_leak_check.run_experiment, "api_leak_check.csv"),
]


def run_all() -> None:
    """Execute all 7 empirical experiments in sequence and verify CSV exports."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    t_start = time.perf_counter()

    print("\n" + "=" * 90)
    print("                 VERIDYN EMPIRICAL EVALUATION SUITE")
    print("=" * 90)
    print(f"Executing {len(EXPERIMENTS)} benchmark and security experiments...\n")

    summary_rows = []

    for name, runner, csv_name in EXPERIMENTS:
        t0 = time.perf_counter()
        try:
            runner()
            status = "COMPLETED"
        except Exception as e:
            status = f"FAILED: {e}"

        elapsed = time.perf_counter() - t0
        csv_file = RESULTS_DIR / csv_name
        file_exists = csv_file.exists() and csv_file.stat().st_size > 0

        summary_rows.append({
            "name": name,
            "status": status,
            "csv_file": csv_name,
            "csv_ok": "YES" if file_exists else "MISSING",
            "time_sec": round(elapsed, 2),
        })

    total_elapsed = time.perf_counter() - t_start

    print("\n" + "=" * 90)
    print("                        EXPERIMENT EXECUTION SUMMARY")
    print("=" * 90)
    print(f"{'Experiment':<38} | {'Status':<12} | {'CSV Export':<18} | {'Time (s)'}")
    print("-" * 90)

    all_passed = True
    for row in summary_rows:
        csv_str = f"{row['csv_file']} ({row['csv_ok']})"
        print(f"{row['name']:<38} | {row['status']:<12} | {csv_str:<18} | {row['time_sec']:>7.2f}")
        if row["status"] != "COMPLETED" or row["csv_ok"] != "YES":
            all_passed = False

    print("-" * 90)
    print(f"Total Suite Runtime: {total_elapsed:.2f} seconds")
    print(f"Artifacts Written to: {RESULTS_DIR}")
    print("=" * 90)

    if not all_passed:
        raise RuntimeError("One or more experiments failed or missed generating their CSV output.")
    print("\nAll experiments successfully completed and validated.")


if __name__ == "__main__":
    run_all()
