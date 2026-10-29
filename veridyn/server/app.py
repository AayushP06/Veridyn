"""FastAPI web application endpoints for VeriDyn challenges.

TOC Concept: Oracle Verification Protocol, Zero-Knowledge Response Classification, and Fixed Outcome Terminology.
"""

from __future__ import annotations

from pathlib import Path
import secrets
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from veridyn.challenge.generator import Challenge, GenerationError, generate_challenge
from veridyn.core.dfa import dfa_accepts
from veridyn.server.db import Database
from veridyn.server.guard import (
    ErrorCode,
    RateLimiter,
    SecurityError,
    validate_answers_payload,
)
from veridyn.server.session import (
    DEFAULT_CONFIG,
    ServerConfig,
    current_timestamp,
    generate_nonce,
)

# Paths
WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"
INDEX_HTML = WEB_DIR / "index.html"


class ChallengeRequest(BaseModel):
    """Request payload for initiating a new challenge."""
    level: int = Field(default=1, ge=1, le=5)
    session_id: str | None = None


class ExampleItem(BaseModel):
    """An example string labelled with its language membership."""
    string: str
    label: str  # "valid" or "invalid"


class TestItem(BaseModel):
    """An unlabelled test string to classify."""
    id: str
    string: str


class ChallengeResponse(BaseModel):
    """Challenge payload returned to client without leaking rule secrets."""
    session_id: str
    nonce: str
    level: int
    examples: list[ExampleItem]
    tests: list[TestItem]
    expires_in: int
    attempts_left: int
    note: str


class SubmitRequest(BaseModel):
    """Submission payload containing classified test strings."""
    nonce: str
    answers: dict[str, str]


class SubmitResponse(BaseModel):
    """Outcome payload returning strictly counts and fixed verdict terminology."""
    result: str  # "Challenge passed" or "Challenge failed"
    correct_count: int
    total_tests: int
    attempts_left: int
    message: str
    note: str


def get_client_ip(request: Request) -> str:
    """Extract client IP address accounting for proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def create_app(config: ServerConfig | None = None, db: Database | None = None) -> FastAPI:
    """Factory function creating the configured FastAPI instance."""
    cfg = config or DEFAULT_CONFIG
    database = db or Database(cfg.db_path)
    limiter = RateLimiter(cfg)

    app = FastAPI(
        title="VeriDyn",
        description="Certified Inductive Challenges Built from Finite Automata",
        version="0.1.0",
    )

    # Store state on app for access in tests/endpoints
    app.state.config = cfg
    app.state.db = database
    app.state.rate_limiter = limiter

    @app.exception_handler(SecurityError)
    async def security_error_handler(request: Request, exc: SecurityError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
                "note": cfg.mandatory_note,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "error_code": ErrorCode.INVALID_PAYLOAD.value,
                "message": "Invalid request payload format or parameters.",
                "note": cfg.mandatory_note,
            },
        )

    @app.get("/", response_class=FileResponse)
    @app.get("/index.html", response_class=FileResponse)
    async def serve_index() -> FileResponse:
        """Serve the single-page application interface."""
        if not INDEX_HTML.exists():
            raise HTTPException(status_code=404, detail="Interface file not found.")
        return FileResponse(INDEX_HTML, media_type="text/html")

    @app.post("/api/challenge", response_model=ChallengeResponse)
    async def post_challenge(request: Request, body: ChallengeRequest | None = None) -> dict[str, Any]:
        """Generate a certified challenge and return public examples and test strings."""
        ip = get_client_ip(request)
        limiter.check(ip)

        req = body or ChallengeRequest()
        level = req.level
        if level < 1 or level > 5:
            raise SecurityError(
                error_code=ErrorCode.INVALID_LEVEL,
                message=f"Level {level} is out of bounds (must be 1..5).",
                status_code=400,
            )

        # Retrieve or initialize session state
        session = database.get_or_create_session(
            session_id=req.session_id,
            level=level,
            max_attempts=cfg.max_attempts_per_session,
        )

        if not cfg.allow_multiple_use and session.attempts_left <= 0:
            raise SecurityError(
                error_code=ErrorCode.SESSION_ATTEMPTS_EXHAUSTED,
                message=f"Session attempts exhausted (maximum {cfg.max_attempts_per_session} attempts).",
                status_code=400,
            )

        # Synthesize fresh certified challenge
        seed = secrets.randbelow(1_000_000_000)
        try:
            challenge: Challenge = generate_challenge(level=level, seed=seed)
        except GenerationError as e:
            raise SecurityError(
                error_code=ErrorCode.CHALLENGE_GENERATION_FAILED,
                message=f"Failed to synthesize challenge: {e}",
                status_code=500,
            )

        nonce = generate_nonce()
        now = current_timestamp()
        expires_at = now + cfg.nonce_expiry_seconds

        # Prepare public and secret datasets
        pos_examples = list(challenge.positive_examples)
        neg_examples = list(challenge.negative_examples)

        examples: list[dict[str, str]] = []
        for s in pos_examples:
            examples.append({"string": s, "label": "valid"})
        for s in neg_examples:
            examples.append({"string": s, "label": "invalid"})

        # Map test strings to stable IDs and compute correct labels server-side
        tests: list[dict[str, str]] = []
        correct_labels: dict[str, str] = {}
        for idx, test_s in enumerate(challenge.test_strings):
            tid = f"t{idx}"
            tests.append({"id": tid, "string": test_s})
            is_valid = dfa_accepts(challenge.dfa, test_s)
            correct_labels[tid] = "valid" if is_valid else "invalid"

        cert_data = {
            "is_certified": challenge.certificate.is_certified,
            "consistent_count": len(challenge.certificate.consistent_hypotheses),
        }

        # Store challenge in database
        database.store_challenge(
            nonce=nonce,
            session_id=session.session_id,
            level=level,
            rule_name=challenge.rule_name,
            regex_str=challenge.regex_str,
            dfa_signature=challenge.dfa_signature,
            positive_examples=pos_examples,
            negative_examples=neg_examples,
            test_strings=tests,
            correct_labels=correct_labels,
            certificate_data=cert_data,
            expires_at=expires_at,
        )

        # Return strictly public components
        return {
            "session_id": session.session_id,
            "nonce": nonce,
            "level": level,
            "examples": examples,
            "tests": tests,
            "expires_in": int(cfg.nonce_expiry_seconds),
            "attempts_left": session.attempts_left if not cfg.allow_multiple_use else 999,
            "note": cfg.mandatory_note,
        }

    @app.post("/api/submit", response_model=SubmitResponse)
    async def post_submit(request: Request, body: SubmitRequest) -> dict[str, Any]:
        """Validate test classifications, consume nonce, and return verification outcome."""
        ip = get_client_ip(request)
        limiter.check(ip)

        nonce = body.nonce
        answers = body.answers

        # 1. Nonce lookup
        record = database.get_challenge(nonce)
        if not record:
            raise SecurityError(
                error_code=ErrorCode.NONCE_NOT_FOUND,
                message="Nonce not found or unrecognized.",
                status_code=404,
            )

        # 2. Replay check (only in strict single-use mode)
        if not cfg.allow_multiple_use and record["used"]:
            raise SecurityError(
                error_code=ErrorCode.NONCE_ALREADY_USED,
                message="Nonce has already been used. Challenges are strictly single-use.",
                status_code=400,
            )

        # 3. Expiration check (only enforced in strict single-use mode)
        now = current_timestamp()
        if not cfg.allow_multiple_use and now > record["expires_at"]:
            raise SecurityError(
                error_code=ErrorCode.NONCE_EXPIRED,
                message=f"Nonce has expired ({int(cfg.nonce_expiry_seconds)}s lifetime exceeded).",
                status_code=400,
            )

        # 4. Session attempts check (only in strict mode)
        session_id = record["session_id"]
        session = database.get_session(session_id)
        if not cfg.allow_multiple_use and (not session or session.attempts_left <= 0):
            raise SecurityError(
                error_code=ErrorCode.SESSION_ATTEMPTS_EXHAUSTED,
                message="Session attempts exhausted (maximum 3 attempts).",
                status_code=400,
            )

        # 5. Input payload validation
        correct_labels: dict[str, str] = record["correct_labels"]
        validate_answers_payload(
            answers=answers,
            expected_ids=list(correct_labels.keys()),
            response_length_cap=cfg.response_length_cap,
        )

        # 6. Single-use consume & decrement session attempt counter (only in strict mode)
        if not cfg.allow_multiple_use:
            database.mark_challenge_used(nonce)
            remaining_attempts = database.decrement_session_attempts(session_id)
        else:
            remaining_attempts = 999

        # 7. Evaluate classifications against ground truth
        total_tests = len(correct_labels)
        correct_count = sum(
            1 for tid, expected in correct_labels.items()
            if answers[tid].strip().lower() == expected.lower()
        )
        passed = (correct_count == total_tests)

        # 8. Fixed outcome terminology
        result = "Challenge passed" if passed else "Challenge failed"
        message = (
            "All test strings correctly classified under the hidden regular rule."
            if passed
            else f"Classification did not match the hidden regular rule ({correct_count}/{total_tests} correct)."
        )

        # 9. Audit trail recording
        database.record_attempt(
            session_id=session_id,
            nonce=nonce,
            ip_address=ip,
            answers=answers,
            correct_count=correct_count,
            total_tests=total_tests,
            passed=passed,
        )

        return {
            "result": result,
            "correct_count": correct_count,
            "total_tests": total_tests,
            "attempts_left": remaining_attempts,
            "message": message,
            "note": cfg.mandatory_note,
        }

    return app


# Default singleton app instance for `uvicorn veridyn.server.app:app`
app = create_app()


__all__ = [
    "ChallengeRequest",
    "SubmitRequest",
    "ChallengeResponse",
    "SubmitResponse",
    "create_app",
    "app",
]
