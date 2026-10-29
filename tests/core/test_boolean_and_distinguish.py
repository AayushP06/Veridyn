"""Unit and property tests for veridyn.core.boolean_ops and veridyn.core.distinguish."""

import itertools
import pytest

from veridyn.core.boolean_ops import (
    complement,
    difference,
    equivalent,
    intersection,
    is_empty,
    product,
    symmetric_difference,
    union,
)
from veridyn.core.dfa import DFA, dfa_accepts, subset_construction
from veridyn.core.distinguish import (
    distinguishing_strings,
    shortest_distinguishing_string,
)
from veridyn.core.minimize import minimize
from veridyn.core.nfa import thompson
from veridyn.core.regex_parser import parse

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


def dfa_from_regex(regex_str: str, alphabet: tuple[str, ...] = ("C", "T", "S")) -> DFA:
    """Helper to construct a DFA from a regular expression."""
    ast = parse(regex_str, alphabet=alphabet)
    nfa = thompson(ast, alphabet=alphabet)
    return subset_construction(nfa)


# ==============================================================================
# 1. Worked Example: Truth ("no TT") vs. Decoy ("no TT at start or end")
# ==============================================================================

def test_worked_example_no_tt_vs_decoy() -> None:
    """TOC Theorem & Worked Example:

    Alphabet: {C, T}
    Truth: Regular language avoiding substring 'TT' anywhere.
           Regex: (C|TC)*T?
    Decoy: Regular language avoiding 'TT' only at the start or end.
           Complement of (TT(C|T)* | (C|T)*TT).

    Theorem: The shortest distinguishing string between Truth and Decoy is EXACTLY 'CTTC'.
    """
    alpha = ("C", "T")

    # 1. Truth DFA: no TT anywhere
    truth_dfa = dfa_from_regex("(C|TC)*T?", alphabet=alpha)

    # 2. Decoy DFA: no TT at start or end
    starts_with_tt = dfa_from_regex("TT(C|T)*", alphabet=alpha)
    ends_with_tt = dfa_from_regex("(C|T)*TT", alphabet=alpha)
    has_tt_at_ends = union(starts_with_tt, ends_with_tt)
    decoy_dfa = complement(has_tt_at_ends)

    # 3. Find shortest distinguishing string
    shortest = shortest_distinguishing_string(truth_dfa, decoy_dfa)

    # Assert that the shortest distinguishing string is strictly 'CTTC'
    assert shortest == "CTTC", f"Expected shortest distinguishing string 'CTTC', but got '{shortest}'"

    # Verify verdicts on both DFAs
    assert dfa_accepts(truth_dfa, "CTTC") is False, "Truth must reject 'CTTC' because it contains 'TT'"
    assert dfa_accepts(decoy_dfa, "CTTC") is True, "Decoy must accept 'CTTC' because TT is not at the start or end"

    # Verify that all shorter strings in {C, T}* give IDENTICAL verdicts
    for length in range(4):
        for combo in itertools.product(alpha, repeat=length):
            w = "".join(combo)
            assert dfa_accepts(truth_dfa, w) == dfa_accepts(decoy_dfa, w), (
                f"Unexpected distinction on shorter string '{w}'"
            )


# ==============================================================================
# 2. De Morgan's Laws (Exhaustive verification on 9,841 strings)
# ==============================================================================

DE_MORGAN_PAIRS = [
    ("C*", "T*"),
    ("(C|T)*S", "C(T|S)*"),
    ("C+", "C?"),
    ("(CT)*", "(C|T)*S"),
]


@pytest.mark.parametrize("r1,r2", DE_MORGAN_PAIRS)
def test_de_morgan_identities_exhaustive(
    r1: str, r2: str, all_strings_up_to_8: list[str]
) -> None:
    """Verify De Morgan's Laws:

    1. not (L1 or L2) == (not L1) and (not L2)
    2. not (L1 and L2) == (not L1) or (not L2)
    Exhaustively evaluated on all 9,841 strings up to length 8.
    """
    d1 = dfa_from_regex(r1)
    d2 = dfa_from_regex(r2)

    # Law 1: not (L1 or L2) == (not L1) and (not L2)
    lhs1 = complement(union(d1, d2))
    rhs1 = intersection(complement(d1), complement(d2))

    assert equivalent(lhs1, rhs1) is True

    # Law 2: not (L1 and L2) == (not L1) or (not L2)
    lhs2 = complement(intersection(d1, d2))
    rhs2 = union(complement(d1), complement(d2))

    assert equivalent(lhs2, rhs2) is True

    # Check exhaustive string acceptance
    for s in all_strings_up_to_8:
        assert dfa_accepts(lhs1, s) == dfa_accepts(rhs1, s)
        assert dfa_accepts(lhs2, s) == dfa_accepts(rhs2, s)


# ==============================================================================
# 3. Boolean Closure Properties against Expected Regular Languages
# ==============================================================================

def test_closure_results_against_expected_languages() -> None:
    """Verify intersection, difference, and union match expected regular languages."""
    # Intersection: L(C*) & L(C+) == L(C+)
    d_cstar = dfa_from_regex("C*")
    d_cplus = dfa_from_regex("C+")
    d_inter = intersection(d_cstar, d_cplus)
    assert equivalent(d_inter, d_cplus) is True

    # Difference: L(C*) \ L(C+) == L(epsilon) == L(C{0})
    d_diff = difference(d_cstar, d_cplus)
    d_eps = dfa_from_regex("C{0}")
    assert equivalent(d_diff, d_eps) is True

    # Self-difference is empty: L(R) \ L(R) == empty_set
    d_empty = difference(d_cstar, d_cstar)
    assert is_empty(d_empty) is True

    # Self-symmetric difference is empty: L(R) (+) L(R) == empty_set
    d_sym_empty = symmetric_difference(d_cstar, d_cstar)
    assert is_empty(d_sym_empty) is True

    # Union with complement is universal: L(R) | L(not R) == Sigma*
    d_univ = union(d_cstar, complement(d_cstar))
    d_sigma_star = dfa_from_regex("(C|T|S)*")
    assert equivalent(d_univ, d_sigma_star) is True


# ==============================================================================
# 4. Equivalent Regexes Return None for Distinguishing Strings
# ==============================================================================

def test_equivalent_regexes_return_none() -> None:
    """Verify that equivalent DFAs produce no distinguishing strings."""
    # C{1,2}T and (C|CC)T recognize the same language
    d1 = dfa_from_regex("C{1,2}T")
    d2 = dfa_from_regex("(C|CC)T")

    assert equivalent(d1, d2) is True
    assert shortest_distinguishing_string(d1, d2) is None
    assert distinguishing_strings(d1, d2, limit=5) == []


# ==============================================================================
# 5. Verification of All Distinguishing Strings by Simulation
# ==============================================================================

@pytest.mark.parametrize(
    "r1,r2",
    [
        ("C*", "T*"),
        ("(C|T)*S", "C(T|S)*"),
        ("C+", "C?"),
        ("CT|SC", "C|T|S"),
        ("C{2}", "C{3}"),
    ],
)
def test_all_distinguishing_strings_verified_by_simulation(r1: str, r2: str) -> None:
    """Verify every string returned by distinguishing_strings is classified differently by both DFAs."""
    d1 = dfa_from_regex(r1)
    d2 = dfa_from_regex(r2)

    witnesses = distinguishing_strings(d1, d2, limit=5)
    assert len(witnesses) > 0, f"Expected distinguishing strings between '{r1}' and '{r2}'"

    for w in witnesses:
        res1 = dfa_accepts(d1, w)
        res2 = dfa_accepts(d2, w)
        assert res1 != res2, f"Witness '{w}' was not distinguishing: d1={res1}, d2={res2}"

    # First witness must match shortest_distinguishing_string
    shortest = shortest_distinguishing_string(d1, d2)
    assert shortest == witnesses[0]
