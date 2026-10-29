"""Finding shortest distinguishing strings and witness words between DFAs.

TOC Concept: Equivalence Verification, Symmetric Difference Witness Finding,
Shortest Separating Words between Non-Equivalent Regular Languages via BFS
over Cross-Product State Graphs.
"""

from __future__ import annotations

from collections import deque

from veridyn.core.dfa import DFA


def distinguishing_strings(d1: DFA, d2: DFA, limit: int = 5) -> list[str]:
    """Find multiple short distinguishing strings between two DFAs using BFS.

    TOC Concept:
        Witness generation in language equivalence testing.
        Searches the cross-product transition graph (Q1 x Q2) in level-by-level
        BFS order to find strings in the symmetric difference L(d1) (+) L(d2).

    Args:
        d1: First complete DFA.
        d2: Second complete DFA.
        limit: Maximum number of distinguishing strings to return.

    Returns:
        List of distinct strings accepted by exactly one DFA, ordered by
        increasing length, then lexicographical order. Returns [] if equivalent.
    """
    if limit <= 0:
        return []

    alphabet = sorted(d1.alphabet | d2.alphabet)
    results: list[str] = []

    # 1. Check the empty string epsilon
    if (d1.start in d1.accepting) != (d2.start in d2.accepting):
        results.append("")
        if len(results) >= limit:
            return results

    # 2. Level-by-level BFS over (p, q) pairs and path string
    queue: deque[tuple[int, int, str]] = deque([(d1.start, d2.start, "")])
    visited: set[tuple[int, int]] = {(d1.start, d2.start)}

    while queue and len(results) < limit:
        p, q, path = queue.popleft()

        for a in alphabet:
            p_next = d1.delta.get((p, a), d1.dead_state)
            q_next = d2.delta.get((q, a), d2.dead_state)
            cand_path = path + a

            p_acc = p_next in d1.accepting
            q_acc = q_next in d2.accepting

            if p_acc != q_acc:
                results.append(cand_path)
                if len(results) >= limit:
                    break

            pair = (p_next, q_next)
            if pair not in visited:
                visited.add(pair)
                queue.append((p_next, q_next, cand_path))

    return results


def shortest_distinguishing_string(d1: DFA, d2: DFA) -> str | None:
    """Find the shortest string accepted by exactly one DFA, or None if equivalent.

    TOC Concept:
        Shortest Separating Sequence in the Symmetric Difference Automaton.
        Guaranteed to find the minimal-length witness string by BFS properties.

    Args:
        d1: First complete DFA.
        d2: Second complete DFA.

    Returns:
        The shortest separating word, or None if L(d1) == L(d2).
    """
    witnesses = distinguishing_strings(d1, d2, limit=1)
    return witnesses[0] if witnesses else None


__all__ = [
    "distinguishing_strings",
    "shortest_distinguishing_string",
]
