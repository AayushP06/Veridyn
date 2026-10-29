"""Tests for inductive certification, H-guesser hardness, and test set construction."""

import random
import pytest

from veridyn.challenge.certify import (
    Certificate,
    build_tests,
    certify,
    consistent,
)
from veridyn.challenge.hypotheses import Hypothesis, build_hypothesis_library
from veridyn.challenge.rules import (
    HiddenRule,
    generate_candidate_rules,
    rule_not_in_H,
)
from veridyn.core.analyze import sample_strings
from veridyn.core.dfa import dfa_accepts


# ==============================================================================
# Fixtures: Shared Hypothesis Library & Pre-generated Candidate Rules
# ==============================================================================

@pytest.fixture(scope="session")
def hypothesis_library() -> list[Hypothesis]:
    H = build_hypothesis_library()
    assert len(H) >= 30, f"Library H must have at least 30 members, got {len(H)}"
    return H


@pytest.fixture(scope="session")
def candidate_rules(hypothesis_library: list[Hypothesis]) -> list[HiddenRule]:
    rules = generate_candidate_rules(hypothesis_library, limit=20)
    assert len(rules) >= 10, f"Must have at least 10 candidate rules, got {len(rules)}"
    return rules


# ==============================================================================
# 1. 100 Seeded Challenges & Absolute H-Guesser Defeat
# ==============================================================================

def test_100_certified_challenges_and_zero_h_guesser_pass_rate(
    hypothesis_library: list[Hypothesis],
    candidate_rules: list[HiddenRule],
) -> None:
    """Core Theoretical Invariant Test:

    For 100 seeded random challenges:
      1. Every accepted challenge carries a valid Certificate.
      2. Balance is strictly 3 valid / 3 invalid for k=6.
      3. Length caps are respected: examples in [2, 6], tests <= 8.
      4. An adversarial H-guesser picking ANY consistent hypothesis in H
         fails on at least one test string in EVERY challenge.
      5. The H-guesser pass rate on certified challenges is EXACTLY 0.0%.
    """
    H = hypothesis_library
    rules = candidate_rules

    num_target_challenges = 100
    h_guesser_pass_count = 0
    total_consistent_hypotheses_evaluated = 0

    base_seed = 42
    rng = random.Random(base_seed)

    challenges_verified = 0
    attempts = 0

    while challenges_verified < num_target_challenges:
        attempts += 1
        rule = rng.choice(rules)

        # 1. Sample 3 positive and 3 negative examples with length in [2, 6]
        try:
            pos_ex = sample_strings(rule.dfa, accepted=True, length_range=(2, 6), n=3, rng=rng)
            neg_ex = sample_strings(rule.dfa, accepted=False, length_range=(2, 6), n=3, rng=rng)
        except ValueError:
            continue

        examples = (pos_ex, neg_ex)

        # 2. Build certified balanced test set of k=6 strings
        tests = build_tests(rule.dfa, examples, H, k=6, rng=rng)
        if tests is None:
            # Resample if certificate required more than k or padding failed
            continue

        # 3. Verify Certificate
        cert = certify(rule.dfa, examples, tests, H)
        assert cert.is_certified is True, f"Challenge failed certification: {cert.failure_reason}"
        assert cert.failure_reason is None

        # 4. Check balance and length bounds
        truth_pos_count = sum(1 for t in tests if dfa_accepts(rule.dfa, t))
        truth_neg_count = sum(1 for t in tests if not dfa_accepts(rule.dfa, t))
        assert truth_pos_count == 3, f"Expected 3 positive test strings, got {truth_pos_count}"
        assert truth_neg_count == 3, f"Expected 3 negative test strings, got {truth_neg_count}"
        assert len(tests) == 6

        assert all(2 <= len(s) <= 6 for s in pos_ex + neg_ex), "Examples violated length bounds [2, 6]"
        assert all(len(t) <= 8 for t in tests), "Test strings violated length cap 8"

        # 5. Evaluate the Adversarial H-Guesser
        # The guesser knows all shown examples and considers all hypotheses in H that fit (E+, E-)
        cons_h_list = [h for h in H if consistent(h.dfa, examples)]

        # Ground truth labels on test strings
        truth_labels = [dfa_accepts(rule.dfa, t) for t in tests]

        for h in cons_h_list:
            total_consistent_hypotheses_evaluated += 1
            # Guesser submits classifications according to h
            guess_labels = [dfa_accepts(h.dfa, t) for t in tests]

            # The guesser passes iff all classifications match truth
            if guess_labels == truth_labels:
                h_guesser_pass_count += 1

            # Assert this hypothesis failed on at least one test string
            assert guess_labels != truth_labels, (
                f"Security Failure: Consistent hypothesis '{h.name}' passed all tests! "
                f"Witness was supposed to be '{cert.witness_map.get(h.name)}'"
            )

        challenges_verified += 1

    # Final hardness assertion: Pass rate must be strictly 0.0%
    h_guesser_pass_rate = h_guesser_pass_count / max(1, total_consistent_hypotheses_evaluated)
    print(
        f"\n[Certification Hardness] Verified {challenges_verified} challenges. "
        f"Evaluated {total_consistent_hypotheses_evaluated} consistent hypotheses. "
        f"H-guesser pass rate: {h_guesser_pass_rate:.4%}"
    )
    assert h_guesser_pass_count == 0
    assert h_guesser_pass_rate == 0.0


# ==============================================================================
# 2. Sabotaged Test Set Fails Certification
# ==============================================================================

def test_sabotaged_test_set_fails_certification(
    hypothesis_library: list[Hypothesis],
    candidate_rules: list[HiddenRule],
) -> None:
    """Verify that omitting distinguishing witness strings causes certify() to fail."""
    H = hypothesis_library
    rule = candidate_rules[0]
    rng = random.Random(101)

    # Find a challenge where at least one hypothesis in H is consistent
    while True:
        pos_ex = sample_strings(rule.dfa, accepted=True, length_range=(2, 6), n=3, rng=rng)
        neg_ex = sample_strings(rule.dfa, accepted=False, length_range=(2, 6), n=3, rng=rng)
        examples = (pos_ex, neg_ex)
        tests = build_tests(rule.dfa, examples, H, k=6, rng=rng)
        if tests is not None:
            cons_h = [h for h in H if consistent(h.dfa, examples)]
            if len(cons_h) > 0:
                break

    # The legitimate test set passes certification
    cert_valid = certify(rule.dfa, examples, tests, H)
    assert cert_valid.is_certified is True

    # Now sabotage the test set:
    # Instead of the real tests, provide test strings that agree with a consistent hypothesis h!
    target_h = cons_h[0]

    # Sample tests only from strings where target_h and truth agree
    # Or simply provide strings where target_h agrees with truth
    sabotaged_tests: list[str] = []
    # If we replace tests with strings where target_h and truth agree:
    # Any string in examples satisfies target_h(s) == truth(s)
    # So repeating examples as test strings ensures target_h agrees with truth on all tests!
    sabotaged_tests = (pos_ex + neg_ex)[:6]

    cert_sabotaged = certify(rule.dfa, examples, sabotaged_tests, H)
    assert cert_sabotaged.is_certified is False
    assert cert_sabotaged.failure_reason is not None
    assert target_h.name in cert_sabotaged.failure_reason


# ==============================================================================
# 3. Rule Separation from Hypothesis Library
# ==============================================================================

def test_all_hidden_rules_not_in_H(
    hypothesis_library: list[Hypothesis],
    candidate_rules: list[HiddenRule],
) -> None:
    """Verify that every synthesized hidden rule is strictly separated from H."""
    for rule in candidate_rules:
        assert rule_not_in_H(rule.dfa, hypothesis_library) is True
        for h in hypothesis_library:
            from veridyn.core.boolean_ops import equivalent
            assert not equivalent(rule.dfa, h.dfa), f"Rule '{rule.name}' is equivalent to hypothesis '{h.name}'"
