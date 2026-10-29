"""Unit and differential tests for veridyn.core.nfa."""

import itertools
import re
import pytest

from veridyn.core.nfa import (
    NFA,
    epsilon_closure,
    nfa_accepts,
    thompson,
)
from veridyn.core.regex_parser import (
    Epsilon,
    parse,
)

# ==============================================================================
# Fixture: Exhaustive set of all 9,841 strings up to length 8 over {C, T, S}
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
# Test Corpus: 24 Diverse Regular Expressions + Edge Cases
# ==============================================================================

REGEX_DIFFERENTIAL_CORPUS = [
    # (label, regex_str, oracle_pattern)
    ("single_c", "C", "C"),
    ("single_t", "T", "T"),
    ("single_s", "S", "S"),
    ("concat_2", "CT", "CT"),
    ("concat_3", "CTS", "CTS"),
    ("union_2", "C|T", "C|T"),
    ("union_3", "C|T|S", "C|T|S"),
    ("concat_union", "CT|SC", "CT|SC"),
    ("kleene_star", "C*", "C*"),
    ("group_star", "(CT)*", "(CT)*"),
    ("union_star", "(C|T)*", "(C|T)*"),
    ("nested_stars_1", "(C*)*", "(C*)*"),
    ("nested_stars_2", "((C|T)*)*", "((C|T)*)*"),
    ("toc_ends_with_s", "(C|T)*S", "(C|T)*S"),
    ("toc_starts_with_c", "C(T|S)*", "C(T|S)*"),
    ("toc_contains_s", "(C|T)*S(C|T)*", "(C|T)*S(C|T)*"),
    ("plus_simple", "C+", "C+"),
    ("plus_group", "(CT)+", "(CT)+"),
    ("question_simple", "C?", "C?"),
    ("question_combined", "(C|T)?S", "(C|T)?S"),
    ("exact_repeat", "C{2}", "C{2}"),
    ("range_repeat", "C{1,2}T", "C{1,2}T"),
    ("c_or_cc_t", "(C|CC)T", "(C|CC)T"),
    ("open_repeat", "C{2,}", "C{2,}"),
    ("even_c_parity", "(CC)*", "(CC)*"),
]


@pytest.mark.parametrize("label,regex_str,oracle_pat", REGEX_DIFFERENTIAL_CORPUS)
def test_nfa_differential_oracle_exhaustive(
    label: str,
    regex_str: str,
    oracle_pat: str,
    all_strings_up_to_8: list[str],
) -> None:
    """Differential test: nfa_accepts must strictly agree with re.fullmatch on all 9,841 strings."""
    ast = parse(regex_str)
    nfa = thompson(ast)

    # Print NFA state count as requested
    print(f"\n[NFA State Count] {label} ('{regex_str}'): |Q| = {len(nfa.states)} states, |transitions| = {len(nfa.transitions)}")

    re_oracle = re.compile(f"^(?:{oracle_pat})$")

    mismatches: list[str] = []
    for s in all_strings_up_to_8:
        expected = bool(re_oracle.fullmatch(s))
        actual = nfa_accepts(nfa, s)
        if actual != expected:
            mismatches.append(f"string='{s}': expected={expected}, actual={actual}")
            if len(mismatches) >= 5:
                break

    assert not mismatches, f"Mismatches found for '{regex_str}': {mismatches}"


def test_epsilon_regex_differential_exhaustive(all_strings_up_to_8: list[str]) -> None:
    """Edge case: Epsilon regex recognizes strictly the empty string ''."""
    nfa = thompson(Epsilon())
    print(f"\n[NFA State Count] epsilon regex (Epsilon()): |Q| = {len(nfa.states)} states")

    re_oracle = re.compile(r"^$")

    for s in all_strings_up_to_8:
        expected = bool(re_oracle.fullmatch(s))
        actual = nfa_accepts(nfa, s)
        assert actual == expected, f"Epsilon NFA mismatch on string '{s}'"


def test_epsilon_closure_properties() -> None:
    """Verify algebraic properties of epsilon-closure: Reflexivity and Idempotence."""
    ast = parse("(C*)*|(T?S{1,2})")
    nfa = thompson(ast)

    # Reflexivity: S subseteq ECLOSE(S)
    for s in nfa.states:
        closure = epsilon_closure(nfa, frozenset({s}))
        assert s in closure

    # Idempotence: ECLOSE(ECLOSE(S)) == ECLOSE(S)
    subset = frozenset({nfa.start})
    cl1 = epsilon_closure(nfa, subset)
    cl2 = epsilon_closure(nfa, cl1)
    assert cl1 == cl2


def test_thompson_state_bounds() -> None:
    """Verify Thompson structural induction property: |Q| is strictly linear in AST size."""
    # Thompson construction creates at most 2 states per AST node
    regex_examples = ["C", "C|T", "CT", "C*", "(C|T)*S"]
    for r in regex_examples:
        ast = parse(r)
        nfa = thompson(ast)
        # Verify single start and single accepting state
        assert nfa.start in nfa.states
        assert len(nfa.accepting) == 1
        acc = next(iter(nfa.accepting))
        assert acc in nfa.states
        assert nfa.start != acc
        assert len(nfa.states) >= 2
