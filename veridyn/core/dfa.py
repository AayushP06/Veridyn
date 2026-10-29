"""Deterministic Finite Automata (DFA) representation, subset construction, and simulation.

TOC Concept: Deterministic Finite Automata (DFA), Rabin-Scott Powerset Construction
(Subset Construction), Deterministic Reachability Worklists, DFA Completeness,
Explicit Dead (Sink) States, and Language Equivalence L(M_NFA) = L(M_DFA).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from veridyn.core.nfa import NFA, epsilon_closure


@dataclass(frozen=True)
class DFA:
    """Deterministic Finite Automaton (DFA).

    Formal 5-tuple: M = (Q, Sigma, delta, q_0, F)
    Attributes:
        states: Q, finite set of states (represented as non-negative integers).
        alphabet: Sigma, finite set of input symbols.
        delta: Transition function delta : Q x Sigma -> Q, represented as
            mapping (state, symbol) -> target_state.
            The DFA is strictly COMPLETE: for every q in states and every a in alphabet,
            (q, a) is in delta.
        start: q_0 in Q, unique initial start state.
        accepting: F subseteq Q, set of accepting (final) states.
        dead_state: Explicit sink/dead state (q_dead in Q \\ F where delta(q_dead, a) == q_dead for all a in Sigma).
    """
    states: frozenset[int]
    alphabet: frozenset[str]
    delta: dict[tuple[int, str], int]
    start: int
    accepting: frozenset[int]
    dead_state: int

    def __post_init__(self) -> None:
        # Completeness assertion: every (state, symbol) in Q x Sigma must be explicitly defined
        for q in self.states:
            for a in self.alphabet:
                assert (q, a) in self.delta, f"DFA is incomplete: missing transition for ({q}, '{a}')"
                assert self.delta[(q, a)] in self.states, (
                    f"Transition ({q}, '{a}') targets state {self.delta[(q, a)]} not in states"
                )

        # Explicit dead state assertion
        assert self.dead_state in self.states, f"dead_state {self.dead_state} not in DFA states"
        assert self.dead_state not in self.accepting, (
            f"dead_state {self.dead_state} must not be an accepting state"
        )
        for a in self.alphabet:
            assert self.delta[(self.dead_state, a)] == self.dead_state, (
                f"dead_state {self.dead_state} must self-loop on symbol '{a}'"
            )


def subset_construction(nfa: NFA) -> DFA:
    """Convert an NFA into an equivalent complete DFA using the Rabin-Scott subset construction.

    Features:
      1. Explores only reachable subsets using a breadth-first worklist.
      2. Guarantees deterministic state numbering by traversing symbols in sorted order.
      3. Produces a strictly complete DFA with an explicit dead state (sink state).

    Args:
        nfa: Source NFA (with or without epsilon-transitions).

    Returns:
        DFA: Equivalent complete deterministic finite automaton.
    """
    alphabet_sorted = sorted(nfa.alphabet)

    # Initial subset: epsilon-closure of the NFA start state
    start_subset = epsilon_closure(nfa, frozenset({nfa.start}))

    subset_to_id: dict[frozenset[int], int] = {}
    id_to_subset: dict[int, frozenset[int]] = {}
    worklist: deque[frozenset[int]] = deque()

    # Deterministic ID assignment for start subset
    subset_to_id[start_subset] = 0
    id_to_subset[0] = start_subset
    worklist.append(start_subset)

    delta: dict[tuple[int, str], int] = {}

    while worklist:
        current_subset = worklist.popleft()
        u = subset_to_id[current_subset]

        for a in alphabet_sorted:
            # Step 1: Collect all states reachable on symbol a from current_subset
            next_raw: set[int] = set()
            for q in current_subset:
                succs = nfa.transitions.get((q, a))
                if succs:
                    next_raw.update(succs)

            # Step 2: Compute epsilon-closure of the successor states
            target_subset = epsilon_closure(nfa, frozenset(next_raw))

            # Step 3: Assign deterministic ID if newly discovered
            if target_subset not in subset_to_id:
                new_id = len(subset_to_id)
                subset_to_id[target_subset] = new_id
                id_to_subset[new_id] = target_subset
                worklist.append(target_subset)

            delta[(u, a)] = subset_to_id[target_subset]

    # Explicit dead state handling:
    # If the empty subset frozenset() was reachable, it is already in subset_to_id.
    # If frozenset() was not reached (e.g. for (C|T|S)*), create an explicit dead state.
    empty_sub = frozenset()
    if empty_sub in subset_to_id:
        dead_id = subset_to_id[empty_sub]
    else:
        dead_id = len(subset_to_id)
        subset_to_id[empty_sub] = dead_id
        id_to_subset[dead_id] = empty_sub
        for a in alphabet_sorted:
            delta[(dead_id, a)] = dead_id

    # Determine accepting states: any subset containing at least one NFA accepting state
    accepting = frozenset(
        u for u, sub in id_to_subset.items() if sub & nfa.accepting
    )

    return DFA(
        states=frozenset(id_to_subset.keys()),
        alphabet=nfa.alphabet,
        delta=delta,
        start=0,
        accepting=accepting,
        dead_state=dead_id,
    )


def dfa_accepts(dfa: DFA, string: str) -> bool:
    """Simulate a complete DFA on an input string to check language membership.

    TOC Concept:
        Extended transition function delta-hat(q_0, w) tracking the single deterministic state.
        Accepts iff delta-hat(q_0, w) in F.

    Args:
        dfa: Complete Deterministic Finite Automaton.
        string: Input string over dfa.alphabet.

    Returns:
        True if string is accepted, False otherwise.
    """
    curr = dfa.start
    for ch in string:
        target = dfa.delta.get((curr, ch))
        if target is None:
            return False
        curr = target

    return curr in dfa.accepting


__all__ = [
    "DFA",
    "subset_construction",
    "dfa_accepts",
]
