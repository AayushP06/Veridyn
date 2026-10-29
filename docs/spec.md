# VeriDyn: Formal Specification

## Scope Statement

> "VeriDyn certifies that no guessing strategy in a stated hypothesis class passes the challenge. It does NOT verify that a respondent is human. Learners, programs and language models outside that class are not covered."

---

## 1. Formal Definitions

### 1.1 Alphabet ($\Sigma$)
An **alphabet** $\Sigma$ is a finite, non-empty set of distinct symbols.
* **Default Alphabet:** $\Sigma = \{C, T, S\}$.
* The set of all finite-length strings formed from $\Sigma$ is denoted $\Sigma^*$, with empty string denoted $\varepsilon$.

### 1.2 Language ($L$)
A **language** $L \subseteq \Sigma^*$ is a subset of strings over $\Sigma$. In VeriDyn, all languages considered are **regular languages**, recognizable by Deterministic Finite Automata (DFA) and expressible via regular expressions.

### 1.3 Hypothesis Library ($\mathcal{H}$)
The **hypothesis library** $\mathcal{H} = \{h_1, h_2, \dots, h_m\}$ is a finite, explicitly specified collection of candidate regular languages ($m \ge 30$).
* Each hypothesis $h \in \mathcal{H}$ is represented as a complete DFA over $\Sigma$.
* Hypotheses are generated from an atomic property family $\mathcal{A}$ covering:
  - Prefix constraints: starts with $X$
  - Suffix constraints: ends with $X$
  - Substring constraints: contains $X$, contains $XX$, avoids $XX$
  - Parity and modular counts: count of $X$ is even/odd, count of $X \equiv r \pmod 3$
  - String length properties: length parity (even/odd), length $\le k$, length $\ge k$
  - Complement/negation of any of the above.
* $\mathcal{H}$ is treated strictly as external data and is not hardcoded into the verification algorithms.

### 1.4 Hidden Target Rule ($R$)
The **hidden rule** $R$ is a regular language $L(R) \subseteq \Sigma^*$ generated on the server:
* $R$ is formed as a Boolean combination (using intersection $\cap$, union $\cup$, and complementation $\neg$) of at most 2 atomic rules from the atom set of $\mathcal{H}$.
* **Separation Constraint:** The hidden rule must **not** be equivalent to any single member of $\mathcal{H}$:
  $$\forall h \in \mathcal{H}, \quad L(R) \neq L(h)$$
* $R$, its defining regular expression, its DFA, and the transition table remain strictly confidential on the server.

### 1.5 Challenge ($C$)
A **challenge** is a tuple:
$$C = (E^+, E^-, T)$$
where:
* $E^+ \subset L(R)$ is a set of positive (accepted) example strings ($|E^+| = 3$, length $2 \le |w| \le 6$).
* $E^- \subset (\Sigma^* \setminus L(R))$ is a set of negative (rejected) example strings ($|E^-| = 3$, length $2 \le |w| \le 6$).
* $T = \{t_1, t_2, \dots, t_k\}$ is an ordered set of unlabelled test strings ($k = 6$, balanced with 3 positive and 3 negative strings with respect to $L(R)$, lengths $|t_i| \le 8$).

### 1.6 Consistency and Certificate
Let $\mathcal{H}_{\text{cons}} \subseteq \mathcal{H}$ be the set of hypotheses in $\mathcal{H}$ that are consistent with the presented examples $(E^+, E^-)$:
$$\mathcal{H}_{\text{cons}} = \{ h \in \mathcal{H} \mid E^+ \subseteq L(h) \land E^- \cap L(h) = \emptyset \}$$

A challenge $C = (E^+, E^-, T)$ is **certified** if for every consistent hypothesis $h \in \mathcal{H}_{\text{cons}}$, there exists at least one test string $t \in T$ on which $h$ and the hidden rule $R$ disagree:
$$\forall h \in \mathcal{H}_{\text{cons}}, \exists t \in T \quad \text{s.t.} \quad \mathbb{I}_{L(h)}(t) \neq \mathbb{I}_{L(R)}(t)$$
where $\mathbb{I}_L(w) = 1$ if $w \in L$ and $0$ otherwise.

The **certificate** is the witness mapping $\operatorname{cert}: \mathcal{H}_{\text{cons}} \to T$ assigning each consistent candidate $h$ a witness test string $t \in T$ where $h$ fails.

### 1.7 "Challenge Passed"
Let $\mathbf{y} = (y_1, y_2, \dots, y_k) \in \{0, 1\}^k$ be the classification submitted by the respondent for test strings $(t_1, \dots, t_k)$.
* The verdict is **"Challenge passed"** if and only if:
  $$\forall i \in \{1, \dots, k\}, \quad y_i = \mathbb{I}_{L(R)}(t_i)$$
* Otherwise, the verdict is **"Challenge failed"**.
* A random coin-flipping respondent passes a balanced $k$-string challenge with probability exactly $2^{-k}$ (for $k=6$, $p = 1/64 \approx 0.0156$).

---

## 2. Regular Expression Grammar (BNF)

VeriDyn implements its own parser and AST for regular expressions supporting standard regular operators and bounded counts.

```bnf
<regex>        ::= <term> '|' <regex>
                 | <term>

<term>         ::= <factor> <term>
                 | <factor>
                 | ε

<factor>       ::= <base> <quantifier>
                 | <base>

<quantifier>   ::= '*'
                 | '+'
                 | '?'
                 | '{' <number> '}'
                 | '{' <number> ',' '}'
                 | '{' <number> ',' <number> '}'

<base>         ::= <char>
                 | '(' <regex> ')'

<char>         ::= 'C' | 'T' | 'S'
<number>       ::= [0-9]+
```

### Precedence Rules (Highest to Lowest):
1. Parentheses: `( ... )`
2. Quantifiers / Repetition: `*`, `+`, `?`, `{m,n}`, `{m}`, `{m,}`
3. Concatenation
4. Alternation: `|`

---

## 3. Parameter Caps and Complexity Bounds

| Parameter | Cap / Bound | Rationale |
|:---|:---|:---|
| Regex string length | $\le 80$ characters | Prevents runaway AST explosion |
| Repetition bound $m, n$ | $\le 6$ | Limits state multiplication during NFA expansion |
| Alphabet size $|\Sigma|$ | 3 symbols ($\{C, T, S\}$) | Balances combinatorial search space and human readability |
| Example string length | $2 \le |w| \le 6$ | Short enough for human inspection, informative enough for induction |
| Example count $N_{ex}$ | 6 (3 positive, 3 negative) | Keeps UI readable and uncluttered |
| Test string count $k$ | 6 (3 positive, 3 negative) | $2^{-6} = 0.0156$ brute-force random guessing bound |
| Test string length | $\le 8$ symbols | Ensures tractability of distinguishing words |
| Response payload length | $\le 8$ symbols per string | Security guard against buffer/payload abuse |

---

## 4. Decisions and Defaults

* **Alphabet:** Fixed default $\Sigma = \{C, T, S\}$. Custom alphabets can be parameterized if specified in tests.
* **DFA Completeness:** All DFAs are strictly complete. Every state has an explicit transition defined for every symbol $a \in \Sigma$, including an explicit sink / dead state when transitions are not accepting.
* **Server-Side Secrecy:** The hidden rule $R$, its regex representation, its state graph, and the certifier matrix remain server-side. The API returns strictly:
  - Example strings $E^+$ and $E^-$
  - Unlabelled test strings $T$
  - Session nonces
* **Fixed UI Terminology:**
  - Verdicts are strictly `"Challenge passed"` or `"Challenge failed"`.
  - Words such as `"human"`, `"verified"`, or `"bot detected"` are prohibited in UI and API responses.
* **Session Guard Defaults:**
  - Nonce expiry: 120 seconds.
  - Nonce policy: One-time use (consumed on verification attempt).
  - Attempt limit: 3 attempts per session. Each new attempt generates a fresh challenge.
  - Rate limit: 30 requests per minute per IP address.
* **Differential Testing Oracle:** Python's standard `re.fullmatch` is utilized exclusively in test suites to validate NFA/DFA language equivalence over all $\Sigma^{\le 8}$.

---

## 5. Difficulty Levels Specification

VeriDyn structures inductive challenges into 5 difficulty levels based on the composition of regular primitives and minimal DFA state complexity:

| Level | Name | Atoms | Operation | Max Minimal States | Examples $N_{ex}$ | Tests $k$ | Description |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **1** | **Novice** | 1 | Atom outside $\mathcal{H}$ | $\le 6$ | 6 (3 pos, 3 neg) | 6 (3 pos, 3 neg) | Single atomic regular property not in $\mathcal{H}$ (e.g. 2/3-symbol prefix, suffix, substring, mod 3 count). |
| **2** | **Elementary** | 2 | Conjunction (`AND`) | $\le 8$ | 6 (3 pos, 3 neg) | 6 (3 pos, 3 neg) | Conjunction of two simple atomic properties from $\mathcal{H}$ ($h_1 \cap h_2$). |
| **3** | **Intermediate** | 2 | Difference (`AND NOT`) | $\le 10$ | 6 (3 pos, 3 neg) | 6 (3 pos, 3 neg) | Difference of two atomic properties from $\mathcal{H}$ ($h_1 \setminus h_2$). |
| **4** | **Advanced** | 2 | Disjunction (`OR`) | $\le 12$ | 6 (3 pos, 3 neg) | 6 (3 pos, 3 neg) | Disjunction of two distinct atomic properties from $\mathcal{H}$ ($h_1 \cup h_2$). |
| **5** | **Expert** | 2 | Symmetric Diff (`XOR`) | $\le 20$ | 6 (3 pos, 3 neg) | 6 (3 pos, 3 neg) | Symmetric difference / modular parity combinations ($h_1 \oplus h_2$). |

