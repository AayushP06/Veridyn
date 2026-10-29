# VeriDyn: Threat Model & Limitation Analysis

## Mandatory Scope Statement

> "VeriDyn certifies that no guessing strategy in a stated hypothesis class passes the challenge. It does NOT verify that a respondent is human. Learners, programs and language models outside that class are not covered."

---

## 1. Limitations & Mitigations Matrix

The table below outlines the core security assumptions, systemic limitations, and the concrete mitigations or empirical measurements provided by VeriDyn.

| ID | Limitation | Status | What the Project Does | Evidence to Produce |
|:---|:---|:---:|:---|:---|
| **(a)** | **Guessers outside $\mathcal{H}$ are not covered** | `mitigated` | Explicitly confines certificates to the hypothesis library $\mathcal{H}$. Challenges are certified mathematically against every $h \in \mathcal{H}_{\text{cons}}$. Communicates boundaries through mandatory UI/spec scope statement. | Certificate generation audit logging; unit test demonstrating that for every $h \in \mathcal{H}_{\text{cons}}$, $\exists t \in T$ with differing label. |
| **(b)** | **Learners such as state-merging (RPNI) or $L^*$ may solve it** | `measured` | Restricts information available: $N_{ex} = 6$ strings is insufficient for exact DFA identification via passive state-merging (RPNI). Respondent is denied an active membership oracle (no interactive queries), blocking active learning algorithms like Angluin's $L^*$. | Empirical evaluation running RPNI and prefix-tree acceptors over sample challenges to measure empirical recovery rate. |
| **(c)** | **Language models may solve it** | `measured` | Generates rule combinations programmatically with diverse token alphabets to prevent reliance on pre-trained memorization. Evaluates LLM prompting strategies against certified challenges. | Experiment benchmark running zero-shot and few-shot LLM prompts against 100 sample challenges, recording pass rate vs. random baseline ($2^{-6}$). |
| **(d)** | **Replay and session abuse** | `mitigated` | Enforces single-use cryptographically random session nonces, strict 120-second time-to-live (TTL), per-IP rate limiting (30 requests/minute), and session cap of 3 attempts with fresh challenges per attempt. | Automated tests verifying nonce invalidation after use, expiration after 120s, and 429 rate-limit responses under burst traffic. |
| **(e)** | **Timing is never used for verdicts** | `mitigated` | Verdicts depend strictly and exclusively on whether submitted classifications match ground truth ($y_i = \mathbb{I}_{L(R)}(t_i)$). Response latency and interaction speed are completely ignored in pass/fail logic. | Unit tests proving identical verdict output regardless of artificial delays introduced between challenge issuance and submission. |
| **(f)** | **Accessibility is basic** | `unresolved` | Implements semantic HTML, high-contrast readable text strings, keyboard navigation, and text equivalents for tile representations. However, cognitive induction load and screen reader optimization are not comprehensively audited. | Accessibility audit notes; documentation acknowledging cognitive load limitations for visually or cognitively impaired users. |
| **(g)** | **Hidden rule must be solvable by humans** | `measured` | Limits hidden rule complexity to at most 2 atomic properties from $\mathcal{H}$, bound string lengths to $2 \le |w| \le 6$ for examples, and guarantees balanced test strings (3 positive, 3 negative). | User study / trial logs showing human solve times and completion rates on standard 6-example challenges. |

---

## 2. What a Pass Does NOT Prove

A verdict of **"Challenge passed"** is a narrow, mathematically well-defined statement with strict theoretical boundaries. It is vital to state explicitly what passing does **not** prove:

1. **It does NOT prove the respondent is human:**
   VeriDyn is an inductive capability test against a defined hypothesis class, not a Turing test or proof of human presence. Any system or program executing an algorithm outside $\mathcal{H}$ (e.g., heuristic program synthesis, sat-solvers, neural networks, or lucky random guessers) may pass.
2. **It does NOT prove resilience against strategies outside $\mathcal{H}$:**
   The certificate guarantees only that no hypothesis $h \in \mathcal{H}$ that matches all shown examples can correctly label all test strings. If a solver considers hypotheses $\mathcal{H}' \not\subseteq \mathcal{H}$, the certificate provides zero security guarantees against $\mathcal{H}'$.
3. **It does NOT prove zero probability of random guessing success:**
   For a balanced test of $k = 6$ strings, an entity flipping an unbiased coin has an exact probability of:
   $$P(\text{pass by chance}) = 2^{-6} = \frac{1}{64} \approx 1.56\%$$
   Passing can occur purely by stochastic chance.
4. **It does NOT prove complete rule identification:**
   A respondent does not need to learn the full minimal DFA of the hidden rule $R$. They only need to correctly classify the $k=6$ specific test strings selected for the challenge instance.
5. **It does NOT prove immunity to automated learners:**
   Given sufficient computational resources or alternative inductive biases (such as minimum description length heuristics or grammar induction), automated systems might consistently classify the test strings correctly.
