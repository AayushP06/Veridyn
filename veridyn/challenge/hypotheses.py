"""Hypothesis library H construction and catalog.

TOC Concept: Hypothesis Spaces in Inductive Inference, Candidate Language Primitives,
Canonical Minimal DFA Representation, and Finite Hypothesis Classes.
"""

from __future__ import annotations

from collections.abc import Container
from dataclasses import dataclass
from functools import lru_cache

from veridyn.core.dfa import DFA, subset_construction
from veridyn.core.minimize import minimize
from veridyn.core.nfa import thompson
from veridyn.core.regex_parser import DEFAULT_ALPHABET, parse


@dataclass(frozen=True)
class Hypothesis:
    """A candidate regular rule in the hypothesis library H.

    Attributes:
        name: Unique programmatic identifier for the hypothesis.
        dfa: Canonical minimal DFA recognizing the hypothesis language.
        description: Human-readable explanation of the rule.
        regex_str: Source regular expression defining the language.
    """
    name: str
    dfa: DFA
    description: str
    regex_str: str


def _build_hypothesis(name: str, regex_str: str, desc: str, alphabet: Container[str]) -> Hypothesis:
    """Build a canonical minimal DFA hypothesis from a regex string."""
    ast = parse(regex_str, alphabet=alphabet)
    nfa = thompson(ast, alphabet=alphabet)
    dfa_raw = subset_construction(nfa)
    dfa_min = minimize(dfa_raw)
    return Hypothesis(name=name, dfa=dfa_min, description=desc, regex_str=regex_str)


@lru_cache(maxsize=4)
def build_hypothesis_library(alphabet: frozenset[str] | None = None) -> list[Hypothesis]:
    """Construct the complete hypothesis library H of at least 30 candidate rules.

    All members are built through the standard pipeline (parse -> thompson ->
    subset_construction -> minimize -> canonicalize) and are data-driven.

    Args:
        alphabet: Allowed terminal alphabet. Defaults to {'C', 'T', 'S'}.

    Returns:
        List of at least 30 canonical, minimized Hypothesis instances.
    """
    alpha = alphabet if alphabet is not None else DEFAULT_ALPHABET
    H: list[Hypothesis] = []

    # 1. Prefix: starts with X (3)
    H.append(_build_hypothesis("starts_with_C", "C(C|T|S)*", "Starts with symbol C", alpha))
    H.append(_build_hypothesis("starts_with_T", "T(C|T|S)*", "Starts with symbol T", alpha))
    H.append(_build_hypothesis("starts_with_S", "S(C|T|S)*", "Starts with symbol S", alpha))

    # 2. Suffix: ends with X (3)
    H.append(_build_hypothesis("ends_with_C", "(C|T|S)*C", "Ends with symbol C", alpha))
    H.append(_build_hypothesis("ends_with_T", "(C|T|S)*T", "Ends with symbol T", alpha))
    H.append(_build_hypothesis("ends_with_S", "(C|T|S)*S", "Ends with symbol S", alpha))

    # 3. Substring: contains X (3)
    H.append(_build_hypothesis("contains_C", "(C|T|S)*C(C|T|S)*", "Contains symbol C", alpha))
    H.append(_build_hypothesis("contains_T", "(C|T|S)*T(C|T|S)*", "Contains symbol T", alpha))
    H.append(_build_hypothesis("contains_S", "(C|T|S)*S(C|T|S)*", "Contains symbol S", alpha))

    # 4. Substring: contains double symbol XX (3)
    H.append(_build_hypothesis("contains_CC", "(C|T|S)*CC(C|T|S)*", "Contains consecutive substring CC", alpha))
    H.append(_build_hypothesis("contains_TT", "(C|T|S)*TT(C|T|S)*", "Contains consecutive substring TT", alpha))
    H.append(_build_hypothesis("contains_SS", "(C|T|S)*SS(C|T|S)*", "Contains consecutive substring SS", alpha))

    # 5. Substring avoidance: no double XX (3)
    H.append(_build_hypothesis("no_CC", "(T|S|CT|CS)*(C?)", "Does not contain substring CC", alpha))
    H.append(_build_hypothesis("no_TT", "(C|S|TC|TS)*(T?)", "Does not contain substring TT", alpha))
    H.append(_build_hypothesis("no_SS", "(C|T|SC|ST)*(S?)", "Does not contain substring SS", alpha))

    # 6. Count parity: even/odd count of X (6)
    H.append(_build_hypothesis("count_C_even", "(T|S|C(T|S)*C)*", "Contains an even number of C's", alpha))
    H.append(_build_hypothesis("count_C_odd", "(T|S)*C(T|S|C(T|S)*C)*", "Contains an odd number of C's", alpha))
    H.append(_build_hypothesis("count_T_even", "(C|S|T(C|S)*T)*", "Contains an even number of T's", alpha))
    H.append(_build_hypothesis("count_T_odd", "(C|S)*T(C|S|T(C|S)*T)*", "Contains an odd number of T's", alpha))
    H.append(_build_hypothesis("count_S_even", "(C|T|S(C|T)*S)*", "Contains an even number of S's", alpha))
    H.append(_build_hypothesis("count_S_odd", "(C|T)*S(C|T|S(C|T)*S)*", "Contains an odd number of S's", alpha))

    # 7. Modular count: count of X mod 3 == 0 (3)
    H.append(_build_hypothesis("count_C_mod3_0", "(T|S|C(T|S)*C(T|S)*C)*", "Count of symbol C is a multiple of 3", alpha))
    H.append(_build_hypothesis("count_T_mod3_0", "(C|S|T(C|S)*T(C|S)*T)*", "Count of symbol T is a multiple of 3", alpha))
    H.append(_build_hypothesis("count_S_mod3_0", "(C|T|S(C|T)*S(C|T)*S)*", "Count of symbol S is a multiple of 3", alpha))

    # 8. Length parity: even / odd total length (2)
    H.append(_build_hypothesis("length_even", "((C|T|S){2})*", "Total string length is even", alpha))
    H.append(_build_hypothesis("length_odd", "(C|T|S)((C|T|S){2})*", "Total string length is odd", alpha))

    # 9. Length bounds: length <= k (3)
    H.append(_build_hypothesis("length_le_2", "(C|T|S){0,2}", "String length is at most 2", alpha))
    H.append(_build_hypothesis("length_le_3", "(C|T|S){0,3}", "String length is at most 3", alpha))
    H.append(_build_hypothesis("length_le_4", "(C|T|S){0,4}", "String length is at most 4", alpha))

    # 10. Length bounds: length >= k (3)
    H.append(_build_hypothesis("length_ge_2", "(C|T|S){2,}", "String length is at least 2", alpha))
    H.append(_build_hypothesis("length_ge_3", "(C|T|S){3,}", "String length is at least 3", alpha))
    H.append(_build_hypothesis("length_ge_4", "(C|T|S){4,}", "String length is at least 4", alpha))

    assert len(H) >= 30, f"Hypothesis library must contain at least 30 members, got {len(H)}"
    return H


__all__ = [
    "Hypothesis",
    "build_hypothesis_library",
]
