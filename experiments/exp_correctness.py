"""Experiment 1: Exhaustive Differential Correctness Verification.

TOC Concept: Differential Oracle Testing, Semantic Equivalence Across Representations (RE, NFA, DFA, Minimal DFA).
"""

from __future__ import annotations

import csv
from itertools import product
from pathlib import Path
import re
import time

from veridyn.core.dfa import dfa_accepts, subset_construction
from veridyn.core.minimize import minimize
from veridyn.core.nfa import eliminate_epsilon, nfa_accepts, thompson
from veridyn.core.regex_parser import DEFAULT_ALPHABET, desugar, parse

RESULTS_DIR = Path(__file__).resolve().parent / "results"
CSV_PATH = RESULTS_DIR / "correctness.csv"

TEST_REGEXES: list[str] = [
    "C",
    "T*",
    "(C|T)*",
    "C*T*",
    "(C|T)*S(C|T)*",
    "C(T|S)*C",
    "(CT)+",
    "C{1,3}",
    "(C|T){2,4}",
    "C?T+S*",
    "((C|T)*S)+",
    "(CC)*|(TT)*",
    "(C|T)*C(C|T){2}",
    "(C|S)*T(C|S)*",
    "C{2,}",
    "(CT|SC)*",
    "(C|T)*S",
    "C(T|S(C|T))",
]


def generate_all_strings(alphabet: set[str] | frozenset[str], max_len: int) -> list[str]:
    """Enumerate all strings over alphabet up to max_len."""
    alpha_sorted = sorted(alphabet)
    strings = [""]
    for length in range(1, max_len + 1):
        for combo in product(alpha_sorted, repeat=length):
            strings.append("".join(combo))
    return strings


def run_experiment(max_len: int = 5) -> list[dict[str, str | int]]:
    """Run differential correctness tests and return results rows."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    alphabet = DEFAULT_ALPHABET
    all_strings = generate_all_strings(alphabet, max_len)
    total_strings = len(all_strings)

    results: list[dict[str, str | int]] = []
    print(f"\n{'='*80}")
    print(f"EXPERIMENT 1: Exhaustive Differential Testing (Strings up to length {max_len}, N={total_strings})")
    print(f"{'='*80}")
    print(f"{'Regex':<26} | {'Strings':<8} | {'re':<6} | {'NFA':<6} | {'eps-free':<8} | {'DFA':<6} | {'MinDFA':<6} | {'Mismatches'}")
    print(f"{'-'*80}")

    total_mismatches = 0

    for pattern in TEST_REGEXES:
        ast = parse(pattern, alphabet=alphabet)
        core_ast = desugar(ast)

        # Build representations
        nfa = thompson(core_ast, alphabet=alphabet)
        efree_nfa = eliminate_epsilon(nfa)
        dfa = subset_construction(nfa)
        min_dfa = minimize(dfa)
        py_pattern = re.compile(f"^(?:{pattern})$")

        mismatches = 0
        re_matches = 0
        nfa_matches = 0
        efree_matches = 0
        dfa_matches = 0
        min_dfa_matches = 0

        for s in all_strings:
            r_val = bool(py_pattern.fullmatch(s))
            n_val = nfa_accepts(nfa, s)
            e_val = nfa_accepts(efree_nfa, s)
            d_val = dfa_accepts(dfa, s)
            m_val = dfa_accepts(min_dfa, s)

            if r_val: re_matches += 1
            if n_val: nfa_matches += 1
            if e_val: efree_matches += 1
            if d_val: dfa_matches += 1
            if m_val: min_dfa_matches += 1

            if not (r_val == n_val == e_val == d_val == m_val):
                mismatches += 1

        total_mismatches += mismatches
        row = {
            "regex": pattern,
            "strings_tested": total_strings,
            "re_matches": re_matches,
            "nfa_matches": nfa_matches,
            "efree_matches": efree_matches,
            "dfa_matches": dfa_matches,
            "min_dfa_matches": min_dfa_matches,
            "mismatches": mismatches,
        }
        results.append(row)

        print(
            f"{pattern:<26} | {total_strings:<8} | {re_matches:<6} | {nfa_matches:<6} | "
            f"{efree_matches:<8} | {dfa_matches:<6} | {min_dfa_matches:<6} | {mismatches}"
        )

    print(f"{'-'*80}")
    print(f"Total Mismatches Across All Models: {total_mismatches} (Expected: 0)")
    assert total_mismatches == 0, f"Expected 0 mismatches, found {total_mismatches}!"

    # Write CSV
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print(f"CSV saved to {CSV_PATH}")
    return results


if __name__ == "__main__":
    run_experiment()
