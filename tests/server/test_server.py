"""Integration and security tests for VeriDyn FastAPI server."""

import time
from fastapi.testclient import TestClient
import pytest

from veridyn.server.app import create_app
from veridyn.server.db import Database
from veridyn.server.guard import ErrorCode
from veridyn.server.session import ServerConfig


@pytest.fixture
def fresh_app():
    """Create an isolated test app instance with in-memory DB and distinct rate limiter."""
    config = ServerConfig(
        nonce_expiry_seconds=120.0,
        max_attempts_per_session=3,
        rate_limit_requests=30,
        rate_limit_window_seconds=60.0,
        response_length_cap=8,
        db_path=":memory:",
        allow_multiple_use=False,
    )
    db = Database(":memory:")
    app = create_app(config=config, db=db)
    return app


@pytest.fixture
def client(fresh_app):
    """Return a TestClient bound to the isolated test app."""
    return TestClient(fresh_app)


# ==============================================================================
# 1. Happy Path & Verdict Testing
# ==============================================================================

def test_happy_path_challenge_and_solve(client: TestClient, fresh_app) -> None:
    """Verify that a solver providing correct classifications receives 'Challenge passed'."""
    # 1. Request challenge
    resp = client.post("/api/challenge", json={"level": 1})
    assert resp.status_code == 200
    data = resp.json()

    assert "nonce" in data
    assert "session_id" in data
    assert len(data["examples"]) == 6
    assert len(data["tests"]) == 6
    assert data["expires_in"] == 120
    assert data["attempts_left"] == 3
    assert data["level"] == 1
    assert data["note"] == "This is a rule-inference check, not identity verification"

    # Verify example labels are valid/invalid
    for ex in data["examples"]:
        assert ex["label"] in {"valid", "invalid"}

    # 2. Extract ground truth from the server's private DB record for testing
    db: Database = fresh_app.state.db
    record = db.get_challenge(data["nonce"])
    assert record is not None
    correct_labels = record["correct_labels"]

    # 3. Submit correct answers
    submit_resp = client.post(
        "/api/submit",
        json={"nonce": data["nonce"], "answers": correct_labels},
    )
    assert submit_resp.status_code == 200
    sub_data = submit_resp.json()

    assert sub_data["result"] == "Challenge passed"
    assert sub_data["correct_count"] == 6
    assert sub_data["total_tests"] == 6
    assert sub_data["attempts_left"] == 2
    assert "All test strings correctly classified" in sub_data["message"]
    assert sub_data["note"] == "This is a rule-inference check, not identity verification"


def test_failed_challenge_submission(client: TestClient, fresh_app) -> None:
    """Verify that inverted answers receive 'Challenge failed' and consume an attempt."""
    resp = client.post("/api/challenge", json={"level": 1})
    data = resp.json()

    db: Database = fresh_app.state.db
    record = db.get_challenge(data["nonce"])
    assert record is not None
    correct_labels = record["correct_labels"]

    # Invert all answers
    wrong_answers = {
        tid: ("invalid" if verdict == "valid" else "valid")
        for tid, verdict in correct_labels.items()
    }

    submit_resp = client.post(
        "/api/submit",
        json={"nonce": data["nonce"], "answers": wrong_answers},
    )
    assert submit_resp.status_code == 200
    sub_data = submit_resp.json()

    assert sub_data["result"] == "Challenge failed"
    assert sub_data["correct_count"] == 0
    assert sub_data["total_tests"] == 6
    assert sub_data["attempts_left"] == 2
    assert "did not match" in sub_data["message"]


# ==============================================================================
# 2. Security & Guard Enforcement (Non-Happy Paths)
# ==============================================================================

def test_wrong_nonce_rejected(client: TestClient) -> None:
    """Verify that an unrecognized or corrupted nonce returns 404 NONCE_NOT_FOUND."""
    resp = client.post(
        "/api/submit",
        json={"nonce": "nonce_completely_fabricated", "answers": {"t0": "valid"}},
    )
    assert resp.status_code == 404
    data = resp.json()
    assert data["error_code"] == ErrorCode.NONCE_NOT_FOUND.value
    assert data["note"] == "This is a rule-inference check, not identity verification"


def test_replay_attack_rejected(client: TestClient, fresh_app) -> None:
    """Verify that submitting the same nonce a second time is rejected with NONCE_ALREADY_USED."""
    resp = client.post("/api/challenge", json={"level": 1})
    data = resp.json()
    nonce = data["nonce"]

    db: Database = fresh_app.state.db
    record = db.get_challenge(nonce)
    assert record is not None
    answers = record["correct_labels"]

    # First submission: success
    res1 = client.post("/api/submit", json={"nonce": nonce, "answers": answers})
    assert res1.status_code == 200

    # Second submission (replay): rejected
    res2 = client.post("/api/submit", json={"nonce": nonce, "answers": answers})
    assert res2.status_code == 400
    err_data = res2.json()
    assert err_data["error_code"] == ErrorCode.NONCE_ALREADY_USED.value


def test_expired_nonce_rejected() -> None:
    """Verify that expired nonces are rejected with NONCE_EXPIRED."""
    config = ServerConfig(
        nonce_expiry_seconds=0.01,  # Expires almost instantly
        allow_multiple_use=False,
        db_path=":memory:",
    )
    app = create_app(config=config)
    client = TestClient(app)

    resp = client.post("/api/challenge", json={"level": 1})
    data = resp.json()
    nonce = data["nonce"]

    # Sleep to exceed the 0.01s expiry window
    time.sleep(0.05)

    answers = {t["id"]: "valid" for t in data["tests"]}
    submit_resp = client.post("/api/submit", json={"nonce": nonce, "answers": answers})
    assert submit_resp.status_code == 400
    err_data = submit_resp.json()
    assert err_data["error_code"] == ErrorCode.NONCE_EXPIRED.value


def test_attempt_cap_overflow(client: TestClient, fresh_app) -> None:
    """Verify that exhausting 3 attempts in a session prevents further challenge/submit operations."""
    resp = client.post("/api/challenge", json={"level": 1})
    sess_id = resp.json()["session_id"]
    nonce = resp.json()["nonce"]

    # Submit 3 failed attempts
    for attempt_idx in range(3):
        if attempt_idx > 0:
            chal_resp = client.post("/api/challenge", json={"level": 1, "session_id": sess_id})
            assert chal_resp.status_code == 200
            nonce = chal_resp.json()["nonce"]

        # Send incorrect answers
        answers = {f"t{i}": "valid" for i in range(6)}
        sub_resp = client.post("/api/submit", json={"nonce": nonce, "answers": answers})
        assert sub_resp.status_code == 200

    # 4th challenge request under this session must be rejected
    overflow_resp = client.post("/api/challenge", json={"level": 1, "session_id": sess_id})
    assert overflow_resp.status_code == 400
    data = overflow_resp.json()
    assert data["error_code"] == ErrorCode.SESSION_ATTEMPTS_EXHAUSTED.value


def test_rate_limit_burst() -> None:
    """Verify that bursting more than 30 requests/minute triggers 429 RATE_LIMIT_EXCEEDED."""
    config = ServerConfig(
        rate_limit_requests=5,  # Set tight cap for test speed
        rate_limit_window_seconds=60.0,
        db_path=":memory:",
    )
    app = create_app(config=config)
    client = TestClient(app)

    headers = {"x-forwarded-for": "203.0.113.195"}

    # First 5 requests succeed
    for _ in range(5):
        r = client.post("/api/challenge", json={"level": 1}, headers=headers)
        assert r.status_code == 200

    # 6th request is throttled
    throttled = client.post("/api/challenge", json={"level": 1}, headers=headers)
    assert throttled.status_code == 429
    data = throttled.json()
    assert data["error_code"] == ErrorCode.RATE_LIMIT_EXCEEDED.value


# ==============================================================================
# 3. Leakage & Secrecy Invariants
# ==============================================================================

def test_leak_test_asserts_no_secrecy_violations(client: TestClient) -> None:
    """Verify that regex, DFA transitions, state matrices, and certificates are NEVER leaked."""
    resp = client.post("/api/challenge", json={"level": 1})
    body_text = resp.text.lower()

    # Prohibited secret keywords
    secret_terms = [
        "regex",
        "regex_str",
        "formula",
        "states",
        "transitions",
        "delta",
        "dead_state",
        "certificate",
        "witness_map",
        "correct_labels",
    ]

    for term in secret_terms:
        assert f'"{term}"' not in body_text, f"Secret term '{term}' was leaked in /api/challenge response!"

    data = resp.json()
    # Ensure test items only contain 'id' and 'string', not labels
    for test_item in data["tests"]:
        assert "label" not in test_item
        assert "verdict" not in test_item

    # Verify submit response also leaks no secret terms
    dummy_answers = {t["id"]: "valid" for t in data["tests"]}
    sub_resp = client.post("/api/submit", json={"nonce": data["nonce"], "answers": dummy_answers})
    sub_text = sub_resp.text.lower()

    for term in secret_terms:
        assert f'"{term}"' not in sub_text, f"Secret term '{term}' was leaked in /api/submit response!"


def test_forbidden_terminology_in_responses(client: TestClient) -> None:
    """Verify that forbidden terms 'human', 'verified', 'bot' never appear in API responses."""
    resp = client.post("/api/challenge", json={"level": 1})
    body_text = resp.text.lower()

    # Words prohibited in UI/API responses
    assert "human" not in body_text
    assert "verified" not in body_text
    assert "bot" not in body_text

    data = resp.json()
    dummy_answers = {t["id"]: "valid" for t in data["tests"]}
    sub_resp = client.post("/api/submit", json={"nonce": data["nonce"], "answers": dummy_answers})
    sub_text = sub_resp.text.lower()

    assert "human" not in sub_text
    assert "verified" not in sub_text
    assert "bot" not in sub_text


def test_static_frontend_served(client: TestClient) -> None:
    """Verify that GET / serves web/index.html with the mandatory scope statement."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "VeriDyn" in resp.text
    assert "VeriDyn certifies that no guessing strategy" in resp.text
    assert "This is a rule-inference check, not identity verification" in resp.text


def test_multiple_use_practice_mode() -> None:
    """Verify that when allow_multiple_use=True, challenges can be re-submitted repeatedly."""
    app = create_app(ServerConfig(allow_multiple_use=True, db_path=":memory:"))
    client = TestClient(app)

    chal = client.post("/api/challenge", json={"level": 1}).json()
    nonce = chal["nonce"]
    tests = chal["tests"]

    # Submission 1: all valid
    ans1 = {t["id"]: "valid" for t in tests}
    r1 = client.post("/api/submit", json={"nonce": nonce, "answers": ans1})
    assert r1.status_code == 200
    assert r1.json()["attempts_left"] >= 999

    # Submission 2: all invalid (re-submit on same nonce)
    ans2 = {t["id"]: "invalid" for t in tests}
    r2 = client.post("/api/submit", json={"nonce": nonce, "answers": ans2})
    assert r2.status_code == 200
    assert r2.json()["attempts_left"] >= 999

    # Submission 3: re-submit again on same nonce
    r3 = client.post("/api/submit", json={"nonce": nonce, "answers": ans1})
    assert r3.status_code == 200
    assert r3.json()["attempts_left"] >= 999

