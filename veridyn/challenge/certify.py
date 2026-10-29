"""Inductive hardness certification and test string generation.

TOC Concept: Formal Certification in Grammatical Inference, Consistency Checking,
Adversarial Witness Extraction, and Balance Invariants.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from veridyn.challenge.hypotheses import Hypothesis
from veridyn.core.analyze import sample_strings
from veridyn.core.dfa import DFA, dfa_accepts
from veridyn.core.distinguish import shortest_distinguishing_string


@dataclass(frozen=True)
class Certificate:
    """Certificate of inductive hardness against hypothesis library H.

    Attributes:
        is_certified: True iff for EVERY consistent hypothesis h in H_cons,
            there exists at least one test string in T where h and truth disagree.
        consistent_hypotheses: Names of all hypotheses in H consistent with shown examples.
        witness_map: Mapping from hypothesis name to the separating test string witness.
        failure_reason: Explanation if certification failed.
    """
    is_certified: bool
    consistent_hypotheses: tuple[str, ...]
    witness_map: dict[str, str]
    failure_reason: str | None = None


def consistent(h_dfa: DFA, examples: tuple[Sequence[str], Sequence[str]]) -> bool:
    """Check if a hypothesis DFA is consistent with shown positive and negative examples.

    TOC Concept:
        Consistency Problem in Grammatical Inference:
        h is consistent with (E+, E-) iff E+ subseteq L(h) and E- cap L(h) == empty_set.

    Args:
        h_dfa: Candidate hypothesis DFA.
        examples: Tuple of (positive_examples, negative_examples).

    Returns:
        True iff h accepts all positive examples and rejects all negative examples.
    """
    pos_examples, neg_examples = examples
    for s in pos_examples:
        if not dfa_accepts(h_dfa, s):
            return False
    for s in neg_examples:
        if dfa_accepts(h_dfa, s):
            return False
    return True


def certify(
    truth: DFA,
    examples: tuple[Sequence[str], Sequence[str]],
    tests: Sequence[str],
    H: Sequence[Hypothesis],
) -> Certificate:
    """Certify that no consistent hypothesis in H can pass the test set.

    Formal Guarantee:
        For every h in H such that consistent(h, examples):
            exists t in tests such that h(t) != truth(t).

    Args:
        truth: Target hidden rule DFA.
        examples: Tuple (E+, E-) of shown examples.
        tests: Proposed sequence of test strings T.
        H: Hypothesis library.

    Returns:
        Certificate containing consistent hypotheses and witness separating strings.
    """
    # 1. Identify all consistent hypotheses in H
    cons_hypotheses: list[Hypothesis] = [
        h for h in H if consistent(h.dfa, examples)
    ]

    witness_map: dict[str, str] = {}

    # 2. For each consistent h, find a test string where h and truth differ
    for h in cons_hypotheses:
        separating_test: str | None = None
        for t in tests:
            truth_label = dfa_accepts(truth, t)
            h_label = dfa_accepts(h.dfa, t)
            if truth_label != h_label:
                separating_test = t
                break

        if separating_test is None:
            # Failure: hypothesis h is consistent with examples AND agrees with truth on all tests!
            return Certificate(
                is_certified=False,
                consistent_hypotheses=tuple(h.name for h in cons_hypotheses),
                witness_map=witness_map,
                failure_reason=(
                    f"Consistent hypothesis '{h.name}' matches truth on all test strings. "
                    "Challenge is uncertified against H."
                ),
            )

        witness_map[h.name] = separating_test

    return Certificate(
        is_certified=True,
        consistent_hypotheses=tuple(h.name for h in cons_hypotheses),
        witness_map=witness_map,
        failure_reason=None,
    )


def build_tests(
    truth: DFA,
    examples: tuple[Sequence[str], Sequence[str]],
    H: Sequence[Hypothesis],
    k: int = 6,
    rng: random.Random | None = None,
) -> list[str] | None:
    """Construct a balanced set of k test strings certifying hardness against H.

    Strategy:
      1. For each consistent h in H, extract the shortest distinguishing string separating
         h from truth (Phase 5 BFS algorithm).
      2. If witnesses exceed the balanced budget (k//2 valid, k//2 invalid) or length caps (> 8),
         fail immediately (return None) to signal the caller to resample examples.
      3. Pad remaining slots uniformly with valid and invalid strings from truth (length 2..8).
      4. Shuffle and verify with certify().

    Args:
        truth: Target hidden rule DFA.
        examples: Tuple of (pos_examples, neg_examples).
        H: Hypothesis library.
        k: Total test strings required (must be even, defaults to 6).
        rng: Seeded random.Random instance.

    Returns:
        List of k balanced test strings, or None if certification within budget fails.
    """
    if rng is None:
        rng = random.Random()

    half_k = k // 2
    pos_examples, neg_examples = examples
    existing_examples = set(pos_examples) | set(neg_examples)

    # 1. Identify consistent hypotheses
    cons_h = [h for h in H if consistent(h.dfa, examples)]

    # 2. Extract shortest distinguishing strings
    pos_witnesses: set[str] = set()
    neg_witnesses: set[str] = set()

    for h in cons_h:
        w = shortest_distinguishing_string(truth, h.dfa)
        if w is None or len(w) > 8:
            # Distinguishing string exceeds length cap 8 or does not exist
            return None

        if dfa_accepts(truth, w):
            pos_witnesses.add(w)
        else:
            neg_witnesses.add(w)

    # 3. Check if witnesses fit within the balanced budget
    if len(pos_witnesses) > half_k or len(neg_witnesses) > half_k:
        return None

    # 4. Pad remaining slots to achieve balanced k/2 valid and k/2 invalid strings
    needed_pos = half_k - len(pos_witnesses)
    needed_neg = half_k - len(neg_witnesses)

    selected_pos: list[str] = sorted(pos_witnesses)
    selected_neg: list[str] = sorted(neg_witnesses)

    used_strings = existing_examples | set(selected_pos) | set(selected_neg)

    if needed_pos > 0:
        try:
            candidates = sample_strings(truth, accepted=True, length_range=(2, 8), n=needed_pos * 8, rng=rng)
            for c in candidates:
                if c not in used_strings:
                    selected_pos.append(c)
                    used_strings.add(c)
                    if len(selected_pos) == half_k:
                        break
        except ValueError:
            return None

        if len(selected_pos) < half_k:
            return None

    if needed_neg > 0:
        try:
            candidates = sample_strings(truth, accepted=False, length_range=(2, 8), n=needed_neg * 8, rng=rng)
            for c in candidates:
                if c not in used_strings:
                    selected_neg.append(c)
                    used_strings.add(c)
                    if len(selected_neg) == half_k:
                        break
        except ValueError:
            return None

        if len(selected_neg) < half_k:
            return None

    # 5. Combine and shuffle
    tests = selected_pos + selected_neg
    rng.shuffle(tests)

    # 6. Final certification check
    cert = certify(truth, examples, tests, H)
    if cert.is_certified:
        return tests

    return None


__all__ = [
    "Certificate",
    "consistent",
    "certify",
    "build_tests",
]
