"""Unit and property tests for veridyn.core.regex_parser."""

import pytest
from hypothesis import given, settings, strategies as st

from veridyn.core.regex_parser import (
    ASTNode,
    Concat,
    Epsilon,
    Plus,
    Question,
    RegexSyntaxError,
    Repeat,
    Star,
    Symbol,
    Union,
    desugar,
    parse,
    to_string,
)

# ==============================================================================
# 1. Parse -> Print -> Parse Equality Tests (25+ diverse regexes)
# ==============================================================================

VALID_REGEXES = [
    # Basic symbols
    "C",
    "T",
    "S",
    # Basic Concatenation
    "CT",
    "CTS",
    "CCC",
    "TCST",
    # Basic Union (Alternation)
    "C|T",
    "C|T|S",
    "CT|SC",
    "C|TT|SSS",
    # Kleene Star
    "C*",
    "C*T*",
    "(CT)*",
    "(C|T)*",
    "((C|T)*S)*",
    # Plus quantifier
    "C+",
    "(CT)+",
    "(C|T|S)+",
    "C+T+S+",
    # Question quantifier
    "C?",
    "(CT)?",
    "(C|T)?S",
    "C?T?S?",
    # Exact repetition {m}
    "C{3}",
    "(CT){2}",
    "(C|T){4}",
    # Range repetition {m,n}
    "C{1,3}",
    "(CT){2,4}",
    "(C|T){0,2}",
    # Open range repetition {m,}
    "C{2,}",
    "(CT){1,}",
    "(C|S){0,}",
    # Complex combinations and nesting
    "C{1,2}T{2,3}|S+",
    "(C|T?)*S{2}",
    "((C|T)*S)+|(T|S){1,2}",
    "C(T|S(C|T*))",
    "(C|T)*S(C|T)*",
]


@pytest.mark.parametrize("regex_str", VALID_REGEXES)
def test_parse_print_parse_equality(regex_str: str) -> None:
    """Verify that parsing a regex, formatting it to string, and re-parsing yields an equal AST."""
    ast1 = parse(regex_str)
    printed = to_string(ast1)
    ast2 = parse(printed)
    assert ast1 == ast2, f"Failed round-trip for '{regex_str}': printed='{printed}'"
    # Also verify that stringifying ast2 reproduces the exact canonical printed string
    assert to_string(ast2) == printed


# ==============================================================================
# 2. Malformed Inputs Table (Only RegexSyntaxError is raised with position)
# ==============================================================================

MALFORMED_INPUTS = [
    # (input_string, expected_error_substring)
    ("", "Empty regex"),
    ("X", "Unknown symbol 'X'"),
    ("C1", "Unknown symbol '1'"),
    ("C#T", "Unknown symbol '#'"),
    ("C T", "Unknown symbol ' '"),
    ("c", "Unknown symbol 'c'"),
    # Parentheses issues
    ("(C", "Unclosed parenthesis"),
    ("((C|T)", "Unclosed parenthesis"),
    ("C)", "Unexpected closing parenthesis"),
    (")", "Unexpected closing parenthesis"),
    ("()", "Empty group"),
    ("(())", "Empty group"),
    # Union alternatives
    ("|", "Empty alternative"),
    ("|C", "Empty alternative"),
    ("C|", "Empty alternative"),
    ("C||T", "Empty alternative"),
    ("(C|)", "Empty alternative"),
    ("(|C)", "Empty alternative"),
    # Missing preceding atom for quantifiers
    ("*", "Quantifier '*' without preceding atom"),
    ("*C", "Quantifier '*' without preceding atom"),
    ("+", "Quantifier '+' without preceding atom"),
    ("+C", "Quantifier '+' without preceding atom"),
    ("?", "Quantifier '?' without preceding atom"),
    ("?T", "Quantifier '?' without preceding atom"),
    ("{2}", "Quantifier '{' without preceding atom"),
    # Repetition bound syntax issues
    ("C{}", "Empty repetition bounds"),
    ("C{,}", "Invalid lower repetition bound"),
    ("C{,2}", "Invalid lower repetition bound"),
    ("C{1,2,3}", "Invalid repetition bounds"),
    ("C{abc}", "Invalid repetition bound"),
    ("C{-1}", "Invalid repetition bound"),
    ("C{2", "Unclosed '{' in repetition bound"),
    ("C{2,3", "Unclosed '{' in repetition bound"),
    # Bounds exceeding cap (max 6)
    ("C{7}", "exceeds maximum limit of 6"),
    ("C{1,7}", "exceeds maximum limit of 6"),
    ("C{8,}", "exceeds maximum limit of 6"),
    # Inverted range bounds (lower > upper)
    ("C{3,2}", "exceeds upper bound"),
    ("C{5,1}", "exceeds upper bound"),
    # Exceeding regex length cap (80)
    ("C" * 81, "exceeds limit of 80"),
]


@pytest.mark.parametrize("bad_input,expected_sub", MALFORMED_INPUTS)
def test_malformed_inputs_raise_regex_syntax_error(bad_input: str, expected_sub: str) -> None:
    """Verify that malformed inputs raise RegexSyntaxError (and no other exception) with valid position."""
    with pytest.raises(RegexSyntaxError) as exc_info:
        parse(bad_input)

    err = exc_info.value
    assert isinstance(err, RegexSyntaxError)
    assert err.position is not None
    assert err.position >= 0
    assert expected_sub.lower() in err.message.lower()


# ==============================================================================
# 3. Equivalence of C{1,2}T and (C|CC)T under Desugaring
# ==============================================================================

def test_desugar_c12t_and_c_or_cc_t_equivalently() -> None:
    """Verify that C{1,2}T and (C|CC)T desugar to identical core AST structures.

    Theoretical Justification:
    --------------------------
    1. C{1,2} denotes the regular language L = { C^k | 1 <= k <= 2 } = { "C", "CC" }.
    2. During desugaring, Repeat(Symbol('C'), min_count=1, max_count=2) expands into
       the union of its constituent bounded power terms:
           Union(Symbol('C'), Concat(Symbol('C'), Symbol('C')))
    3. The alternative regular expression "(C|CC)" parses directly into:
           Union(Symbol('C'), Concat(Symbol('C'), Symbol('C')))
    4. When concatenated with Symbol('T') on the right, both expressions yield
       the identical core AST structure:
           Concat(
               Union(Symbol('C'), Concat(Symbol('C'), Symbol('C'))),
               Symbol('T')
           )
    This proves that bounded range repetitions and explicit finite unions
    produce isomorphic canonical representations in the core regular algebra.
    """
    ast1 = parse("C{1,2}T")
    ast2 = parse("(C|CC)T")

    desugared1 = desugar(ast1)
    desugared2 = desugar(ast2)

    expected_core = Concat(
        Union(
            Symbol("C"),
            Concat(Symbol("C"), Symbol("C")),
        ),
        Symbol("T"),
    )

    assert desugared1 == expected_core
    assert desugared2 == expected_core
    assert desugared1 == desugared2


def test_desugar_removes_all_sugar_nodes() -> None:
    """Verify that desugar() strictly leaves only core AST nodes."""
    complex_sugar = parse("C+T?S{2,4}|(CT){2}|S{1,}")
    core_tree = desugar(complex_sugar)

    def assert_no_sugar(node: ASTNode) -> None:
        assert not isinstance(node, (Plus, Question, Repeat)), f"Found sugar node {type(node)}"
        if isinstance(node, Concat):
            assert_no_sugar(node.left)
            assert_no_sugar(node.right)
        elif isinstance(node, Union):
            assert_no_sugar(node.left)
            assert_no_sugar(node.right)
        elif isinstance(node, Star):
            assert_no_sugar(node.child)
        elif isinstance(node, (Symbol, Epsilon)):
            pass
        else:
            pytest.fail(f"Unexpected AST node: {type(node)}")

    assert_no_sugar(core_tree)


# ==============================================================================
# 4. Hypothesis Round-Trip Property-Based Tests
# ==============================================================================

# Strategy for generating arbitrary well-formed ASTs within VeriDyn caps
def symbol_strategy() -> st.SearchStrategy[ASTNode]:
    return st.sampled_from(["C", "T", "S"]).map(Symbol)


def ast_strategy() -> st.SearchStrategy[ASTNode]:
    def extend_tree(children: st.SearchStrategy[ASTNode]) -> st.SearchStrategy[ASTNode]:
        return st.one_of(
            st.builds(Star, children),
            st.builds(Plus, children),
            st.builds(Question, children),
            st.builds(
                lambda child, m, n: Repeat(child, m, n),
                children,
                st.integers(min_value=0, max_value=6),
                st.one_of(st.none(), st.integers(min_value=0, max_value=6)),
            ).filter(lambda r: r.max_count is None or r.min_count <= r.max_count),
            st.builds(Concat, children, children),
            st.builds(Union, children, children),
        )

    return st.recursive(symbol_strategy(), extend_tree, max_leaves=8)


@given(ast_strategy())
@settings(max_examples=100)
def test_hypothesis_ast_roundtrip(ast: ASTNode) -> None:
    """Property test: Formatting an arbitrary AST to a string and re-parsing preserves string form and semantics."""
    rendered = to_string(ast)
    if len(rendered) <= 80:
        parsed = parse(rendered, alphabet={"C", "T", "S"})
        rendered_again = to_string(parsed)
        assert rendered == rendered_again
        # Parsing the re-rendered string should yield the exact same parsed AST
        reparsed = parse(rendered_again, alphabet={"C", "T", "S"})
        assert parsed == reparsed
