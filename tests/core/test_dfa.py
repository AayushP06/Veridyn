"""Unit and differential tests for veridyn.core.dfa and epsilon-free NFA conversion."""

import itertools
import pytest

from veridyn.core.dfa import (
    DFA,
    dfa_accepts,
    subset_construction,
)
from veridyn.core.nfa import (
    NFA,
    eliminate_epsilon,
    nfa_accepts,
    thompson,
)
from veridyn.core.regex_parser import (
    Epsilon,
    parse,
)

# ==============================================================================
# Fixture: All 9,841 strings up to length 8 over {C, T, S}
# ==============================================================================

@pytest.fixture(scope="session")
def all_strings_up_to_8() -> list[str]:
    """Generate all 9,841 strings over alphabet {C, T, S} with length in [0, 8]."""
    alphabet = ("C", "T", "S")
    strings: list[str] = [""]
    for length in range(1, 9):
        for combo in itertools.product(alphabet, repeat=length):
            strings.append("".join(combo))
    assert len(strings) == 9841
    return strings


# ==============================================================================
# Test Corpus: 22 Diverse Regular Expressions
# ==============================================================================

REGEX_CORPUS = [
    "C",
    "T",
    "S",
    "CT",
    "CTS",
    "C|T",
    "C|T|S",
    "CT|SC",
    "C*",
    "(CT)*",
    "(C|T)*",
    "(C*)*",
    "(C|T)*S",
    "C(T|S)*",
    "(C|T)*S(C|T)*",
    "C+",
    "(CT)+",
    "C?",
    "(C|T)?S",
    "C{2}",
    "C{1,2}T",
    "(CC)*",
]


@pytest.mark.parametrize("regex_str", REGEX_CORPUS)
def test_three_way_agreement_exhaustive(regex_str: str, all_strings_up_to_8: list[str]) -> None:
    """Differential test: NFA, epsilon-free NFA, and DFA must agree on all 9,841 strings."""
    ast = parse(regex_str)
    nfa = thompson(ast)
    nfa_no_eps = eliminate_epsilon(nfa)
    dfa = subset_construction(nfa)

    # 1. Structural checks on epsilon-free NFA
    for (src, sym) in nfa_no_eps.transitions:
        assert sym is not None, f"Epsilon transition found in epsilon-free NFA for '{regex_str}'"

    # 2. Strict completeness check on DFA
    for q in dfa.states:
        for a in dfa.alphabet:
            assert (q, a) in dfa.delta, f"DFA for '{regex_str}' missing transition ({q}, '{a}')"
            assert dfa.delta[(q, a)] in dfa.states

    # 3. Explicit dead state check
    assert dfa.dead_state in dfa.states
    assert dfa.dead_state not in dfa.accepting
    for a in dfa.alphabet:
        assert dfa.delta[(dfa.dead_state, a)] == dfa.dead_state

    # 4. Exhaustive 3-way language equivalence test
    mismatches: list[str] = []
    for s in all_strings_up_to_8:
        res_nfa = nfa_accepts(nfa, s)
        res_no_eps = nfa_accepts(nfa_no_eps, s)
        res_dfa = dfa_accepts(dfa, s)

        if not (res_nfa == res_no_eps == res_dfa):
            mismatches.append(
                f"string='{s}': nfa={res_nfa}, no_eps={res_no_eps}, dfa={res_dfa}"
            )
            if len(mismatches) >= 5:
                break

    assert not mismatches, f"Mismatches for '{regex_str}': {mismatches}"


def test_epsilon_regex_three_way_agreement(all_strings_up_to_8: list[str]) -> None:
    """Edge case: Epsilon regex language equivalence across NFA, epsilon-free NFA, and DFA."""
    nfa = thompson(Epsilon())
    nfa_no_eps = eliminate_epsilon(nfa)
    dfa = subset_construction(nfa)

    assert dfa_accepts(dfa, "") is True
    assert nfa_accepts(nfa_no_eps, "") is True

    for s in all_strings_up_to_8:
        expected = (s == "")
        assert nfa_accepts(nfa, s) == expected
        assert nfa_accepts(nfa_no_eps, s) == expected
        assert dfa_accepts(dfa, s) == expected


def test_dfa_completeness_and_dead_state() -> None:
    """Verify that all DFAs are complete and have valid explicit dead states."""
    test_cases = ["C", "C|T", "(C|T)*", "C{2,}", "(C|T|S)*"]
    for r in test_cases:
        ast = parse(r)
        dfa = subset_construction(thompson(ast))

        # Check total transition count = |states| * |alphabet|
        expected_transitions = len(dfa.states) * len(dfa.alphabet)
        assert len(dfa.delta) == expected_transitions

        # Dead state must exist and strictly self-loop
        d = dfa.dead_state
        assert d in dfa.states
        assert d not in dfa.accepting
        for a in dfa.alphabet:
            assert dfa.delta[(d, a)] == d


# ==============================================================================
# Exponential Blow-Up Table: (C|T)*C(C|T){k} for k = 1..8
# ==============================================================================

def test_exponential_blowup_table() -> None:
    """TOC Theorem Test: Subset construction state explosion on (C|T)*C(C|T){k}.

    Language: Strings where the (k+1)-th character from the end is 'C'.
    Over alphabet Sigma = {C, T, S}, an NFA requires O(k) states, while a DFA
    must track the last k symbols of the sliding window, requiring at least 2^k states.
    """
    print("\n" + "=" * 78)
    print(f"{'k':<3} | {'Regex':<26} | {'NFA |Q|':<8} | {'DFA |Q|':<8} | {'Lower Bound 2^k':<15} | {'Ratio |Q_DFA|/|Q_NFA|':<18}")
    print("-" * 78)

    dfa_state_counts: list[int] = []

    for k in range(1, 9):
        regex_str = f"(C|T)*C(C|T){{{k}}}"
        ast = parse(regex_str, max_repetition_bound=8)
        nfa = thompson(ast)
        dfa = subset_construction(nfa)

        nfa_q = len(nfa.states)
        dfa_q = len(dfa.states)
        lower_bound = 2 ** k
        ratio = dfa_q / nfa_q

        dfa_state_counts.append(dfa_q)

        print(
            f"{k:<3} | {regex_str:<26} | {nfa_q:<8} | {dfa_q:<8} | {lower_bound:<15} | {ratio:<18.2f}"
        )

        # Assert exponential growth lower bound
        # The DFA must maintain at least 2^k distinct subsets for the sliding window
        assert dfa_q >= lower_bound, (
            f"Expected DFA states >= 2^{k} ({lower_bound}), but got {dfa_q}"
        )

    print("=" * 78)

    # Strictly verify exponential increase: DFA state count strictly follows 2^(k+1) + 2
    for i in range(1, len(dfa_state_counts)):
        k_val = i + 1
        assert dfa_state_counts[i] > dfa_state_counts[i - 1]
        assert dfa_state_counts[i] == 2 ** (k_val + 1) + 2, (
            f"Expected 2^({k_val}+1)+2 = {2 ** (k_val + 1) + 2}, got {dfa_state_counts[i]}"
        )
        growth_factor = dfa_state_counts[i] / dfa_state_counts[i - 1]
        assert growth_factor >= 1.6, f"Growth factor {growth_factor:.2f} at k={k_val} is not exponential"
