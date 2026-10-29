# VeriDyn Pilot Human Usability & Solvability Survey

> **Mandatory Scope Statement:**
> *"VeriDyn certifies that no guessing strategy in a stated hypothesis class passes the challenge. It does NOT verify that a respondent is human. Learners, programs and language models outside that class are not covered."*

---

## 1. Rationale: Why Human Pilot Testing Matters

In formal language induction and theoretical computer science, constructing certified challenges provides mathematical guarantees that **no hypothesis $h \in \mathcal{H}$ can pass the challenge**.

However, **certification is practically meaningless if human respondents cannot solve the challenge**.

An effective inductive challenge protocol must satisfy two complementary criteria:
1. **Adversarial Hardness:** Provably reject every candidate in the guessing hypothesis class $\mathcal{H}$ (pass rate strictly 0.00%).
2. **Human Solvability & Usability:** Enable human respondents using visual pattern recognition and inductive reasoning to infer the underlying regular language from $N_{ex} = 6$ labelled examples and correctly classify $k = 6$ test strings within reasonable cognitive effort and time.

If an inductive rule is so obscure or poorly presented that human solve rates drop toward random guessing ($2^{-k} \approx 1.56\%$), the protocol degenerates into an arbitrary barrier rather than an interactive proof of rule inference. This pilot survey measures whether human cognitive inductive reasoning succeeds under our presentation constraints.

---

## 2. Study Design & Participant Cohort

* **Cohort Size:** 8 to 15 participants.
* **Target Audience:** College students, researchers, and general computer users with varied technical backgrounds (mix of CS and non-CS disciplines).
* **Setting:** Desktop or laptop browser with keyboard and mouse/trackpad.
* **Protocol Duration:** 15–25 minutes per participant.
* **Ethics & Data Privacy:** All session data is anonymized; no personally identifiable information (PII) is stored.

---

## 3. Experimental Protocol

Each participant completes 5 consecutive challenges (one per difficulty level):
1. **Level 1 (Novice):** Single regular atomic property outside $\mathcal{H}$ (e.g. 2/3-symbol prefixes, suffixes, substrings).
2. **Level 2 (Elementary):** Conjunction (`AND`) of 2 regular properties from $\mathcal{H}$.
3. **Level 3 (Intermediate):** Difference (`AND NOT`) of 2 regular properties from $\mathcal{H}$.
4. **Level 4 (Advanced):** Disjunction (`OR`) of 2 regular properties from $\mathcal{H}$.
5. **Level 5 (Expert):** Symmetric difference (`XOR`) of 2 regular properties from $\mathcal{H}$.

Participants may use mouse or keyboard shortcuts (<kbd>&uarr;</kbd>/<kbd>&darr;</kbd>, <kbd>V</kbd>, <kbd>I</kbd>, <kbd>Enter</kbd>).

---

## 4. Participant Result Tracking Sheet

| Participant ID | Level | Solved? (Passed/Failed) | Attempts Used (1..3) | Completion Time (s) | Perceived Difficulty (1–5) | Input Mode Used (Mouse / Keyboard) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `P01` | L1 | Passed | 1 | 42s | 2 | Keyboard |
| `P01` | L2 | Passed | 1 | 58s | 3 | Keyboard |
| `P01` | L3 | Passed | 2 | 84s | 4 | Keyboard |
| `P01` | L4 | Passed | 1 | 67s | 3 | Keyboard |
| `P01` | L5 | Failed | 3 | 118s | 5 | Keyboard |
| *...* | *...* | *...* | *...* | *...* | *...* | *...* |

---

## 5. System Usability Scale (SUS) Questionnaire

Administered immediately following completion of the 5 challenges. Rated on a standard 5-point Likert scale (1 = Strongly Disagree, 5 = Strongly Agree):

1. **Q1:** I think that I would like to use this system frequently. `[ 1 | 2 | 3 | 4 | 5 ]`
2. **Q2:** I found the system unnecessarily complex. `[ 1 | 2 | 3 | 4 | 5 ]`
3. **Q3:** I thought the system was easy to use. `[ 1 | 2 | 3 | 4 | 5 ]`
4. **Q4:** I think that I would need the support of a technical person to be able to use this system. `[ 1 | 2 | 3 | 4 | 5 ]`
5. **Q5:** I found the various functions in this system were well integrated. `[ 1 | 2 | 3 | 4 | 5 ]`
6. **Q6:** I thought there was too much inconsistency in this system. `[ 1 | 2 | 3 | 4 | 5 ]`
7. **Q7:** I would imagine that most people would learn to use this system very quickly. `[ 1 | 2 | 3 | 4 | 5 ]`
8. **Q8:** I found the system very cumbersome to use. `[ 1 | 2 | 3 | 4 | 5 ]`
9. **Q9:** I felt very confident using the system. `[ 1 | 2 | 3 | 4 | 5 ]`
10. **Q10:** I needed to learn a lot of things before I could get going with this system. `[ 1 | 2 | 3 | 4 | 5 ]`

*Target Benchmark:* Composite SUS score $\ge 75$ (indicative of "Good" to "Excellent" usability).

---

## 6. Accessibility & Multi-Modal Perception Questions

Specific questions assessing WCAG 2.1 compliance and multi-modal symbol distinction:

1. **Shape vs. Color Distinction:**
   - *Question:* Were the symbols $\{C, T, S\}$ easily distinguishable by their geometric shapes (Circle, Triangle, Square) without relying on colors?
   - *Options:* `[ 1 - Not distinguishable | 3 - Neutral | 5 - Perfectly clear without color ]`

2. **Keyboard Operability:**
   - *Question:* How intuitive was the keyboard-only navigation (<kbd>&uarr;</kbd>/<kbd>&darr;</kbd> to navigate, <kbd>V</kbd>/<kbd>I</kbd> to classify, <kbd>Enter</kbd> to submit)?
   - *Options:* `[ 1 - Frustrating / Clunky | 3 - Acceptable | 5 - Extremely smooth & efficient ]`

3. **Cognitive Load of Examples:**
   - *Question:* Were $N_{ex} = 6$ examples (3 valid, 3 invalid) sufficient to discern the hidden pattern, or did you feel the observation set was too small?
   - *Options:* `[ 1 - Insufficient | 3 - Just right | 5 - More than enough ]`

4. **Visual Contrast & Typography:**
   - *Question:* Was the high-contrast dark theme and symbol badge typography clear and comfortable to read?
   - *Options:* `[ 1 - Poor readability | 3 - Acceptable | 5 - Excellent readability ]`

---

## 7. Pilot Evaluation Aggregate Report Template

```markdown
### Aggregate Pilot Findings (N = [8..15])
- Overall Challenge Solve Rate (within 3 attempts): [XX.X]%
  - Level 1 (Novice): [XX]%
  - Level 2 (Elementary): [XX]%
  - Level 3 (Intermediate): [XX]%
  - Level 4 (Advanced): [XX]%
  - Level 5 (Expert): [XX]%
- Median Completion Time per Challenge: [XX] seconds
- Mean System Usability Scale (SUS) Score: [XX.X] / 100
- Multi-Modal Accessibility Rating: [X.X] / 5.0
- Key Qualitative Feedback & Bottlenecks:
  1. [Participant observations on Level 5 XOR complexity...]
  2. [Feedback on keyboard navigation fluidity...]
```
