# VeriDyn Empirical Evaluation Report & Limitations Specification

> **Mandatory Scope Statement:**
> *"VeriDyn certifies that no guessing strategy in a stated hypothesis class passes the challenge. It does NOT verify that a respondent is human. Learners, programs and language models outside that class are not covered."*

---

## 1. Executive Summary and Evaluation Framework

VeriDyn formulates the challenge of regular language induction as an interactive oracle proof protocol. This document outlines the formal interpretation of each benchmark metric in the empirical test suite (`experiments/`), delineating precisely what each experiment proves, what it cannot prove, and the system's explicit theoretical and practical boundaries.

---

## 2. Metric-by-Metric Verification Matrix

| Experiment | Target Hypothesis / Property | What the Metric Proves | What the Metric CANNOT Prove |
|:---|:---|:---|:---|
| **`exp_correctness`** | Representation Equivalence | All 5 automata models ($\text{RE} \equiv \text{NFA} \equiv \text{NFA}_{\varepsilon\text{-free}} \equiv \text{DFA} \equiv \text{DFA}_{\text{min}}$) agree identically on 100% of strings up to length 5. Zero differential mismatches. | Does not prove equivalence for infinite-length strings (proven separately by DFA minimization isomorphism). |
| **`exp_performance`** | Complexity & Blow-Up | Subset construction adheres strictly to the $2^{k+1}+2$ state progression for $(C\|T)^*C(C\|T)^k$. Challenge synthesis and certification execute in $< 50$ ms per challenge. | Does not guarantee polynomial-time subset construction on arbitrary unbounded non-deterministic automata. |
| **`exp_certification`** | Inductive Hardness against $\mathcal{H}$ | **Core Result:** Consistent hypothesis guessers in $\mathcal{H}$ pass random test suites 15–37% of the time, but achieve an **exact 0.0000% pass rate** on certified witness test suites. | Does not prove that learners with richer model spaces outside $\mathcal{H}$ cannot pass. |
| **`exp_coin_flip`** | Random Respondent Baseline | Random binary response vectors pass with frequency tightly centered on the analytic $2^{-k}$ bound ($1.5625\%$ at $k=6$; $z = 0.026$). | Does not prove protection against learners employing structured inductive biases. |
| **`exp_learner_bots`** | Claim Boundary & Extensibility | State-merging (RPNI) and small-state enumerators achieve 0% to 15% pass rates depending on level complexity and sample coverage. | Does not guarantee 0% pass rate against all possible learning algorithms. Demonstrates why the scope statement is required. |
| **`exp_replay`** | Protocol State Invariants | Replay attempts (10/10), expired nonces (1/1), attempt-cap overflows (1/1), oversized payloads (1/1), and burst floods (5/5) are 100% blocked with distinct error codes. | Does not prevent distributed botnets using large pools of residential IP addresses from consuming rate-limit budgets. |
| **`exp_api_leak_check`** | Zero-Knowledge Secrecy | Zero leakage ($0$ bytes) of hidden regular expressions, DFA transition matrices, state counts, certificates, or test ground truth across all API endpoints. | Does not prevent timing side-channel attacks on sub-millisecond local network connections. |

---

## 3. Comprehensive Limitations Specification

VeriDyn's theoretical guarantees and operational limitations are structured into three distinct categories:

### (a) Out of Scope by Design
1. **Passive and Active Grammatical Learners Outside $\mathcal{H}$:**
   - Algorithms such as RPNI (Regular Positive and Negative Inference), OSTIA, genetic inductive algorithms, and SAT-based DFA solvers operate outside the candidate hypothesis class $\mathcal{H}$. When an observation sample $E^+, E^-$ uniquely characterizes a simple regular language, an unconstrained learner can infer the target concept.
2. **Large Language Models (LLMs) and Neural In-Context Learners:**
   - Pre-trained transformer architectures with large context windows can recognize sequential syntactic patterns. LLMs are explicitly excluded from the certified hardness claim.
3. **Identity Verification & "Bot Detection":**
   - VeriDyn does **not** verify that a respondent is a biological human. Verdicts are strictly `"Challenge passed"` or `"Challenge failed"`. The words `"human"`, `"verified"`, and `"bot detected"` are strictly prohibited across all APIs and documentation.

### (b) Mitigated with Measured Bounds
1. **Brute-Force Random Guessing:**
   - *Mitigation:* Fixed test string count $k = 6$ bounds the random pass probability at $2^{-6} = 0.015625$ ($\approx 1.56\%$).
2. **Replay and Pre-Computation Attacks:**
   - *Mitigation:* Single-use cryptographic nonces (`secrets.token_urlsafe(32)`) with a strict 120-second TTL. Replaying a previously observed valid answer vector is immediately rejected with `NONCE_ALREADY_USED`.
3. **Session Exhaustion & Brute-Force Enumeration:**
   - *Mitigation:* Maximum 3 attempts per session. Upon 3 failures, the session is invalidated (`SESSION_ATTEMPTS_EXHAUSTED`). Each attempt issues a freshly synthesized challenge.
4. **Denial of Service & Buffer Overflow:**
   - *Mitigation:* Sliding-window rate limiter enforces 30 requests/minute per client IP (`RATE_LIMIT_EXCEEDED`). Request payloads enforce an 8-character response length cap per symbol string.
5. **AST & Automata State Explosion:**
   - *Mitigation:* Regex length capped at $\le 80$ characters; repetition bounds capped at $m, n \le 6$; DFA state caps enforced per level ($\le 6, 8, 10, 12, 20$).

### (c) Partially Addressed
1. **Under-Constrained Sample Ambiguity at Low Difficulty Levels:**
   - In Level 1 and Level 2, an observation set of $N_{ex} = 6$ examples can occasionally coincide with small-state quotients discovered by brute-force state enumerators (as measured in `exp_learner_bots`, where small-DFA enumeration achieved up to a 15% pass rate).
2. **Cognitive Load on Symmetric Difference (Level 5):**
   - High-state parity and XOR languages ($h_1 \oplus h_2$) present substantial cognitive load for human respondents within a 120-second window. The pilot survey (`docs/pilot_survey.md`) is specifically designed to quantify human solve rates and completion times on these higher difficulty tiers.
