"""Experiment 3: Certification Proof — H-Guesser against Random vs Certified Test Sets.

TOC Concept: Certificate Hardness Invariant, Witness Separation, and Oracle Soundness.
"""

from __future__ import annotations

import csv
from pathlib import Path
import random

from veridyn.challenge.certify import consistent
from veridyn.challenge.generator import generate_challenge
from veridyn.challenge.hypotheses import build_hypothesis_library
from veridyn.core.dfa import dfa_accepts

RESULTS_DIR = Path(__file__).resolve().parent / "results"
CSV_PATH = RESULTS_DIR / "certification.csv"


def generate_random_test_strings(k: int, rng: random.Random) -> list[str]:
    """Generate k random test strings over {C, T, S} with length in [1, 8]."""
    alphabet = ["C", "T", "S"]
    tests: list[str] = []
    while len(tests) < k:
        length = rng.randint(1, 8)
        s = "".join(rng.choices(alphabet, k=length))
        if s not in tests:
            tests.append(s)
    return tests


def evaluate_level(
    level: int,
    num_challenges: int = 30,
    k: int = 6,
    base_seed: int = 42000,
) -> dict[str, str | int | float]:
    """Evaluate H-guesser pass rates on random vs certified test suites for a given level."""
    H = build_hypothesis_library()
    rng = random.Random(base_seed + level * 1000)

    total_consistent_hyps = 0
    random_passes = 0
    certified_passes = 0
    total_evaluations = 0

    for idx in range(num_challenges):
        seed = base_seed + level * 500 + idx
        chal = generate_challenge(level=level, seed=seed)
        examples = (list(chal.positive_examples), list(chal.negative_examples))

        # Find all hypotheses in H consistent with observation examples
        consistent_H = [h for h in H if consistent(h.dfa, examples)]
        if not consistent_H:
            continue

        total_consistent_hyps += len(consistent_H)
        total_evaluations += len(consistent_H)

        # 1. Condition A: Random Test Strings
        random_tests = generate_random_test_strings(k=k, rng=rng)
        truth_random_verdicts = [dfa_accepts(chal.dfa, t) for t in random_tests]

        for h in consistent_H:
            h_random_verdicts = [dfa_accepts(h.dfa, t) for t in random_tests]
            if h_random_verdicts == truth_random_verdicts:
                random_passes += 1

        # 2. Condition B: Certified Test Strings
        truth_cert_verdicts = [dfa_accepts(chal.dfa, t) for t in chal.test_strings]
        for h in consistent_H:
            h_cert_verdicts = [dfa_accepts(h.dfa, t) for t in chal.test_strings]
            if h_cert_verdicts == truth_cert_verdicts:
                certified_passes += 1

    avg_consistent = total_consistent_hyps / max(1, num_challenges)
    random_pass_rate = (random_passes / max(1, total_evaluations)) * 100.0
    certified_pass_rate = (certified_passes / max(1, total_evaluations)) * 100.0

    return {
        "level": level,
        "challenges_tested": num_challenges,
        "total_consistent_hypotheses": total_evaluations,
        "avg_consistent_per_challenge": round(avg_consistent, 2),
        "random_tests_pass_count": random_passes,
        "random_tests_pass_rate_pct": round(random_pass_rate, 2),
        "certified_tests_pass_count": certified_passes,
        "certified_tests_pass_rate_pct": round(certified_pass_rate, 4),
    }


def run_experiment() -> list[dict[str, str | int | float]]:
    """Execute certification effectiveness experiment across all 5 levels."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n{'='*80}")
    print("EXPERIMENT 3: H-Guesser Pass Rates: Random Tests vs Certified Witness Tests")
    print(f"{'='*80}")
    print(f"{'Level':<6} | {'Challenges':<11} | {'Avg Consistent':<15} | {'Random Pass Rate':<18} | {'Certified Pass Rate'}")
    print("-" * 80)

    results = []
    for level in range(1, 6):
        res = evaluate_level(level=level, num_challenges=30)
        results.append(res)
        print(
            f"{res['level']:<6} | {res['challenges_tested']:<11} | "
            f"{res['avg_consistent_per_challenge']:<15} | "
            f"{res['random_tests_pass_rate_pct']:>6.2f}% ({res['random_tests_pass_count']}/{res['total_consistent_hypotheses']})  | "
            f"{res['certified_tests_pass_rate_pct']:>6.4f}% ({res['certified_tests_pass_count']}/{res['total_consistent_hypotheses']})"
        )

        # Invariant assertion: certified pass rate must be strictly 0.00%
        assert res["certified_tests_pass_count"] == 0, (
            f"Level {level} permitted {res['certified_tests_pass_count']} consistent hypotheses to pass certified tests!"
        )

    print("-" * 80)
    print("Result: Certified witness construction guarantees exactly 0.0000% pass rate for any H-guesser.")

    # Write CSV
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print(f"CSV saved to {CSV_PATH}")
    return results


if __name__ == "__main__":
    run_experiment()
