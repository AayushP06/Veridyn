"""Boolean operations on regular languages using product automata and state inversion.

TOC Concept: Closure Properties of Regular Languages under Boolean Operations
(Union, Intersection, Complementation, Set Difference, Symmetric Difference),
Cross-Product Automata Construction, Language Emptiness Testing, and Language Equivalence.
"""

from __future__ import annotations

from collections import deque

from veridyn.core.dfa import DFA
from veridyn.core.minimize import remove_unreachable


def complement(dfa: DFA) -> DFA:
    """Construct the complement DFA recognizing Sigma* \\ L(dfa).

    TOC Concept:
        State Inversion in Complete DFAs.
        For a complete DFA M = (Q, Sigma, delta, q_0, F), the complement language
        is recognized by inverting accepting states: F' = Q \\ F.
        An explicit dead state is added to strictly preserve VeriDyn DFA invariants.
    """
    clean_dfa = remove_unreachable(dfa)
    alphabet_sorted = sorted(clean_dfa.alphabet)

    # Invert accepting states among reachable states
    new_accepting = frozenset(q for q in clean_dfa.states if q not in clean_dfa.accepting)

    # Add an explicit non-accepting dead state with self-loops to maintain DFA invariants
    dead_id = max(clean_dfa.states) + 1
    new_states = set(clean_dfa.states) | {dead_id}
    new_delta = dict(clean_dfa.delta)
    for a in alphabet_sorted:
        new_delta[(dead_id, a)] = dead_id

    return DFA(
        states=frozenset(new_states),
        alphabet=clean_dfa.alphabet,
        delta=new_delta,
        start=clean_dfa.start,
        accepting=new_accepting,
        dead_state=dead_id,
    )


def product(d1: DFA, d2: DFA, mode: str) -> DFA:
    """Synchronous product automaton construction for regular language Boolean operations.

    TOC Concept:
        Given M1 = (Q1, Sigma, delta1, q0_1, F1) and M2 = (Q2, Sigma, delta2, q0_2, F2):
        The product automaton M = (Q1 x Q2, Sigma, delta, (q0_1, q0_2), F) tracks
        both automata synchronously on each symbol:
            delta((p, q), a) = (delta1(p, a), delta2(q, a))

    Modes:
        - 'intersection':          F = { (p, q) | p in F1 and q in F2 }
        - 'union':                 F = { (p, q) | p in F1 or q in F2 }
        - 'difference':            F = { (p, q) | p in F1 and q not in F2 }
        - 'symmetric_difference':  F = { (p, q) | (p in F1) != (q in F2) }

    Args:
        d1: First complete DFA.
        d2: Second complete DFA.
        mode: Boolean operation ('intersection', 'union', 'difference', 'symmetric_difference').

    Returns:
        DFA recognizing the combined language.
    """
    valid_modes = {"intersection", "union", "difference", "symmetric_difference"}
    if mode not in valid_modes:
        raise ValueError(f"Invalid mode '{mode}'. Expected one of {valid_modes}")

    alphabet_union = sorted(d1.alphabet | d2.alphabet)

    start_pair = (d1.start, d2.start)
    pair_to_id: dict[tuple[int, int], int] = {start_pair: 0}
    id_to_pair: dict[int, tuple[int, int]] = {0: start_pair}
    worklist: deque[tuple[int, int]] = deque([start_pair])

    delta: dict[tuple[int, str], int] = {}

    while worklist:
        p, q = worklist.popleft()
        u = pair_to_id[(p, q)]

        for a in alphabet_union:
            p_next = d1.delta.get((p, a), d1.dead_state)
            q_next = d2.delta.get((q, a), d2.dead_state)
            next_pair = (p_next, q_next)

            if next_pair not in pair_to_id:
                new_id = len(pair_to_id)
                pair_to_id[next_pair] = new_id
                id_to_pair[new_id] = next_pair
                worklist.append(next_pair)

            delta[(u, a)] = pair_to_id[next_pair]

    # Accepting states determined by Boolean mode predicate
    accepting: set[int] = set()
    for state_id, (p, q) in id_to_pair.items():
        p_in = p in d1.accepting
        q_in = q in d2.accepting

        if mode == "intersection" and (p_in and q_in):
            accepting.add(state_id)
        elif mode == "union" and (p_in or q_in):
            accepting.add(state_id)
        elif mode == "difference" and (p_in and not q_in):
            accepting.add(state_id)
        elif mode == "symmetric_difference" and (p_in != q_in):
            accepting.add(state_id)

    # Designate or create explicit dead state
    dead_pair = (d1.dead_state, d2.dead_state)
    if dead_pair in pair_to_id and pair_to_id[dead_pair] not in accepting:
        dead_id = pair_to_id[dead_pair]
    else:
        dead_id = len(pair_to_id)
        for a in alphabet_union:
            delta[(dead_id, a)] = dead_id

    return DFA(
        states=frozenset(set(id_to_pair.keys()) | {dead_id}),
        alphabet=frozenset(alphabet_union),
        delta=delta,
        start=0,
        accepting=frozenset(accepting),
        dead_state=dead_id,
    )


def union(d1: DFA, d2: DFA) -> DFA:
    """Construct DFA for L(d1) union L(d2)."""
    return product(d1, d2, mode="union")


def intersection(d1: DFA, d2: DFA) -> DFA:
    """Construct DFA for L(d1) intersect L(d2)."""
    return product(d1, d2, mode="intersection")


def difference(d1: DFA, d2: DFA) -> DFA:
    """Construct DFA for L(d1) \\ L(d2)."""
    return product(d1, d2, mode="difference")


def symmetric_difference(d1: DFA, d2: DFA) -> DFA:
    """Construct DFA for L(d1) (+) L(d2)."""
    return product(d1, d2, mode="symmetric_difference")


def is_empty(dfa: DFA) -> bool:
    """Check if the language recognized by a DFA is empty (L(dfa) == empty_set).

    TOC Concept:
        Emptiness Decision Property for Regular Languages.
        L(M) is empty iff no accepting state is reachable from q_0.
    """
    if dfa.start in dfa.accepting:
        return False

    reachable: set[int] = {dfa.start}
    queue: deque[int] = deque([dfa.start])

    while queue:
        curr = queue.popleft()
        for a in dfa.alphabet:
            nxt = dfa.delta[(curr, a)]
            if nxt in dfa.accepting:
                return False
            if nxt not in reachable:
                reachable.add(nxt)
                queue.append(nxt)

    return True


def equivalent(d1: DFA, d2: DFA) -> bool:
    """Check language equivalence L(d1) == L(d2) via symmetric difference.

    TOC Concept:
        Equivalence Decision Property for Regular Languages:
        L(d1) == L(d2) <==> L(d1 (+) d2) == empty_set.
    """
    sym_diff = symmetric_difference(d1, d2)
    return is_empty(sym_diff)


__all__ = [
    "complement",
    "product",
    "union",
    "intersection",
    "difference",
    "symmetric_difference",
    "is_empty",
    "equivalent",
]
