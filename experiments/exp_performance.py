"""Experiment 2: Performance, Automata Sizes, Blow-Up Family, and Certification Latency.

TOC Concept: State Complexity, Subset Construction Blow-Up, and Verification Latency Scaling.
"""

from __future__ import annotations

import csv
from pathlib import Path
import time

from veridyn.challenge.certify import certify
from veridyn.challenge.generator import generate_challenge
from veridyn.challenge.hypotheses import build_hypothesis_library
from veridyn.core.dfa import subset_construction
from veridyn.core.minimize import minimize
from veridyn.core.nfa import thompson
from veridyn.core.regex_parser import DEFAULT_ALPHABET, desugar, parse

RESULTS_DIR = Path(__file__).resolve().parent / "results"
CSV_PATH = RESULTS_DIR / "performance.csv"


def evaluate_model_sizes() -> list[dict[str, str | int | float]]:
    """Measure build times and state sizes vs regex size."""
    regexes = [
        "C",
        "C|T",
        "(C|T)*",
        "(C|T)*S",
        "(C|T)*S(C|T)*",
        "((C|T)*S)+",
        "(C|T){1,3}S",
        "(CC|TT|SS)*",
        "(C|T)*C(C|T)*T(C|T)*S",
        "((C|T)*S){1,2}|(T|S){1,2}",
    ]

    rows = []
    print("\n--- Part A: Model Sizes and Conversion Times vs Regex Complexity ---")
    print(f"{'Regex':<30} | {'Len':<4} | {'NFA |Q|':<8} | {'DFA |Q|':<8} | {'Min |Q|':<8} | {'Time (ms)'}")
    print("-" * 75)

    for pat in regexes:
        t0 = time.perf_counter()
        ast = parse(pat, alphabet=DEFAULT_ALPHABET)
        core_ast = desugar(ast)
        nfa = thompson(core_ast, alphabet=DEFAULT_ALPHABET)
        dfa = subset_construction(nfa)
        min_dfa = minimize(dfa)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        row = {
            "category": "regex_complexity",
            "identifier": pat,
            "param": len(pat),
            "nfa_states": len(nfa.states),
            "dfa_states": len(dfa.states),
            "min_dfa_states": len(min_dfa.states),
            "latency_ms": round(elapsed_ms, 3),
        }
        rows.append(row)
        print(f"{pat:<30} | {len(pat):<4} | {len(nfa.states):<8} | {len(dfa.states):<8} | {len(min_dfa.states):<8} | {elapsed_ms:>8.3f}")

    return rows


def evaluate_blowup_family() -> list[dict[str, str | int | float]]:
    """Measure exponential blow-up family (C|T)*C(C|T)^k."""
    rows = []
    print("\n--- Part B: Exponential Subset Construction Blow-Up: (C|T)*C(C|T)^k ---")
    print(f"{'k':<3} | {'Regex':<24} | {'NFA |Q|':<8} | {'DFA |Q|':<8} | {'Min |Q|':<8} | {'Theoretical 2^(k+1)+2':<22} | {'Time (ms)'}")
    print("-" * 88)

    for k in range(1, 7):
        pat = f"(C|T)*C(C|T){{{k}}}"
        t0 = time.perf_counter()
        ast = parse(pat, alphabet=DEFAULT_ALPHABET, max_repetition_bound=k)
        core_ast = desugar(ast)
        nfa = thompson(core_ast, alphabet=DEFAULT_ALPHABET)
        dfa = subset_construction(nfa)
        min_dfa = minimize(dfa)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        theoretical = 2 ** (k + 1) + 2
        row = {
            "category": "exponential_blowup",
            "identifier": pat,
            "param": k,
            "nfa_states": len(nfa.states),
            "dfa_states": len(dfa.states),
            "min_dfa_states": len(min_dfa.states),
            "latency_ms": round(elapsed_ms, 3),
        }
        rows.append(row)
        print(f"{k:<3} | {pat:<24} | {len(nfa.states):<8} | {len(dfa.states):<8} | {len(min_dfa.states):<8} | {theoretical:<22} | {elapsed_ms:>8.3f}")

    return rows


def evaluate_certification_latency() -> list[dict[str, str | int | float]]:
    """Measure challenge generation and certification times across difficulty levels."""
    rows = []
    print("\n--- Part C: Challenge Synthesis and Certification Latency per Level ---")
    print(f"{'Level':<6} | {'Challenges':<11} | {'Avg Gen (ms)':<14} | {'Avg Cert (ms)':<14} | {'Avg Total (ms)'}")
    print("-" * 65)

    H = build_hypothesis_library()

    for level in range(1, 6):
        num_trials = 10
        gen_times = []
        cert_times = []

        for i in range(num_trials):
            seed = 9000 + level * 100 + i
            t_start = time.perf_counter()
            chal = generate_challenge(level=level, seed=seed)
            t_gen = time.perf_counter()

            # Measure stand-alone certification step
            examples = (list(chal.positive_examples), list(chal.negative_examples))
            t_cert_start = time.perf_counter()
            cert = certify(chal.dfa, examples, list(chal.test_strings), H)
            t_cert_end = time.perf_counter()

            gen_times.append((t_gen - t_start) * 1000.0)
            cert_times.append((t_cert_end - t_cert_start) * 1000.0)

        avg_gen = sum(gen_times) / len(gen_times)
        avg_cert = sum(cert_times) / len(cert_times)
        avg_total = avg_gen + avg_cert

        row = {
            "category": "certification_latency",
            "identifier": f"level_{level}",
            "param": level,
            "nfa_states": len(chal.dfa.states),
            "dfa_states": len(chal.dfa.states),
            "min_dfa_states": len(chal.dfa.states),
            "latency_ms": round(avg_total, 3),
        }
        rows.append(row)
        print(f"{level:<6} | {num_trials:<11} | {avg_gen:>12.3f}   | {avg_cert:>12.3f}   | {avg_total:>12.3f}")

    return rows


def run_experiment() -> list[dict[str, str | int | float]]:
    """Execute all performance and blow-up benchmarks and export CSV."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n{'='*80}")
    print("EXPERIMENT 2: Automata Performance, Size Scaling, and Certification Latency")
    print(f"{'='*80}")

    all_rows = []
    all_rows.extend(evaluate_model_sizes())
    all_rows.extend(evaluate_blowup_family())
    all_rows.extend(evaluate_certification_latency())

    # Write CSV
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["category", "identifier", "param", "nfa_states", "dfa_states", "min_dfa_states", "latency_ms"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nCSV saved to {CSV_PATH}")
    return all_rows


if __name__ == "__main__":
    run_experiment()
