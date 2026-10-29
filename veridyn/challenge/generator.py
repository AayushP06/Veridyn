"""Challenge generation pipeline: difficulty levels, admission checks, and certified challenge synthesis.

TOC Concept: Inductive Learning Problem Generation, Certified Hardness Constraints,
Automata-Driven Positive/Negative Example Sampling, and Balanced Test Witness Partitioning.
"""

from __future__ import annotations

from collections.abc import Container
from dataclasses import dataclass
from functools import lru_cache
import random

from veridyn.challenge.certify import Certificate, build_tests, certify
from veridyn.challenge.hypotheses import Hypothesis, build_hypothesis_library
from veridyn.challenge.rules import HiddenRule, create_boolean_rule, rule_not_in_H
from veridyn.core.analyze import sample_strings
from veridyn.core.boolean_ops import complement, is_empty
from veridyn.core.dfa import DFA, subset_construction
from veridyn.core.minimize import dfa_signature, minimize
from veridyn.core.nfa import thompson
from veridyn.core.regex_parser import DEFAULT_ALPHABET, parse


class GenerationError(RuntimeError):
    """Raised when challenge generation fails admission checks after maximum retries."""
    pass


@dataclass(frozen=True)
class LevelConfig:
    """Configuration constraints for a challenge difficulty level."""
    level: int
    name: str
    description: str
    max_states: int
    atoms_count: int
    operation: str | None


LEVEL_CONFIGS: dict[int, LevelConfig] = {
    1: LevelConfig(
        level=1,
        name="Novice",
        description="Single atomic regular property outside H (2/3-symbol prefix, suffix, or substring)",
        max_states=6,
        atoms_count=1,
        operation=None,
    ),
    2: LevelConfig(
        level=2,
        name="Elementary",
        description="Conjunction (AND) of 2 atomic regular properties from H",
        max_states=8,
        atoms_count=2,
        operation="and",
    ),
    3: LevelConfig(
        level=3,
        name="Intermediate",
        description="Difference (AND NOT) of 2 atomic regular properties from H",
        max_states=10,
        atoms_count=2,
        operation="diff",
    ),
    4: LevelConfig(
        level=4,
        name="Advanced",
        description="Disjunction (OR) of 2 atomic regular properties from H",
        max_states=12,
        atoms_count=2,
        operation="or",
    ),
    5: LevelConfig(
        level=5,
        name="Expert",
        description="Symmetric difference (XOR) of 2 atomic regular properties from H",
        max_states=20,
        atoms_count=2,
        operation="xor",
    ),
}


@dataclass(frozen=True)
class Challenge:
    """A fully certified inductive challenge instance.

    Attributes:
        rule_name: Name of the hidden regular rule.
        regex_str: Regex representation of the hidden rule.
        dfa: Canonical minimal DFA of the hidden rule.
        dfa_signature: SHA-256 canonical hash of the DFA.
        positive_examples: Labelled accepted example strings (length in [2, 6]).
        negative_examples: Labelled rejected example strings (length in [2, 6]).
        test_strings: Balanced set of k test strings to classify (length <= 8).
        certificate: Inductive certificate proving no h in H can pass.
        level: Difficulty level (1..5).
        seed: Initial seed used to generate this challenge.
    """
    rule_name: str
    regex_str: str
    dfa: DFA
    dfa_signature: str
    positive_examples: tuple[str, ...]
    negative_examples: tuple[str, ...]
    test_strings: tuple[str, ...]
    certificate: Certificate
    level: int
    seed: int


# ==============================================================================
# Rule Catalog Generation per Level
# ==============================================================================

def _make_rule_from_regex(name: str, regex_str: str, H: list[Hypothesis], alpha: Container[str]) -> HiddenRule | None:
    """Helper to compile a single-atom regex rule outside H."""
    ast = parse(regex_str, alphabet=alpha)
    dfa = minimize(subset_construction(thompson(ast, alphabet=alpha)))
    if is_empty(dfa) or is_empty(complement(dfa)):
        return None
    if not rule_not_in_H(dfa, H):
        return None
    return HiddenRule(name=name, dfa=dfa, formula=name, atoms=(name,))


@lru_cache(maxsize=16)
def get_rules_for_level(level: int, alphabet: frozenset[str] | None = None) -> list[HiddenRule]:
    """Retrieve precompiled, verified hidden rules conforming to the level specification."""
    alpha = alphabet if alphabet is not None else DEFAULT_ALPHABET
    H = build_hypothesis_library(alpha)

    if level not in LEVEL_CONFIGS:
        raise ValueError(f"Invalid level {level}. Supported levels are 1..5.")

    config = LEVEL_CONFIGS[level]
    rules: list[HiddenRule] = []

    if config.atoms_count == 1:
        # Level 1: 1-atom properties outside H (2-char and 3-char prefixes, suffixes, substrings, mod counts)
        patterns: list[tuple[str, str]] = []

        # 2-character prefixes (9)
        for p1 in ("C", "T", "S"):
            for p2 in ("C", "T", "S"):
                patterns.append((f"prefix_{p1}{p2}", f"{p1}{p2}(C|T|S)*"))

        # 2-character suffixes (9)
        for s1 in ("C", "T", "S"):
            for s2 in ("C", "T", "S"):
                patterns.append((f"suffix_{s1}{s2}", f"(C|T|S)*{s1}{s2}"))

        # 3-character prefixes (27)
        for p1 in ("C", "T", "S"):
            for p2 in ("C", "T", "S"):
                for p3 in ("C", "T", "S"):
                    patterns.append((f"prefix_{p1}{p2}{p3}", f"{p1}{p2}{p3}(C|T|S)*"))

        # 3-character substrings (sample 15)
        for sub in ("CCC", "TTT", "SSS", "CTC", "TCT", "SCS", "CST", "TSC", "SCT", "TCS", "CTS", "STC", "CCT", "TTC", "SSC"):
            patterns.append((f"contains_{sub}", f"(C|T|S)*{sub}(C|T|S)*"))

        # Modulo counts not in H (e.g. mod 3 == 1, mod 3 == 2)
        patterns.append(("count_C_mod3_1", "(T|S)*C(T|S|C(T|S)*C(T|S)*C)*"))
        patterns.append(("count_C_mod3_2", "(T|S)*C(T|S)*C(T|S|C(T|S)*C(T|S)*C)*"))
        patterns.append(("count_T_mod3_1", "(C|S)*T(C|S|T(C|S)*T(C|S)*T)*"))
        patterns.append(("count_T_mod3_2", "(C|S)*T(C|S)*T(C|S|T(C|S)*T(C|S)*T)*"))
        patterns.append(("count_S_mod3_1", "(C|T)*S(C|T|S(C|T)*S(C|T)*S)*"))
        patterns.append(("count_S_mod3_2", "(C|T)*S(C|T)*S(C|T|S(C|T)*S(C|T)*S)*"))

        for name, pat in patterns:
            r = _make_rule_from_regex(name, pat, H, alpha)
            if r is not None and len(r.dfa.states) <= config.max_states:
                rules.append(r)

    else:
        # Levels 2..5: 2-atom Boolean combinations from H
        op = config.operation
        assert op is not None

        for i in range(len(H)):
            for j in range(i + 1, len(H)):
                h1, h2 = H[i], H[j]
                r = create_boolean_rule(h1, h2, op, H)
                if r is not None and len(r.dfa.states) <= config.max_states:
                    rules.append(r)

    assert len(rules) >= 50, (
        f"Level {level} must have at least 50 candidate rules, found {len(rules)}"
    )
    return rules


# ==============================================================================
# Challenge Generation with Admission Checks
# ==============================================================================

def validate_rule_admission(
    rule_dfa: DFA,
    H: list[Hypothesis],
    max_states: int,
    session_signatures: Container[str] | None = None,
) -> tuple[bool, str | None]:
    """Execute formal admission checks on a candidate rule.

    Admission Invariants:
      1. Non-triviality: L(M) != empty_set and L(M) != Sigma*.
      2. Separation: rule not in H (forall h in H, L(M) != L(h)).
      3. Complexity: |Q_min| <= max_states for this level.
      4. Deduplication: dfa_signature not in session_signatures.

    Returns:
        (is_admissible, rejection_reason)
    """
    if is_empty(rule_dfa):
        return False, "Language is empty"

    if is_empty(complement(rule_dfa)):
        return False, "Language is universal (Sigma*)"

    if not rule_not_in_H(rule_dfa, H):
        return False, "Rule is equivalent to a member of H"

    if len(rule_dfa.states) > max_states:
        return False, f"Minimal DFA has {len(rule_dfa.states)} states, exceeding level cap of {max_states}"

    sig = dfa_signature(rule_dfa)
    if session_signatures is not None and sig in session_signatures:
        return False, f"Rule with signature '{sig}' was already issued in this session"

    return True, None


def generate_challenge(
    level: int,
    seed: int,
    session_signatures: set[str] | None = None,
    alphabet: frozenset[str] | None = None,
    k: int = 6,
    n_examples: int = 6,
    max_retries: int = 200,
) -> Challenge:
    """Generate a certified inductive challenge instance.

    Guarantees:
      - Admission checks strictly validated.
      - Exactly N_ex labelled examples (N_ex // 2 valid, N_ex // 2 invalid, length 2..6).
      - Exactly k test strings (k // 2 valid, k // 2 invalid, length <= 8).
      - Formal Certificate attached proving 0% pass rate for consistent H-guessers.
      - Retries with derived deterministic seeds up to max_retries before raising GenerationError.

    Args:
        level: Difficulty level (1..5).
        seed: Base random seed for reproducibility.
        session_signatures: Set of previously generated DFA signatures to deduplicate.
        alphabet: Target alphabet (defaults to {C, T, S}).
        k: Test string count (must be even, defaults to 6).
        n_examples: Total example count (must be even, defaults to 6: 3 pos, 3 neg).
        max_retries: Maximum candidate sampling attempts (defaults to 200).

    Returns:
        Challenge: A fully certified inductive challenge.

    Raises:
        GenerationError: If no qualifying challenge could be constructed within max_retries.
    """
    alpha = alphabet if alphabet is not None else DEFAULT_ALPHABET
    H = build_hypothesis_library(alpha)

    if level not in LEVEL_CONFIGS:
        raise ValueError(f"Invalid level {level}. Supported levels are 1..5.")

    config = LEVEL_CONFIGS[level]
    rules_pool = get_rules_for_level(level, alpha)

    half_ex = n_examples // 2
    last_rejection_reason = "Unknown"

    for attempt in range(max_retries):
        # Deterministically derive attempt seed from (seed, attempt, level)
        derived_seed = (seed + attempt * 10007 + level * 7919) & 0xFFFFFFFF
        rng = random.Random(derived_seed)

        # 1. Select a candidate rule from the level pool
        rule = rng.choice(rules_pool)

        # 2. Admission check on candidate rule
        admissible, reason = validate_rule_admission(
            rule.dfa, H, config.max_states, session_signatures
        )
        if not admissible:
            last_rejection_reason = reason or "Inadmissible rule"
            continue

        # 3. Sample balanced examples: length in [2, 6]
        try:
            pos_ex = sample_strings(
                rule.dfa, accepted=True, length_range=(2, 6), n=half_ex, rng=rng
            )
            neg_ex = sample_strings(
                rule.dfa, accepted=False, length_range=(2, 6), n=half_ex, rng=rng
            )
        except ValueError as e:
            last_rejection_reason = f"Example sampling error: {e}"
            continue

        if len(pos_ex) != half_ex or len(neg_ex) != half_ex:
            last_rejection_reason = "Could not sample sufficient unique balanced examples"
            continue

        examples = (pos_ex, neg_ex)

        # 4. Build balanced test strings with certification
        tests = build_tests(rule.dfa, examples, H, k=k, rng=rng)
        if tests is None:
            last_rejection_reason = "Test set construction failed (witness budget or balance exceeded)"
            continue

        # 5. Execute certification
        cert = certify(rule.dfa, examples, tests, H)
        if not cert.is_certified:
            last_rejection_reason = f"Certification failed: {cert.failure_reason}"
            continue

        # 6. Admission succeeded! Dedupe by signature
        sig = dfa_signature(rule.dfa)
        if session_signatures is not None:
            session_signatures.add(sig)

        return Challenge(
            rule_name=rule.name,
            regex_str=rule.formula,
            dfa=rule.dfa,
            dfa_signature=sig,
            positive_examples=tuple(pos_ex),
            negative_examples=tuple(neg_ex),
            test_strings=tuple(tests),
            certificate=cert,
            level=level,
            seed=seed,
        )

    raise GenerationError(
        f"Failed to generate an admissible challenge for level {level} after {max_retries} attempts. "
        f"Last rejection reason: {last_rejection_reason}"
    )


__all__ = [
    "GenerationError",
    "LevelConfig",
    "LEVEL_CONFIGS",
    "Challenge",
    "get_rules_for_level",
    "validate_rule_admission",
    "generate_challenge",
]
