"""Nondeterministic Finite Automata (NFA) representation, Thompson's construction, and simulation.

TOC Concept: Nondeterministic Finite Automata with Epsilon Transitions (NFA-epsilon),
Thompson's Structural Induction Construction, Epsilon Closure (Graph Reachability),
Epsilon-Elimination (Epsilon-Free NFA Conversion), and Extended Transition Function
(delta-hat) Simulation via Subset Tracking.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Container
from dataclasses import dataclass

from veridyn.core.regex_parser import (
    ASTNode,
    Concat,
    DEFAULT_ALPHABET,
    Epsilon,
    Star,
    Symbol,
    Union,
    desugar,
)


@dataclass(frozen=True)
class NFA:
    """Nondeterministic Finite Automaton with epsilon-transitions (NFA-epsilon).

    Formal 5-tuple: M = (Q, Sigma, delta, q_0, F)
    Attributes:
        states: Q, finite set of states (represented as non-negative integers).
        alphabet: Sigma, finite set of input symbols.
        transitions: delta : Q x (Sigma U {None}) -> 2^Q, mapping (state, symbol_or_None)
            to a frozenset of successor states. None represents an epsilon-transition.
        start: q_0 in Q, the unique initial start state.
        accepting: F subseteq Q, set of accepting (final) states.
    """
    states: frozenset[int]
    alphabet: frozenset[str]
    transitions: dict[tuple[int, str | None], frozenset[int]]
    start: int
    accepting: frozenset[int]

    def __post_init__(self) -> None:
        # Precompute single-state epsilon closures for accelerated graph reachability
        eps_single: dict[int, frozenset[int]] = {}
        for s in self.states:
            closure: set[int] = {s}
            queue = deque([s])
            while queue:
                curr = queue.popleft()
                for nxt in self.transitions.get((curr, None), ()):
                    if nxt not in closure:
                        closure.add(nxt)
                        queue.append(nxt)
            eps_single[s] = frozenset(closure)
        object.__setattr__(self, "_eps_single", eps_single)
        object.__setattr__(self, "_step_cache", {})


def thompson(ast: ASTNode, alphabet: Container[str] | None = None) -> NFA:
    """Construct an NFA from a regular expression AST using Thompson's construction.

    Thompson's structural induction guarantees:
      1. Exactly one initial state with in-degree 0.
      2. Exactly one accepting state with out-degree 0.
      3. For any AST of size n, the resulting NFA has at most 2n states.

    Args:
        ast: Regular expression AST (will be desugared into core nodes).
        alphabet: Allowed terminal alphabet Sigma. Defaults to {'C', 'T', 'S'}.

    Returns:
        NFA: A canonical Thompson NFA equivalent to the input regular expression.
    """
    core_ast = desugar(ast)
    alpha = frozenset(alphabet) if alphabet is not None else DEFAULT_ALPHABET

    state_counter = 0

    def new_state() -> int:
        nonlocal state_counter
        s = state_counter
        state_counter += 1
        return s

    transitions: dict[tuple[int, str | None], set[int]] = {}
    all_states: set[int] = set()

    def add_transition(src: int, sym: str | None, dst: int) -> None:
        transitions.setdefault((src, sym), set()).add(dst)

    def build(node: ASTNode) -> tuple[int, int]:
        """Recursively build NFA fragment returning (start_state, accept_state)."""
        if isinstance(node, Symbol):
            s = new_state()
            f = new_state()
            all_states.add(s)
            all_states.add(f)
            add_transition(s, node.char, f)
            return s, f

        if isinstance(node, Epsilon):
            s = new_state()
            f = new_state()
            all_states.add(s)
            all_states.add(f)
            add_transition(s, None, f)
            return s, f

        if isinstance(node, Concat):
            s1, f1 = build(node.left)
            s2, f2 = build(node.right)
            add_transition(f1, None, s2)
            return s1, f2

        if isinstance(node, Union):
            s1, f1 = build(node.left)
            s2, f2 = build(node.right)
            s = new_state()
            f = new_state()
            all_states.add(s)
            all_states.add(f)
            add_transition(s, None, s1)
            add_transition(s, None, s2)
            add_transition(f1, None, f)
            add_transition(f2, None, f)
            return s, f

        if isinstance(node, Star):
            s_c, f_c = build(node.child)
            s = new_state()
            f = new_state()
            all_states.add(s)
            all_states.add(f)
            add_transition(s, None, s_c)  # enter child
            add_transition(s, None, f)    # bypass child (zero occurrences)
            add_transition(f_c, None, s_c)  # loop back
            add_transition(f_c, None, f)    # exit loop
            return s, f

        raise TypeError(f"Unexpected AST node in core tree: {type(node)}")

    start_state, accept_state = build(core_ast)

    frozen_transitions = {
        k: frozenset(v) for k, v in transitions.items() if v
    }

    return NFA(
        states=frozenset(all_states),
        alphabet=alpha,
        transitions=frozen_transitions,
        start=start_state,
        accepting=frozenset({accept_state}),
    )


def epsilon_closure(nfa: NFA, states: frozenset[int]) -> frozenset[int]:
    """Compute the epsilon-closure of a set of states.

    TOC Definition:
        ECLOSE(S) = { q in Q | exists path from some p in S to q using only epsilon-transitions }.
    Computed via Breadth-First Search (BFS) / reachability traversal.
    """
    eps_single: dict[int, frozenset[int]] | None = getattr(nfa, "_eps_single", None)
    if eps_single is not None:
        closure: set[int] = set()
        for s in states:
            closure.update(eps_single.get(s, (s,)))
        return frozenset(closure)

    closure = set(states)
    queue = deque(states)

    while queue:
        curr = queue.popleft()
        eps_successors = nfa.transitions.get((curr, None))
        if eps_successors:
            for nxt in eps_successors:
                if nxt not in closure:
                    closure.add(nxt)
                    queue.append(nxt)

    return frozenset(closure)


def eliminate_epsilon(nfa: NFA) -> NFA:
    """Eliminate all epsilon-transitions to produce an equivalent epsilon-free NFA.

    TOC Definition:
        Given M = (Q, Sigma, delta, q_0, F), the epsilon-free NFA M' = (Q', Sigma, delta', q_0, F') is:
        - F' = { q in Q | ECLOSE({q}) intersects F }
        - delta'(q, a) = ECLOSE( delta(ECLOSE({q}), a) ) for all a in Sigma
        - delta'(q, None) = empty set (all epsilon edges eliminated)
        Reachable states from q_0 are retained.
    """
    eps_single: dict[int, frozenset[int]] | None = getattr(nfa, "_eps_single", None)
    if eps_single is None:
        eps_single = {s: epsilon_closure(nfa, frozenset({s})) for s in nfa.states}

    new_accepting = frozenset(
        q for q in nfa.states if eps_single[q] & nfa.accepting
    )

    new_transitions: dict[tuple[int, str | None], frozenset[int]] = {}

    for q in nfa.states:
        eclose_q = eps_single[q]
        for a in nfa.alphabet:
            targets_on_a: set[int] = set()
            for p in eclose_q:
                succs = nfa.transitions.get((p, a))
                if succs:
                    targets_on_a.update(succs)

            if targets_on_a:
                final_targets: set[int] = set()
                for t in targets_on_a:
                    final_targets.update(eps_single[t])
                new_transitions[(q, a)] = frozenset(final_targets)

    # Retain only reachable states from start state q_0 in M'
    reachable: set[int] = {nfa.start}
    queue = deque([nfa.start])
    while queue:
        curr = queue.popleft()
        for a in nfa.alphabet:
            for nxt in new_transitions.get((curr, a), ()):
                if nxt not in reachable:
                    reachable.add(nxt)
                    queue.append(nxt)

    pruned_transitions = {
        (src, sym): frozenset(dst for dst in dsts if dst in reachable)
        for (src, sym), dsts in new_transitions.items()
        if src in reachable
    }

    return NFA(
        states=frozenset(reachable),
        alphabet=nfa.alphabet,
        transitions={k: v for k, v in pruned_transitions.items() if v},
        start=nfa.start,
        accepting=frozenset(new_accepting & reachable),
    )


def _step_nfa(nfa: NFA, current_states: frozenset[int], symbol: str) -> frozenset[int]:
    """Compute successor state set after consuming one symbol: ECLOSE(delta(S, symbol))."""
    next_raw: set[int] = set()
    for q in current_states:
        succs = nfa.transitions.get((q, symbol))
        if succs:
            next_raw.update(succs)
    if not next_raw:
        return frozenset()
    return epsilon_closure(nfa, frozenset(next_raw))


def nfa_accepts(nfa: NFA, word: str) -> bool:
    """Simulate an NFA on an input string to check language membership w in L(M).

    TOC Concept:
        Extended transition function delta-hat(q_0, w) tracking the subset of
        reachable states after reading prefix w_[:i] with epsilon-closures applied.
        Accepts iff delta-hat(q_0, w) intersects F.

    Args:
        nfa: The NFA to simulate.
        word: Input string over nfa.alphabet.

    Returns:
        True if the string is accepted by the NFA, False otherwise.
    """
    cache: dict[tuple[frozenset[int], str], frozenset[int]] | None = getattr(nfa, "_step_cache", None)
    current = epsilon_closure(nfa, frozenset({nfa.start}))

    for sym in word:
        if cache is not None:
            key = (current, sym)
            nxt = cache.get(key)
            if nxt is None:
                nxt = _step_nfa(nfa, current, sym)
                cache[key] = nxt
            current = nxt
        else:
            current = _step_nfa(nfa, current, sym)

        if not current:
            return False

    return bool(current & nfa.accepting)


__all__ = [
    "NFA",
    "thompson",
    "epsilon_closure",
    "eliminate_epsilon",
    "nfa_accepts",
]
