"""Hidden rule synthesis and non-equivalence validation against hypothesis library H.

TOC Concept: Regular Language Composition, Boolean Closure Syntheses,
and Equivalence Invariants (Separation from Candidate Hypothesis Class).
"""

from __future__ import annotations

from dataclasses import dataclass

from veridyn.challenge.hypotheses import Hypothesis, build_hypothesis_library
from veridyn.core.boolean_ops import (
    complement,
    difference,
    equivalent,
    intersection,
    is_empty,
    symmetric_difference,
    union,
)
from veridyn.core.dfa import DFA
from veridyn.core.minimize import minimize


@dataclass(frozen=True)
class HiddenRule:
    """A target regular rule defined as a Boolean combination of at most 2 atomic hypotheses.

    Invariants:
        1. Formed by AND, OR, DIFFERENCE, or XOR of at most 2 atoms from H.
        2. Non-trivial: neither empty nor universal (Sigma*).
        3. Strictly NOT equivalent to any single member in H.
    """
    name: str
    dfa: DFA
    formula: str
    atoms: tuple[str, ...]


def rule_not_in_H(dfa: DFA, H: list[Hypothesis]) -> bool:
    """Verify that a candidate rule DFA is not equivalent to any single hypothesis in H.

    TOC Concept:
        Equivalence Decision:
        forall h in H,  L(dfa) != L(h)  <==>  not equivalent(dfa, h.dfa).

    Args:
        dfa: Candidate target rule DFA.
        H: Hypothesis library.

    Returns:
        True if dfa is not equivalent to any h in H, False otherwise.
    """
    for h in H:
        if equivalent(dfa, h.dfa):
            return False
    return True


def create_boolean_rule(
    h1: Hypothesis,
    h2: Hypothesis,
    op: str,
    H: list[Hypothesis],
) -> HiddenRule | None:
    """Synthesize a minimized target rule from two hypotheses under an operation, if valid.

    Args:
        h1: First atomic hypothesis.
        h2: Second atomic hypothesis.
        op: Operation ('and', 'or', 'diff', 'xor', 'not_and').
        H: Full hypothesis library to enforce rule_not_in_H.

    Returns:
        HiddenRule if valid, non-trivial, and separated from H; None otherwise.
    """
    if op == "and":
        raw = intersection(h1.dfa, h2.dfa)
        formula = f"({h1.name} AND {h2.name})"
    elif op == "or":
        raw = union(h1.dfa, h2.dfa)
        formula = f"({h1.name} OR {h2.name})"
    elif op == "diff":
        raw = difference(h1.dfa, h2.dfa)
        formula = f"({h1.name} AND NOT {h2.name})"
    elif op == "not_and":
        raw = difference(h2.dfa, h1.dfa)
        formula = f"(NOT {h1.name} AND {h2.name})"
    elif op == "xor":
        raw = symmetric_difference(h1.dfa, h2.dfa)
        formula = f"({h1.name} XOR {h2.name})"
    else:
        raise ValueError(f"Unknown operation: {op}")

    dfa_min = minimize(raw)

    # 1. Reject trivial languages (empty or universal)
    if is_empty(dfa_min):
        return None
    if is_empty(complement(dfa_min)):
        return None

    # 2. Reject rules equivalent to any single member in H
    if not rule_not_in_H(dfa_min, H):
        return None

    name = f"rule_{h1.name}_{op}_{h2.name}"
    return HiddenRule(
        name=name,
        dfa=dfa_min,
        formula=formula,
        atoms=(h1.name, h2.name),
    )


def generate_candidate_rules(
    H: list[Hypothesis] | None = None,
    limit: int = 50,
) -> list[HiddenRule]:
    """Generate a diverse catalog of valid hidden rules from the hypothesis library.

    Args:
        H: Hypothesis library (defaults to build_hypothesis_library()).
        limit: Maximum number of valid hidden rules to synthesize.

    Returns:
        List of verified HiddenRule instances.
    """
    library = H if H is not None else build_hypothesis_library()
    rules: list[HiddenRule] = []

    operations = ["and", "or", "diff", "xor"]

    for i in range(len(library)):
        for j in range(i + 1, len(library)):
            h1 = library[i]
            h2 = library[j]

            for op in operations:
                rule = create_boolean_rule(h1, h2, op, library)
                if rule is not None:
                    rules.append(rule)
                    if len(rules) >= limit:
                        return rules

    return rules


__all__ = [
    "HiddenRule",
    "rule_not_in_H",
    "create_boolean_rule",
    "generate_candidate_rules",
]
