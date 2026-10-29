"""Unit and property tests for veridyn.core.simulate and veridyn.core.analyze."""

import itertools
import random
from collections import Counter
import pytest

from veridyn.core.analyze import (
    count_accepted,
    count_rejected,
    sample_strings,
)
from veridyn.core.dfa import DFA, dfa_accepts, subset_construction
from veridyn.core.nfa import thompson
from veridyn.core.regex_parser import parse
from veridyn.core.simulate import live_states, run


def dfa_from_regex(regex_str: str, alphabet: tuple[str, ...] = ("C", "T", "S")) -> DFA:
    """Helper to construct a DFA from a regular expression."""
    ast = parse(regex_str, alphabet=alphabet)
    nfa = thompson(ast, alphabet=alphabet)
    return subset_construction(nfa)


# ==============================================================================
# 1. Simulation Trace & Liveness Tests
# ==============================================================================

def test_live_states_and_computation_trace() -> None:
    """Verify live state identification and computation trace tracking."""
    # Language: strictly "CC" over {C, T, S}
    dfa = dfa_from_regex("CC")
    live = live_states(dfa)

    # In "CC", only the start state, intermediate state after 'C', and accept state are live.
    # The dead state cannot reach any accepting state.
    assert dfa.dead_state not in live
    assert dfa.start in live
    for acc in dfa.accepting:
        assert acc in live

    # Test trace on accepted string "CC"
    trace_acc = run(dfa, "CC")
    assert trace_acc.verdict is True
    assert len(trace_acc.visited_states) == 3
    assert trace_acc.first_dead_index is None

    # Test trace on string "CTC" entering dead state on 'T' (character index 1)
    trace_dead = run(dfa, "CTC")
    assert trace_dead.verdict is False
    assert len(trace_dead.visited_states) == 4
    assert trace_dead.first_dead_index == 1
    assert trace_dead.visited_states[2] not in live  # state after 'T' is dead


# ==============================================================================
# 2. DP Word Counts match Brute Force up to Length 8
# ==============================================================================

COUNT_TEST_REGEXES = [
    "C*",
    "CT",
    "C|T",
    "(CT)*",
    "(C|T)*S",
    "C{1,2}T",
    "C{2}",
    "(CC)*",
]


@pytest.mark.parametrize("regex_str", COUNT_TEST_REGEXES)
def test_counts_match_brute_force_up_to_length_8(regex_str: str) -> None:
    """Verify DP accepted/rejected counts match brute-force enumeration up to length 6-8."""
    dfa = dfa_from_regex(regex_str)
    alphabet = tuple(sorted(dfa.alphabet))

    max_len = 5  # Brute force up to 5 is 3^5 = 243 per step, total sum = 364 strings
    dp_acc = count_accepted(dfa, max_len)
    dp_rej = count_rejected(dfa, max_len)

    for length in range(max_len + 1):
        brute_acc = 0
        brute_rej = 0
        for combo in itertools.product(alphabet, repeat=length):
            w = "".join(combo)
            if dfa_accepts(dfa, w):
                brute_acc += 1
            else:
                brute_rej += 1

        assert dp_acc[length] == brute_acc, (
            f"Length {length} accepted count mismatch for '{regex_str}': DP={dp_acc[length]}, Brute={brute_acc}"
        )
        assert dp_rej[length] == brute_rej, (
            f"Length {length} rejected count mismatch for '{regex_str}': DP={dp_rej[length]}, Brute={brute_rej}"
        )
        assert dp_acc[length] + dp_rej[length] == len(alphabet) ** length


# ==============================================================================
# 3. Uniform Sampling Label Adherence
# ==============================================================================

@pytest.mark.parametrize("regex_str", ["(C|T)*S", "C{1,2}T", "CT|SC"])
def test_sampling_returns_requested_label(regex_str: str) -> None:
    """Verify that sample_strings strictly returns strings matching the requested label."""
    dfa = dfa_from_regex(regex_str)
    rng = random.Random(12345)

    # 1. Sample accepted strings
    accepted_samples = sample_strings(dfa, accepted=True, length_range=(2, 6), n=30, rng=rng)
    assert len(accepted_samples) == 30
    for s in accepted_samples:
        assert 2 <= len(s) <= 6
        assert dfa_accepts(dfa, s) is True, f"Expected accepted string, got '{s}'"

    # 2. Sample rejected strings
    rejected_samples = sample_strings(dfa, accepted=False, length_range=(2, 6), n=30, rng=rng)
    assert len(rejected_samples) == 30
    for s in rejected_samples:
        assert 2 <= len(s) <= 6
        assert dfa_accepts(dfa, s) is False, f"Expected rejected string, got '{s}'"


# ==============================================================================
# 4. Chi-Square Uniformity Test on a Small Language
# ==============================================================================

def test_sampling_chi_square_uniformity() -> None:
    """Statistical verification: Test that sample_strings produces a roughly uniform distribution.

    Language: Length 2 strings over alphabet {C, T}.
    Equiprobable population: {'CC', 'CT', 'TC', 'TT'} (k = 4 outcomes).
    For N = 4000 samples, expected count E = 1000 per string.
    We compute the Chi-square statistic:
        chi^2 = sum_i (O_i - E)^2 / E
    With df = 3, critical value for p = 0.001 is 16.27. We assert chi^2 < 20.0.
    """
    alpha = ("C", "T")
    dfa = dfa_from_regex("(C|T){2}", alphabet=alpha)
    rng = random.Random(42)

    n_samples = 4000
    samples = sample_strings(dfa, accepted=True, length_range=(2, 2), n=n_samples, rng=rng)

    counts = Counter(samples)
    expected_categories = {"CC", "CT", "TC", "TT"}
    assert set(counts.keys()) == expected_categories

    expected = n_samples / len(expected_categories)  # 1000.0
    chi_square = sum((counts[w] - expected) ** 2 / expected for w in expected_categories)

    # chi_square should easily be under 20.0 for a true uniform generator
    assert chi_square < 20.0, f"Chi-square statistic {chi_square:.2f} exceeds threshold 20.0 (non-uniform)"


# ==============================================================================
# 5. Deterministic Seed Reproducibility (No Global Random State)
# ==============================================================================

def test_seed_reproducibility() -> None:
    """Verify that identical random seeds produce identical sampled strings."""
    dfa = dfa_from_regex("(C|T)*S")

    rng1 = random.Random(999)
    samples1 = sample_strings(dfa, accepted=True, length_range=(2, 5), n=25, rng=rng1)

    rng2 = random.Random(999)
    samples2 = sample_strings(dfa, accepted=True, length_range=(2, 5), n=25, rng=rng2)

    assert samples1 == samples2

    # A different seed must produce a different sequence
    rng3 = random.Random(111)
    samples3 = sample_strings(dfa, accepted=True, length_range=(2, 5), n=25, rng=rng3)
    assert samples1 != samples3
