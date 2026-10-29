"""Unit and integration tests for veridyn.challenge.generator."""

import pytest

from veridyn.challenge.generator import (
    Challenge,
    GenerationError,
    LEVEL_CONFIGS,
    generate_challenge,
    get_rules_for_level,
    validate_rule_admission,
)
from veridyn.challenge.hypotheses import build_hypothesis_library
from veridyn.core.dfa import DFA, subset_construction
from veridyn.core.minimize import dfa_signature, minimize
from veridyn.core.nfa import thompson
from veridyn.core.regex_parser import parse


# ==============================================================================
# 1. Deterministic Seed Reproducibility
# ==============================================================================

@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_challenge_seed_reproducibility(level: int) -> None:
    """Verify that identical seeds produce identical Challenge instances."""
    c1 = generate_challenge(level=level, seed=12345)
    c2 = generate_challenge(level=level, seed=12345)

    assert c1.rule_name == c2.rule_name
    assert c1.dfa_signature == c2.dfa_signature
    assert c1.positive_examples == c2.positive_examples
    assert c1.negative_examples == c2.negative_examples
    assert c1.test_strings == c2.test_strings
    assert c1.certificate.is_certified == c2.certificate.is_certified
    assert c1.certificate.witness_map == c2.certificate.witness_map


# ==============================================================================
# 2. Each Level Yields 50 Distinct Certified Challenges
# ==============================================================================

@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_each_level_yields_50_distinct_certified_challenges(level: int) -> None:
    """Verify that each difficulty level can generate 50 distinct certified challenges within a session."""
    session_signatures: set[str] = set()
    config = LEVEL_CONFIGS[level]

    for i in range(50):
        # Generate with distinct seeds
        challenge = generate_challenge(
            level=level,
            seed=i * 1000 + 7,
            session_signatures=session_signatures,
            max_retries=100,
        )

        assert challenge.level == level
        assert challenge.certificate.is_certified is True
        assert len(challenge.positive_examples) == 3
        assert len(challenge.negative_examples) == 3
        assert len(challenge.test_strings) == 6
        assert len(challenge.dfa.states) <= config.max_states

    # Verify that all 50 challenges possess distinct minimal DFA signatures
    assert len(session_signatures) == 50, (
        f"Level {level} produced {len(session_signatures)} distinct signatures, expected 50."
    )


# ==============================================================================
# 3. Admission Checks & Rejection Reasons
# ==============================================================================

def test_admission_checks_and_rejection_reasons() -> None:
    """Verify each rejection branch of the admission check pipeline."""
    H = build_hypothesis_library()

    # 1. Reject empty language
    empty_dfa = DFA(
        states=(0,),
        alphabet=frozenset({"C", "T", "S"}),
        delta={(0, "C"): 0, (0, "T"): 0, (0, "S"): 0},
        start=0,
        accepting=frozenset(),
        dead_state=0,
    )
    admissible, reason = validate_rule_admission(empty_dfa, H, max_states=10)
    assert admissible is False
    assert reason == "Language is empty"

    # 2. Reject universal language (Sigma*)
    universal_dfa = DFA(
        states=(0, 1),
        alphabet=frozenset({"C", "T", "S"}),
        delta={
            (0, "C"): 0, (0, "T"): 0, (0, "S"): 0,
            (1, "C"): 1, (1, "T"): 1, (1, "S"): 1,
        },
        start=0,
        accepting=frozenset({0}),
        dead_state=1,
    )
    admissible, reason = validate_rule_admission(universal_dfa, H, max_states=10)
    assert admissible is False
    assert reason == "Language is universal (Sigma*)"

    # 3. Reject rule in H
    h_member = H[0]
    admissible, reason = validate_rule_admission(h_member.dfa, H, max_states=10)
    assert admissible is False
    assert reason == "Rule is equivalent to a member of H"

    # 4. Reject state count exceeding level cap
    valid_rules = get_rules_for_level(level=2)
    sample_rule = valid_rules[0]
    admissible, reason = validate_rule_admission(sample_rule.dfa, H, max_states=len(sample_rule.dfa.states) - 1)
    assert admissible is False
    assert "exceeding level cap" in (reason or "")

    # 5. Reject duplicate DFA signature in session
    sig = dfa_signature(sample_rule.dfa)
    session_sigs = {sig}
    admissible, reason = validate_rule_admission(sample_rule.dfa, H, max_states=20, session_signatures=session_sigs)
    assert admissible is False
    assert "already issued in this session" in (reason or "")

    # 6. Valid rule passes admission
    admissible, reason = validate_rule_admission(sample_rule.dfa, H, max_states=20, session_signatures=set())
    assert admissible is True
    assert reason is None


def test_generation_error_raised_when_budget_exhausted() -> None:
    """Verify that GenerationError is raised when max_retries is insufficient."""
    # Attempt to generate level 1 with max_retries=0
    with pytest.raises(GenerationError) as exc_info:
        generate_challenge(level=1, seed=42, max_retries=0)
    assert "Failed to generate an admissible challenge" in str(exc_info.value)
