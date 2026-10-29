"""Experiment 4: Coin-Flip Guessing Baseline vs Analytic 2^-k Bound.

TOC Concept: Information-Theoretic Lower Bounds on Random Guessing under Binary Oracle Classification.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
import random

RESULTS_DIR = Path(__file__).resolve().parent / "results"
CSV_PATH = RESULTS_DIR / "coin_flip.csv"


def simulate_coin_flips(k: int, trials: int, rng: random.Random) -> dict[str, int | float]:
    """Simulate random binary guesses for k test strings over N trials."""
    passes = 0
    # True string classifications (e.g. alternating valid/invalid)
    truth = [i % 2 for i in range(k)]

    for _ in range(trials):
        guesses = [rng.randint(0, 1) for _ in range(k)]
        if guesses == truth:
            passes += 1

    analytic_prob = 2.0 ** (-k)
    empirical_rate = passes / trials
    std_error = math.sqrt(analytic_prob * (1.0 - analytic_prob) / trials)
    z_score = (empirical_rate - analytic_prob) / std_error if std_error > 0 else 0.0

    return {
        "k": k,
        "trials": trials,
        "passes": passes,
        "empirical_pass_rate": round(empirical_rate, 6),
        "analytic_bound": round(analytic_prob, 6),
        "std_error": round(std_error, 6),
        "z_score": round(z_score, 3),
        "empirical_pct": round(empirical_rate * 100.0, 4),
        "analytic_pct": round(analytic_prob * 100.0, 4),
    }


def run_experiment(trials: int = 100000, seed: int = 1337) -> list[dict[str, int | float]]:
    """Execute coin-flip baseline experiment across test sizes k in {4, 6, 8, 10}."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)

    print(f"\n{'='*80}")
    print(f"EXPERIMENT 4: Random Respondent (Coin-Flip) Baseline (N={trials:,} Trials)")
    print(f"{'='*80}")
    print(f"{'k':<4} | {'Trials':<10} | {'Passes':<8} | {'Empirical Pass %':<18} | {'Analytic 2^-k %':<16} | {'z-score'}")
    print("-" * 80)

    results = []
    for k in (4, 6, 8, 10):
        res = simulate_coin_flips(k=k, trials=trials, rng=rng)
        results.append(res)
        print(
            f"{res['k']:<4} | {res['trials']:<10} | {res['passes']:<8} | "
            f"{res['empirical_pct']:>7.4f}%           | {res['analytic_pct']:>7.4f}%         | {res['z_score']:>6.3f}"
        )

    print("-" * 80)
    print("Conclusion: At default k=6, a random guesser passes with probability ~1.56% (2^-6), tightly matching theory.")

    # Write CSV
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print(f"CSV saved to {CSV_PATH}")
    return results


if __name__ == "__main__":
    run_experiment()
