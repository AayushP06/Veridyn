"""Automata simulation, computation trace tracking, and liveness analysis.

TOC Concept: Computation Traces on Finite Automata, State Transitions,
Extended Transition Function Paths, Liveness (Productive States), and Dead State Detection.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

from veridyn.core.dfa import DFA


@dataclass(frozen=True)
class Trace:
    """Execution trace of a DFA on an input sequence of symbols.

    Attributes:
        visited_states: Complete sequence of states visited during execution.
            Length is len(symbols) + 1. Starts with dfa.start.
        verdict: True if the final visited state is in dfa.accepting, False otherwise.
        first_dead_index: 0-based character index where the DFA first entered a
            non-live (dead/trap) state, or None if the DFA never entered a dead state.
    """
    visited_states: tuple[int, ...]
    verdict: bool
    first_dead_index: int | None


def live_states(dfa: DFA) -> frozenset[int]:
    """Compute the set of live (productive) states in a DFA.

    TOC Concept:
        A state q in Q is live iff there exists some word w in Sigma* such that
        delta-hat(q, w) in F. A state is dead / unproductive if no accepting state
        can ever be reached from it.
        Computed via backward breadth-first search from the set of accepting states F.

    Args:
        dfa: Complete deterministic finite automaton.

    Returns:
        frozenset of state IDs that can reach at least one accepting state.
    """
    if not dfa.accepting:
        return frozenset()

    # Invert transition graph: map dst -> set of src states
    predecessors: dict[int, set[int]] = {q: set() for q in dfa.states}
    for (src, _), dst in dfa.delta.items():
        if dst in predecessors:
            predecessors[dst].add(src)

    live: set[int] = set(dfa.accepting)
    queue: deque[int] = deque(dfa.accepting)

    while queue:
        curr = queue.popleft()
        for pred in predecessors.get(curr, ()):
            if pred not in live:
                live.add(pred)
                queue.append(pred)

    return frozenset(live)


def run(dfa: DFA, symbols: Sequence[str] | str) -> Trace:
    """Execute a DFA on a sequence of symbols and record a full computation trace.

    TOC Concept:
        Computation Path: (q_0, a_1, q_1, a_2, ..., a_n, q_n)
        Traces each intermediate state and detects the earliest point of dead-state entry.

    Args:
        dfa: Complete deterministic finite automaton.
        symbols: Input string or sequence of terminal alphabet symbols.

    Returns:
        Trace recording visited states, acceptance verdict, and first dead-state index.
    """
    live = live_states(dfa)

    visited: list[int] = [dfa.start]
    first_dead_idx: int | None = 0 if dfa.start not in live else None

    curr = dfa.start
    for i, sym in enumerate(symbols):
        nxt = dfa.delta.get((curr, sym), dfa.dead_state)
        visited.append(nxt)
        if first_dead_idx is None and nxt not in live:
            first_dead_idx = i
        curr = nxt

    verdict = curr in dfa.accepting
    return Trace(
        visited_states=tuple(visited),
        verdict=verdict,
        first_dead_index=first_dead_idx,
    )


__all__ = [
    "Trace",
    "live_states",
    "run",
]
