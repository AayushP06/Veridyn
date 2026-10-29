"""DFA state minimization, canonicalization, and Myhill-Nerode equivalence checking.

TOC Concept: DFA State Minimization, Myhill-Nerode Equivalence Theorem and Relation,
Moore's Partition Refinement Algorithm, Canonical DFA Representation (Isomorphism via BFS),
and Myhill-Nerode Table-Filling Algorithm (State Distinguishability).
"""

from __future__ import annotations

from collections import deque
import hashlib

from veridyn.core.dfa import DFA


# ==============================================================================
# Theoretical Foundations: Myhill-Nerode Equivalence & Partition Refinement
# ==============================================================================
#
# By the Myhill-Nerode Theorem:
# A language L subseteq Sigma* is regular iff the right-invariant equivalence
# relation ~_L has finite index (finite number of equivalence classes).
#
# For a DFA M = (Q, Sigma, delta, q_0, F):
# Two states p, q in Q are equivalent (p ~_L q) iff:
#     forall w in Sigma*,  delta-hat(p, w) in F  <==>  delta-hat(q, w) in F
#
# Moore's Partition Refinement Algorithm computes these classes constructively:
# 1. Base partition P_0 separates accepting from non-accepting states (0-distinguishable by epsilon):
#        P_0 = { F, Q \ F }
# 2. Inductive refinement: Two states p, q in the same block B in P_k remain in the
#    same block in P_{k+1} iff for every symbol a in Sigma, delta(p, a) and delta(q, a)
#    belong to the same block of P_k (i.e. they are not (k+1)-distinguishable).
# 3. Upon reaching a fixed point P* = P_{k+1} = P_k (in at most |Q| iterations),
#    every block B in P* corresponds PRECISELY to a Myhill-Nerode right-invariant
#    equivalence class [q]_{~_L}.
# 4. Collapsing each block into a single state produces the unique minimal DFA
#    recognizing L.
# ==============================================================================


def remove_unreachable(dfa: DFA) -> DFA:
    """Prune all states unreachable from the initial start state.

    Maintains DFA completeness and ensures explicit dead state presence.
    """
    reachable: set[int] = {dfa.start}
    queue: deque[int] = deque([dfa.start])

    while queue:
        curr = queue.popleft()
        for a in dfa.alphabet:
            nxt = dfa.delta[(curr, a)]
            if nxt not in reachable:
                reachable.add(nxt)
                queue.append(nxt)

    # Ensure explicit dead state is retained for completeness
    dead_id = dfa.dead_state
    if dead_id not in reachable:
        reachable.add(dead_id)

    pruned_delta = {
        (q, a): dfa.delta[(q, a)]
        for q in reachable
        for a in dfa.alphabet
        if dfa.delta[(q, a)] in reachable
    }

    # Ensure dead state transitions are complete
    for a in dfa.alphabet:
        pruned_delta[(dead_id, a)] = dead_id

    return DFA(
        states=frozenset(reachable),
        alphabet=dfa.alphabet,
        delta=pruned_delta,
        start=dfa.start,
        accepting=frozenset(dfa.accepting & reachable),
        dead_state=dead_id,
    )


def minimize(dfa: DFA) -> DFA:
    """Minimize a DFA using Moore's partition refinement algorithm.

    TOC Note:
        Blocks of the final partition correspond directly to Myhill-Nerode
        equivalence classes. The resulting minimal DFA is then canonically
        renumbered so that equivalent minimal DFAs are structurally identical data.

    Args:
        dfa: Input deterministic finite automaton.

    Returns:
        Canonical minimal DFA recognizing the exact same language.
    """
    clean_dfa = remove_unreachable(dfa)
    alphabet_sorted = sorted(clean_dfa.alphabet)

    # 1. Initial partition P_0: { F, Q \ F }
    F = frozenset(clean_dfa.accepting)
    non_F = frozenset(q for q in clean_dfa.states if q not in clean_dfa.accepting)

    partition: list[frozenset[int]] = []
    if F:
        partition.append(F)
    if non_F:
        partition.append(non_F)

    # 2. Moore's refinement loop
    state_to_block: dict[int, int] = {
        q: idx for idx, block in enumerate(partition) for q in block
    }

    while True:
        new_partition: list[frozenset[int]] = []
        for block in partition:
            if len(block) <= 1:
                new_partition.append(block)
                continue

            # Group states in block by their transition signature:
            # signature(q) = (state_to_block[delta(q, a_1)], ..., state_to_block[delta(q, a_m)])
            subgroups: dict[tuple[int, ...], set[int]] = {}
            for q in block:
                sig = tuple(state_to_block[clean_dfa.delta[(q, a)]] for a in alphabet_sorted)
                subgroups.setdefault(sig, set()).add(q)

            for subgroup in subgroups.values():
                new_partition.append(frozenset(subgroup))

        if len(new_partition) == len(partition):
            # Fixed point reached: each block is a Myhill-Nerode equivalence class
            break

        partition = new_partition
        state_to_block = {
            q: idx for idx, block in enumerate(partition) for q in block
        }

    # 3. Construct uncanonicalized quotient DFA
    # Find block containing start state
    start_block_idx = state_to_block[clean_dfa.start]

    # Find or designate dead state block
    dead_block_idx = state_to_block[clean_dfa.dead_state]

    block_accepting: set[int] = set()
    block_delta: dict[tuple[int, str], int] = {}

    for idx, block in enumerate(partition):
        rep = next(iter(block))
        if rep in clean_dfa.accepting:
            block_accepting.add(idx)
        for a in alphabet_sorted:
            succ = clean_dfa.delta[(rep, a)]
            block_delta[(idx, a)] = state_to_block[succ]

    raw_min_dfa = DFA(
        states=frozenset(range(len(partition))),
        alphabet=clean_dfa.alphabet,
        delta=block_delta,
        start=start_block_idx,
        accepting=frozenset(block_accepting),
        dead_state=dead_block_idx,
    )

    # 4. Canonicalize via deterministic BFS renumbering
    return canonicalize(raw_min_dfa)


def canonicalize(dfa: DFA) -> DFA:
    """Renumber DFA states using a deterministic BFS traversal over sorted alphabet symbols.

    Guarantees that isomorphic minimal DFAs produce byte-for-byte identical data structures.
    """
    alphabet_sorted = sorted(dfa.alphabet)
    visited: dict[int, int] = {dfa.start: 0}
    queue: deque[int] = deque([dfa.start])
    counter = 1

    while queue:
        curr = queue.popleft()
        for a in alphabet_sorted:
            nxt = dfa.delta[(curr, a)]
            if nxt not in visited:
                visited[nxt] = counter
                counter += 1
                queue.append(nxt)

    # Ensure dead state is included in renumbering if not already visited
    if dfa.dead_state not in visited:
        visited[dfa.dead_state] = counter
        counter += 1

    new_delta: dict[tuple[int, str], int] = {}
    for old_state, new_state in visited.items():
        for a in alphabet_sorted:
            old_nxt = dfa.delta[(old_state, a)]
            # If target was not reachable in BFS, map to dead state
            new_nxt = visited.get(old_nxt, visited[dfa.dead_state])
            new_delta[(new_state, a)] = new_nxt

    return DFA(
        states=frozenset(visited.values()),
        alphabet=dfa.alphabet,
        delta=new_delta,
        start=0,
        accepting=frozenset(visited[q] for q in dfa.accepting if q in visited),
        dead_state=visited[dfa.dead_state],
    )


def dfa_signature(dfa: DFA) -> str:
    """Generate a stable cryptographic SHA-256 hash representing a canonical DFA.

    Two DFAs recognize the same language iff their canonicalized minimal forms
    have the exact same signature.
    """
    # Ensure canonical form before hashing
    canon = canonicalize(dfa)

    alphabet_sorted = sorted(canon.alphabet)
    states_sorted = sorted(canon.states)
    accepting_sorted = sorted(canon.accepting)

    lines: list[str] = [
        f"states:{','.join(map(str, states_sorted))}",
        f"alphabet:{','.join(alphabet_sorted)}",
        f"start:{canon.start}",
        f"dead:{canon.dead_state}",
        f"accepting:{','.join(map(str, accepting_sorted))}",
    ]

    for q in states_sorted:
        for a in alphabet_sorted:
            target = canon.delta[(q, a)]
            lines.append(f"delta:({q},{a})->{target}")

    serialized = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def is_minimal(dfa: DFA) -> bool:
    """Verify whether a DFA is strictly minimal using the Table-Filling Algorithm.

    TOC Concept:
        Moore / Hopcroft-Ullman Table-Filling Algorithm for state distinguishability.
        A DFA is minimal iff:
          1. All states are reachable from the start state (with optional unreachable dead state).
          2. Every pair of distinct reachable states (p, q) is distinguishable by some word w.
    """
    clean_dfa = remove_unreachable(dfa)
    alphabet_sorted = sorted(clean_dfa.alphabet)
    states_list = sorted(clean_dfa.states)
    n = len(states_list)

    # Distinguishable pairs table: set of (p, q) with p < q
    distinguishable: set[tuple[int, int]] = set()

    # Step 1: Base case (0-distinguishable by epsilon)
    # A pair (p, q) is distinguishable if exactly one of them is accepting
    for i in range(n):
        p = states_list[i]
        for j in range(i + 1, n):
            q = states_list[j]
            p_acc = p in clean_dfa.accepting
            q_acc = q in clean_dfa.accepting
            if p_acc != q_acc:
                distinguishable.add((p, q))

    # Step 2: Iterative propagation
    # If delta(p, a) and delta(q, a) are distinguishable, then (p, q) is distinguishable
    while True:
        newly_added = 0
        for i in range(n):
            p = states_list[i]
            for j in range(i + 1, n):
                q = states_list[j]
                if (p, q) in distinguishable:
                    continue

                for a in alphabet_sorted:
                    p_next = clean_dfa.delta[(p, a)]
                    q_next = clean_dfa.delta[(q, a)]
                    if p_next != q_next:
                        u, v = min(p_next, q_next), max(p_next, q_next)
                        if (u, v) in distinguishable:
                            distinguishable.add((p, q))
                            newly_added += 1
                            break

        if newly_added == 0:
            break

    # Total distinct pairs
    total_pairs = (n * (n - 1)) // 2
    return len(distinguishable) == total_pairs


__all__ = [
    "remove_unreachable",
    "minimize",
    "canonicalize",
    "dfa_signature",
    "is_minimal",
]
