"""Unit and property tests for veridyn.core.minimize."""

import itertools
import pytest
from hypothesis import given, settings, strategies as st

from veridyn.core.dfa import (
    DFA,
    dfa_accepts,
    subset_construction,
)
from veridyn.core.minimize import (
    canonicalize,
    dfa_signature,
    is_minimal,
    minimize,
    remove_unreachable,
)
from veridyn.core.nfa import thompson
from veridyn.core.regex_parser import (
    ASTNode,
    Concat,
    Plus,
    Question,
    Repeat,
    Star,
    Symbol,
    Union,
    parse,
    to_string,
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
# Test Corpus: 20+ Diverse Regular Expressions
# ==============================================================================

MINIMIZE_TEST_CORPUS = [
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
    "(C|CC)T",
    "C{2,}",
    "(CC)*",
]


# ==============================================================================
# 1. Signature & Data Identity on Equivalent Expressions: C{1,2}T and (C|CC)T
# ==============================================================================

def test_c12t_and_c_or_cc_t_identical_signature_and_data() -> None:
    """Verify that equivalent regular expressions yield byte-for-byte identical canonical minimal DFAs."""
    dfa1 = minimize(subset_construction(thompson(parse("C{1,2}T"))))
    dfa2 = minimize(subset_construction(thompson(parse("(C|CC)T"))))

    sig1 = dfa_signature(dfa1)
    sig2 = dfa_signature(dfa2)

    # 1. Signatures must match
    assert sig1 == sig2
    # 2. Python dataclass instances must be structurally equal
    assert dfa1 == dfa2
    # 3. Transitions, states, and accepting sets must match
    assert dfa1.delta == dfa2.delta
    assert dfa1.states == dfa2.states
    assert dfa1.accepting == dfa2.accepting
    assert dfa1.start == dfa2.start
    assert dfa1.dead_state == dfa2.dead_state


# ==============================================================================
# 2. Idempotence: minimize(minimize(DFA)) == minimize(DFA)
# ==============================================================================

@pytest.mark.parametrize("regex_str", MINIMIZE_TEST_CORPUS)
def test_minimize_is_idempotent(regex_str: str) -> None:
    """Verify that minimizing an already minimal DFA is strictly an identity operation."""
    dfa = subset_construction(thompson(parse(regex_str)))
    dfa_min1 = minimize(dfa)
    dfa_min2 = minimize(dfa_min1)

    assert dfa_min1 == dfa_min2
    assert dfa_signature(dfa_min1) == dfa_signature(dfa_min2)


# ==============================================================================
# 3. Language Preservation up to Length 8 (Exhaustive 9,841 strings)
# ==============================================================================

@pytest.mark.parametrize("regex_str", MINIMIZE_TEST_CORPUS)
def test_minimize_preserves_language_exhaustive(
    regex_str: str, all_strings_up_to_8: list[str]
) -> None:
    """Verify that minimization preserves language membership on all 9,841 strings."""
    dfa = subset_construction(thompson(parse(regex_str)))
    dfa_min = minimize(dfa)

    mismatches: list[str] = []
    for s in all_strings_up_to_8:
        res_orig = dfa_accepts(dfa, s)
        res_min = dfa_accepts(dfa_min, s)
        if res_orig != res_min:
            mismatches.append(f"string='{s}': orig={res_orig}, min={res_min}")
            if len(mismatches) >= 5:
                break

    assert not mismatches, f"Minimization altered language for '{regex_str}': {mismatches}"


# ==============================================================================
# 4. Table-Filling Algorithm Confirms Minimality
# ==============================================================================

@pytest.mark.parametrize("regex_str", MINIMIZE_TEST_CORPUS)
def test_table_filling_confirms_minimality(regex_str: str) -> None:
    """Verify that independent table-filling algorithm certifies every minimized DFA as minimal."""
    dfa = subset_construction(thompson(parse(regex_str)))
    dfa_min = minimize(dfa)

    assert is_minimal(dfa_min) is True


def test_table_filling_detects_non_minimal_dfa() -> None:
    """Verify that table-filling correctly detects an intentionally non-minimal DFA with redundant states."""
    # Build a DFA for 'C' with duplicate redundant start states:
    # State 0 (start): 'C' -> 2, others -> 3
    # State 1 (duplicate equivalent of 0): 'C' -> 2, others -> 3
    # State 2 (accepting): all -> 3
    # State 3 (dead): all -> 3
    delta = {
        (0, "C"): 2, (0, "T"): 3, (0, "S"): 3,
        (1, "C"): 2, (1, "T"): 3, (1, "S"): 3,
        (2, "C"): 3, (2, "T"): 3, (2, "S"): 3,
        (3, "C"): 3, (3, "T"): 3, (3, "S"): 3,
    }
    non_minimal_dfa = DFA(
        states=frozenset({0, 1, 2, 3}),
        alphabet=frozenset({"C", "T", "S"}),
        delta=delta,
        start=0,
        accepting=frozenset({2}),
        dead_state=3,
    )

    # State 1 is unreachable from start 0
    # If state 0 transitions to 1 on 'T' instead of 3, both 0 and 1 are reachable and equivalent
    delta_reachable_dup = dict(delta)
    delta_reachable_dup[(0, "T")] = 1  # 1 is now reachable
    delta_reachable_dup[(1, "T")] = 1  # self-loop
    delta_reachable_dup[(1, "S")] = 3
    # But now 1 behaves differently on T? No, let's keep exact equivalence:
    # Let state 0 and state 1 be completely equivalent reachable states:
    # Start -> 0 or 1:
    # Start state 0: 'C' -> 1, 'T' -> 2, 'S' -> 4
    # State 1 and State 2 are both accepting and both go to dead state on all inputs:
    # delta(1, a) == 4, delta(2, a) == 4. Both are accepting!
    delta_dup = {
        (0, "C"): 1, (0, "T"): 2, (0, "S"): 3,
        (1, "C"): 3, (1, "T"): 3, (1, "S"): 3,  # accepting state 1
        (2, "C"): 3, (2, "T"): 3, (2, "S"): 3,  # accepting state 2 (identical behavior to 1!)
        (3, "C"): 3, (3, "T"): 3, (3, "S"): 3,  # dead state
    }
    reachable_dup_dfa = DFA(
        states=frozenset({0, 1, 2, 3}),
        alphabet=frozenset({"C", "T", "S"}),
        delta=delta_dup,
        start=0,
        accepting=frozenset({1, 2}),
        dead_state=3,
    )

    # States 1 and 2 are indistinguishable: both are accepting and both transition to dead state 3 on all symbols
    assert is_minimal(reachable_dup_dfa) is False

    # After minimization, states 1 and 2 must be merged:
    minimized_dup = minimize(reachable_dup_dfa)
    assert len(minimized_dup.states) == 3  # Start, Merged Accepting, Dead
    assert is_minimal(minimized_dup) is True


# ==============================================================================
# 5. Hypothesis Property-Based Random Regex Tests
# ==============================================================================

def symbol_strategy() -> st.SearchStrategy[ASTNode]:
    return st.sampled_from(["C", "T", "S"]).map(Symbol)


def ast_strategy() -> st.SearchStrategy[ASTNode]:
    def extend_tree(children: st.SearchStrategy[ASTNode]) -> st.SearchStrategy[ASTNode]:
        return st.one_of(
            st.builds(Star, children),
            st.builds(Plus, children),
            st.builds(Question, children),
            st.builds(
                lambda child, m: Repeat(child, m, m),
                children,
                st.integers(min_value=0, max_value=3),
            ),
            st.builds(Concat, children, children),
            st.builds(Union, children, children),
        )

    return st.recursive(symbol_strategy(), extend_tree, max_leaves=5)


@given(ast_strategy())
@settings(max_examples=50)
def test_hypothesis_minimization_properties(ast: ASTNode) -> None:
    """Property test: Minimization produces minimal, idempotent DFAs preserving language."""
    rendered = to_string(ast)
    if len(rendered) <= 40:
        nfa = thompson(ast)
        dfa = subset_construction(nfa)
        min_dfa = minimize(dfa)

        # 1. Result must be minimal by table-filling oracle
        assert is_minimal(min_dfa) is True

        # 2. Minimization must be idempotent
        assert minimize(min_dfa) == min_dfa
        assert dfa_signature(minimize(min_dfa)) == dfa_signature(min_dfa)

        # 3. Minimal state count cannot exceed original state count
        assert len(min_dfa.states) <= len(dfa.states)

        # 4. Check consistency on sample strings
        sample_words = ["", "C", "T", "S", "CT", "TT", "CST", "CCC"]
        for w in sample_words:
            assert dfa_accepts(dfa, w) == dfa_accepts(min_dfa, w)
