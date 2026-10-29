"""Decision properties, dynamic programming word counting, and uniform sampling on regular languages.

TOC Concept: Enumeration of Regular Languages, Generating Functions and Dynamic Programming
over DFA State Transition Matrices, and Exact Uniform Sampling from Regular Languages.
"""

from __future__ import annotations

import random
from typing import Sequence

from veridyn.core.dfa import DFA


def count_accepted(dfa: DFA, max_len: int) -> list[int]:
    """Count the exact number of accepted strings for each length from 0 to max_len using DP.

    TOC Concept:
        Dynamic Programming over Finite Automata:
        Let N(q, k) be the number of strings of length k that lead from state q to an accepting state in F.
            Base Case:  N(q, 0) = 1 if q in F else 0
            Induction:  N(q, k) = sum_{a in Sigma} N(delta(q, a), k - 1)
        Counts are calculated using exact Python arbitrary-precision integers.

    Args:
        dfa: Complete deterministic finite automaton.
        max_len: Maximum string length to enumerate (inclusive, >= 0).

    Returns:
        List of counts of length max_len + 1, where counts[k] is the number of
        strings in L(dfa) of length k.
    """
    if max_len < 0:
        return []

    states = list(dfa.states)
    alphabet = list(dfa.alphabet)

    # dp[k][q] stores N(q, k)
    # Base case k = 0
    curr_dp: dict[int, int] = {
        q: 1 if q in dfa.accepting else 0 for q in states
    }

    results: list[int] = [curr_dp[dfa.start]]

    for _ in range(1, max_len + 1):
        next_dp: dict[int, int] = {}
        for q in states:
            total_paths = 0
            for a in alphabet:
                target = dfa.delta[(q, a)]
                total_paths += curr_dp[target]
            next_dp[q] = total_paths

        results.append(next_dp[dfa.start])
        curr_dp = next_dp

    return results


def count_rejected(dfa: DFA, max_len: int) -> list[int]:
    """Count the exact number of rejected strings for each length from 0 to max_len.

    TOC Concept:
        For an alphabet of size |Sigma|, there are exactly |Sigma|^k strings of length k.
        The number of rejected strings is:
            N_rej(k) = |Sigma|^k - N_acc(k).
    """
    if max_len < 0:
        return []

    acc_counts = count_accepted(dfa, max_len)
    sigma_size = len(dfa.alphabet)

    results: list[int] = []
    for k, acc in enumerate(acc_counts):
        total_strings = sigma_size ** k
        results.append(total_strings - acc)

    return results


def _build_dp_table(dfa: DFA, max_len: int, accepted: bool) -> dict[int, list[int]]:
    """Build full state DP table: table[q][k] is the number of valid paths of length k from q."""
    states = list(dfa.states)
    alphabet = list(dfa.alphabet)

    # table[q] is list of length max_len + 1
    table: dict[int, list[int]] = {q: [0] * (max_len + 1) for q in states}

    # Base case k = 0
    for q in states:
        if accepted:
            table[q][0] = 1 if q in dfa.accepting else 0
        else:
            table[q][0] = 1 if q not in dfa.accepting else 0

    # Inductive fill
    for k in range(1, max_len + 1):
        for q in states:
            total = 0
            for a in alphabet:
                target = dfa.delta[(q, a)]
                total += table[target][k - 1]
            table[q][k] = total

    return table


def sample_strings(
    dfa: DFA,
    accepted: bool,
    length_range: tuple[int, int] | Sequence[int] | int,
    n: int,
    rng: random.Random,
) -> list[str]:
    """Draw n strings UNIFORMLY at random from accepted or rejected words in a length range.

    TOC Algorithm:
        Exact Combinatorial Sampling on Directed Acyclic Graph of Computations:
        Using precomputed DP path counts, at each step from state q with k remaining symbols,
        symbol a is selected with exact probability:
            P(a) = table[delta(q, a)][k - 1] / table[q][k]
        This telescoping product guarantees that every valid string of length L is
        sampled with identical probability P(w) = 1 / Total_Valid(L).
        Guarantees zero reliance on global random state.

    Args:
        dfa: Complete deterministic finite automaton.
        accepted: If True, samples from L(dfa); if False, samples from Sigma* \\ L(dfa).
        length_range: Target length, range (min, max), or sequence of allowable lengths.
        n: Number of strings to generate (>= 0).
        rng: Seeded random.Random instance.

    Returns:
        List of n uniformly sampled strings matching the acceptance criterion.

    Raises:
        ValueError: If no valid strings exist in the specified length range.
    """
    if n <= 0:
        return []

    # Parse length options
    if isinstance(length_range, int):
        target_lengths = [length_range]
    elif isinstance(length_range, tuple) and len(length_range) == 2:
        target_lengths = list(range(length_range[0], length_range[1] + 1))
    else:
        target_lengths = list(length_range)

    target_lengths = [L for L in target_lengths if L >= 0]
    if not target_lengths:
        raise ValueError("length_range must contain non-negative integer lengths.")

    max_l = max(target_lengths)
    dp_table = _build_dp_table(dfa, max_l, accepted)

    # Filter to lengths that have at least one valid string from start state
    valid_lengths = [L for L in target_lengths if dp_table[dfa.start][L] > 0]
    if not valid_lengths:
        mode_str = "accepted" if accepted else "rejected"
        raise ValueError(
            f"No {mode_str} strings exist for lengths in {target_lengths}."
        )

    alphabet_sorted = sorted(dfa.alphabet)
    sampled_strings: list[str] = []

    for _ in range(n):
        # Choose a target length uniformly among valid lengths
        chosen_len = rng.choice(valid_lengths)

        curr = dfa.start
        chars: list[str] = []

        for remaining in range(chosen_len, 0, -1):
            weights: list[int] = []
            for a in alphabet_sorted:
                target = dfa.delta[(curr, a)]
                weights.append(dp_table[target][remaining - 1])

            # Draw symbol proportional to the count of valid continuations
            chosen_sym = rng.choices(alphabet_sorted, weights=weights, k=1)[0]
            chars.append(chosen_sym)
            curr = dfa.delta[(curr, chosen_sym)]

        sampled_strings.append("".join(chars))

    return sampled_strings


__all__ = [
    "count_accepted",
    "count_rejected",
    "sample_strings",
]
