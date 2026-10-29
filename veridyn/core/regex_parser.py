"""Regular expression parsing, AST representation, and desugaring.

TOC Concept: Context-Free Grammars (CFG), Recursive-Descent Parsing,
Abstract Syntax Trees (AST), and Syntactic Desugaring into Core Regular Operators.
"""

from __future__ import annotations

from collections.abc import Container
from dataclasses import dataclass

# ==============================================================================
# Grammar Specification & Theoretical Foundations
# ==============================================================================
#
# Context-Free Grammar (CFG) for VeriDyn Regular Expressions:
#
#   regex      := union
#   union      := concat ('|' concat)*
#   concat     := repeat+
#   repeat     := atom (quantifier)*
#   atom       := SYMBOL | '(' regex ')'
#   quantifier := '*' | '+' | '?' | '{' BOUNDS '}'
#
# TOC Note:
# Although regular expressions describe Chomsky Type-3 (regular) languages, the
# syntax of regular expressions with balanced parentheses is itself a CONTEXT-FREE
# language (Chomsky Type-2). Specifically, matching nested parentheses:
#     L_paren = { (ⁿ C )ⁿ | n >= 1 }
# cannot be recognized by any finite automaton by the Pumping Lemma for Regular
# Languages. A pushdown automaton or a recursive-descent parser (utilizing an
# execution stack) is therefore required to parse regular expressions.
# ==============================================================================

DEFAULT_ALPHABET: frozenset[str] = frozenset({"C", "T", "S"})
MAX_REGEX_LENGTH: int = 80
MAX_REPETITION_BOUND: int = 6


class RegexSyntaxError(ValueError):
    """Exception raised when regular expression parsing fails.

    Attributes:
        message: Description of the syntax violation.
        position: 0-based character index where the error was detected.
    """

    def __init__(self, message: str, position: int | None = None) -> None:
        super().__init__(f"{message} at position {position}" if position is not None else message)
        self.message = message
        self.position = position


# ==============================================================================
# AST Node Hierarchy
# ==============================================================================

class ASTNode:
    """Base class for all regular expression AST nodes."""
    pass


# Core AST nodes (minimal regular language basis)

@dataclass(frozen=True)
class Symbol(ASTNode):
    """Literal alphabet symbol."""
    char: str


@dataclass(frozen=True)
class Epsilon(ASTNode):
    """Empty string (epsilon)."""
    pass


@dataclass(frozen=True)
class Concat(ASTNode):
    """Concatenation of two regular expressions (left followed by right)."""
    left: ASTNode
    right: ASTNode


@dataclass(frozen=True)
class Union(ASTNode):
    """Alternation of two regular expressions (left or right)."""
    left: ASTNode
    right: ASTNode


@dataclass(frozen=True)
class Star(ASTNode):
    """Kleene star closure (zero or more repetitions)."""
    child: ASTNode


# Syntactic Sugar AST nodes

@dataclass(frozen=True)
class Plus(ASTNode):
    """Positive closure (one or more repetitions)."""
    child: ASTNode


@dataclass(frozen=True)
class Question(ASTNode):
    """Optional quantifier (zero or one occurrence)."""
    child: ASTNode


@dataclass(frozen=True)
class Repeat(ASTNode):
    """Bounded repetition quantifier.

    min_count: Lower bound of occurrences (>= 0).
    max_count: Upper bound of occurrences (None denotes unbounded {m,}).
    """
    child: ASTNode
    min_count: int
    max_count: int | None


# ==============================================================================
# Recursive-Descent Parser Implementation
# ==============================================================================

class _Parser:
    """Internal recursive-descent parser state machine."""

    def __init__(
        self,
        text: str,
        alphabet: frozenset[str],
        max_repetition_bound: int = MAX_REPETITION_BOUND,
    ) -> None:
        self.text = text
        self.alphabet = alphabet
        self.max_repetition_bound = max_repetition_bound
        self.pos = 0
        self.length = len(text)

    def _peek(self) -> str | None:
        return self.text[self.pos] if self.pos < self.length else None

    def _consume(self) -> str:
        ch = self.text[self.pos]
        self.pos += 1
        return ch

    def _match(self, expected: str) -> bool:
        if self._peek() == expected:
            self.pos += 1
            return True
        return False

    def parse(self) -> ASTNode:
        if self.length > MAX_REGEX_LENGTH:
            raise RegexSyntaxError(
                f"Regex length {self.length} exceeds limit of {MAX_REGEX_LENGTH}",
                position=MAX_REGEX_LENGTH,
            )
        if self.length == 0:
            raise RegexSyntaxError("Empty regex is not allowed", position=0)

        node = self._parse_regex()
        if self.pos < self.length:
            trailing = self._peek()
            if trailing == ")":
                raise RegexSyntaxError("Unexpected closing parenthesis ')'", position=self.pos)
            raise RegexSyntaxError(f"Unexpected trailing character '{trailing}'", position=self.pos)
        return node

    def _parse_regex(self) -> ASTNode:
        return self._parse_union()

    def _parse_union(self) -> ASTNode:
        if self._peek() == "|":
            raise RegexSyntaxError("Empty alternative before '|'", position=self.pos)

        left = self._parse_concat()
        while self._match("|"):
            if self._peek() in {"|", ")", None}:
                raise RegexSyntaxError("Empty alternative in union", position=self.pos)
            right = self._parse_concat()
            left = Union(left, right)
        return left

    def _parse_concat(self) -> ASTNode:
        repeats = [self._parse_repeat()]
        while self._peek() is not None and self._peek() not in {"|", ")"}:
            repeats.append(self._parse_repeat())

        node = repeats[0]
        for r in repeats[1:]:
            node = Concat(node, r)
        return node

    def _parse_repeat(self) -> ASTNode:
        node = self._parse_atom()
        while self._peek() in {"*", "+", "?", "{"}:
            node = self._parse_quantifier(node)
        return node

    def _parse_quantifier(self, node: ASTNode) -> ASTNode:
        ch = self._peek()
        if ch == "*":
            self._consume()
            return Star(node)
        if ch == "+":
            self._consume()
            return Plus(node)
        if ch == "?":
            self._consume()
            return Question(node)
        if ch == "{":
            return self._parse_bounds(node)
        raise RegexSyntaxError(f"Unexpected quantifier '{ch}'", position=self.pos)

    def _parse_bounds(self, node: ASTNode) -> ASTNode:
        start_pos = self.pos
        self._consume()  # consume '{'
        end_brace = self.text.find("}", self.pos)
        if end_brace == -1:
            raise RegexSyntaxError("Unclosed '{' in repetition bound", position=start_pos)

        content = self.text[self.pos:end_brace]
        self.pos = end_brace + 1  # advance past '}'

        if not content:
            raise RegexSyntaxError("Empty repetition bounds '{}'", position=start_pos)

        if "," not in content:
            if not content.isdigit():
                raise RegexSyntaxError(f"Invalid repetition bound '{content}'", position=start_pos)
            m = int(content)
            if m > self.max_repetition_bound:
                raise RegexSyntaxError(
                    f"Repetition bound {m} exceeds maximum limit of {self.max_repetition_bound}",
                    position=start_pos,
                )
            return Repeat(node, m, m)
        else:
            parts = content.split(",")
            if len(parts) != 2:
                raise RegexSyntaxError(f"Invalid repetition bounds '{{{content}}}'", position=start_pos)
            m_str, n_str = parts[0], parts[1]
            if not m_str.isdigit():
                raise RegexSyntaxError(f"Invalid lower repetition bound '{m_str}'", position=start_pos)
            m = int(m_str)
            if m > self.max_repetition_bound:
                raise RegexSyntaxError(
                    f"Lower repetition bound {m} exceeds maximum limit of {self.max_repetition_bound}",
                    position=start_pos,
                )

            if n_str == "":
                return Repeat(node, m, None)
            else:
                if not n_str.isdigit():
                    raise RegexSyntaxError(f"Invalid upper repetition bound '{n_str}'", position=start_pos)
                n = int(n_str)
                if n > self.max_repetition_bound:
                    raise RegexSyntaxError(
                        f"Upper repetition bound {n} exceeds maximum limit of {self.max_repetition_bound}",
                        position=start_pos,
                    )
                if m > n:
                    raise RegexSyntaxError(
                        f"Lower repetition bound {m} exceeds upper bound {n}",
                        position=start_pos,
                    )
                return Repeat(node, m, n)

    def _parse_atom(self) -> ASTNode:
        pos = self.pos
        ch = self._peek()
        if ch is None:
            raise RegexSyntaxError("Unexpected end of pattern", position=pos)
        if ch == "(":
            self._consume()
            if self._peek() == ")":
                raise RegexSyntaxError("Empty group '()' is not allowed", position=self.pos)
            inner = self._parse_regex()
            if self._peek() != ")":
                raise RegexSyntaxError("Unclosed parenthesis '('", position=pos)
            self._consume()  # consume ')'
            return inner
        if ch == ")":
            raise RegexSyntaxError("Unexpected closing parenthesis ')'", position=pos)
        if ch in {"*", "+", "?", "{"}:
            raise RegexSyntaxError(f"Quantifier '{ch}' without preceding atom", position=pos)
        if ch == "|":
            raise RegexSyntaxError("Empty alternative before '|'", position=pos)
        if ch in self.alphabet:
            self._consume()
            return Symbol(ch)
        raise RegexSyntaxError(f"Unknown symbol '{ch}' not in alphabet", position=pos)


def parse(
    text: str,
    alphabet: Container[str] | None = None,
    max_repetition_bound: int = MAX_REPETITION_BOUND,
) -> ASTNode:
    """Parse a regular expression string into an AST.

    Args:
        text: Regular expression string.
        alphabet: Allowed terminal characters. Defaults to {'C', 'T', 'S'}.
        max_repetition_bound: Maximum allowable bound for repetition quantifiers. Defaults to 6.

    Returns:
        ASTNode representing the parsed regular expression.

    Raises:
        RegexSyntaxError: If the input is malformed, uses unknown symbols,
            has unbalanced parentheses or braces, bad repetition bounds,
            empty groups/branches, or exceeds the length limit.
    """
    alpha = frozenset(alphabet) if alphabet is not None else DEFAULT_ALPHABET
    parser = _Parser(text, alpha, max_repetition_bound=max_repetition_bound)
    return parser.parse()


# ==============================================================================
# AST Stringification (to_string)
# ==============================================================================

def _prec(node: ASTNode) -> int:
    if isinstance(node, Union):
        return 0
    if isinstance(node, Concat):
        return 1
    if isinstance(node, (Star, Plus, Question, Repeat)):
        return 2
    if isinstance(node, (Symbol, Epsilon)):
        return 3
    raise TypeError(f"Unknown AST node type: {type(node)}")


def _to_str_child(child: ASTNode, parent_prec: int, is_right: bool = False) -> str:
    child_p = _prec(child)
    text = to_string(child)
    if child_p < parent_prec:
        return f"({text})"
    if child_p == parent_prec:
        # Parentheses preserve right-associativity differences in Concat and Union,
        # and prevent ambiguous quantifier chaining at level 2.
        if is_right or parent_prec == 2:
            return f"({text})"
    return text


def to_string(ast: ASTNode) -> str:
    """Format an AST node back into a canonical regular expression string.

    Minimal parentheses are added strictly as needed by operator precedence
    and associativity rules.
    """
    if isinstance(ast, Symbol):
        return ast.char
    if isinstance(ast, Epsilon):
        return ""
    if isinstance(ast, Star):
        child_str = _to_str_child(ast.child, parent_prec=2)
        return f"{child_str}*"
    if isinstance(ast, Plus):
        child_str = _to_str_child(ast.child, parent_prec=2)
        return f"{child_str}+"
    if isinstance(ast, Question):
        child_str = _to_str_child(ast.child, parent_prec=2)
        return f"{child_str}?"
    if isinstance(ast, Repeat):
        child_str = _to_str_child(ast.child, parent_prec=2)
        if ast.min_count == ast.max_count:
            return f"{child_str}{{{ast.min_count}}}"
        elif ast.max_count is None:
            return f"{child_str}{{{ast.min_count},}}"
        else:
            return f"{child_str}{{{ast.min_count},{ast.max_count}}}"
    if isinstance(ast, Concat):
        left_str = _to_str_child(ast.left, parent_prec=1, is_right=False)
        right_str = _to_str_child(ast.right, parent_prec=1, is_right=True)
        return f"{left_str}{right_str}"
    if isinstance(ast, Union):
        left_str = _to_str_child(ast.left, parent_prec=0, is_right=False)
        right_str = _to_str_child(ast.right, parent_prec=0, is_right=True)
        return f"{left_str}|{right_str}"
    raise TypeError(f"Unknown AST node type: {type(ast)}")


# ==============================================================================
# Syntactic Desugaring (desugar)
# ==============================================================================

def desugar(ast: ASTNode) -> ASTNode:
    """Rewrite syntactic sugar (+, ?, {m,n}, {m}, {m,}) into core regular operators.

    Core nodes: Symbol, Concat, Union, Star, Epsilon.
    """
    if isinstance(ast, (Symbol, Epsilon)):
        return ast
    if isinstance(ast, Star):
        return Star(desugar(ast.child))
    if isinstance(ast, Concat):
        return Concat(desugar(ast.left), desugar(ast.right))
    if isinstance(ast, Union):
        return Union(desugar(ast.left), desugar(ast.right))
    if isinstance(ast, Plus):
        d = desugar(ast.child)
        return Concat(d, Star(d))
    if isinstance(ast, Question):
        d = desugar(ast.child)
        return Union(d, Epsilon())
    if isinstance(ast, Repeat):
        d = desugar(ast.child)
        m = ast.min_count
        n = ast.max_count
        if n is None:
            # R{m,} -> R^m R*
            if m == 0:
                return Star(d)
            if m == 1:
                return Concat(d, Star(d))
            prefix = d
            for _ in range(m - 1):
                prefix = Concat(prefix, d)
            return Concat(prefix, Star(d))
        else:
            # R{m,n} where m <= n
            if m == n:
                if m == 0:
                    return Epsilon()
                if m == 1:
                    return d
                res = d
                for _ in range(m - 1):
                    res = Concat(res, d)
                return res
            else:
                # m < n: build terms R^k for k in [m, n]
                terms: list[ASTNode] = []
                for k in range(m, n + 1):
                    if k == 0:
                        terms.append(Epsilon())
                    elif k == 1:
                        terms.append(d)
                    else:
                        term = d
                        for _ in range(k - 1):
                            term = Concat(term, d)
                        terms.append(term)
                res = terms[0]
                for t in terms[1:]:
                    res = Union(res, t)
                return res
    raise TypeError(f"Unknown AST node type: {type(ast)}")


__all__ = [
    "ASTNode",
    "Symbol",
    "Epsilon",
    "Concat",
    "Union",
    "Star",
    "Plus",
    "Question",
    "Repeat",
    "RegexSyntaxError",
    "parse",
    "to_string",
    "desugar",
    "DEFAULT_ALPHABET",
    "MAX_REGEX_LENGTH",
    "MAX_REPETITION_BOUND",
]
