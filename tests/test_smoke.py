"""Smoke tests verifying package structure, imports, TOC docstrings, and documentation consistency."""

import importlib
from pathlib import Path
import re


def test_import_packages() -> None:
    """Verify that every package in VeriDyn can be imported successfully."""
    packages = [
        "veridyn",
        "veridyn.core",
        "veridyn.challenge",
        "veridyn.server",
        "experiments",
    ]
    for pkg in packages:
        mod = importlib.import_module(pkg)
        assert mod is not None, f"Failed to import package: {pkg}"


def test_import_all_modules() -> None:
    """Verify that every module defined in the project layout imports cleanly."""
    modules = [
        "veridyn.core.regex_parser",
        "veridyn.core.nfa",
        "veridyn.core.dfa",
        "veridyn.core.minimize",
        "veridyn.core.boolean_ops",
        "veridyn.core.distinguish",
        "veridyn.core.simulate",
        "veridyn.core.analyze",
        "veridyn.challenge.hypotheses",
        "veridyn.challenge.rules",
        "veridyn.challenge.generator",
        "veridyn.challenge.certify",
        "veridyn.server.app",
        "veridyn.server.session",
        "veridyn.server.guard",
        "veridyn.server.db",
    ]
    for mod_name in modules:
        mod = importlib.import_module(mod_name)
        assert mod is not None, f"Failed to import module: {mod_name}"
        assert mod.__doc__, f"Module {mod_name} missing docstring"
        assert "TOC Concept:" in mod.__doc__, f"Module {mod_name} docstring does not name TOC concept"


def test_scope_statement_in_required_locations() -> None:
    """Verify that the mandatory scope statement appears in README, docs, and web UI."""
    root = Path(__file__).resolve().parent.parent
    scope_phrase = (
        "VeriDyn certifies that no guessing strategy in a stated hypothesis class passes the challenge. "
        "It does NOT verify that a respondent is human. "
        "Learners, programs and language models outside that class are not covered."
    )

    targets = [
        root / "README.md",
        root / "docs" / "spec.md",
        root / "docs" / "threat_model.md",
        root / "web" / "index.html",
    ]

    for target in targets:
        assert target.exists(), f"File does not exist: {target}"
        content = target.read_text(encoding="utf-8")
        assert scope_phrase in content, f"Mandatory scope statement missing from {target.name}"


def test_threat_model_limitations_status() -> None:
    """Verify that limitations (a) through (g) are documented with valid status in threat_model.md."""
    root = Path(__file__).resolve().parent.parent
    threat_model = (root / "docs" / "threat_model.md").read_text(encoding="utf-8")

    expected_ids = ["(a)", "(b)", "(c)", "(d)", "(e)", "(f)", "(g)"]
    valid_statuses = {"mitigated", "measured", "unresolved"}

    for item_id in expected_ids:
        escaped_id = re.escape(item_id)
        # Search for row starting with | **(x)** | ... | `status` |
        match = re.search(
            rf"\|\s*\*\*{escaped_id}\*\*\s*\|[^|]+\|\s*`(mitigated|measured|unresolved)`\s*\|",
            threat_model,
        )
        assert match is not None, f"Limitation row {item_id} not found or missing valid status in docs/threat_model.md"
        status = match.group(1)
        assert status in valid_statuses, f"Invalid status '{status}' for limitation {item_id}"
