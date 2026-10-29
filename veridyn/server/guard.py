"""Security guards, rate limiting, and input validation.

TOC Concept: Bounded Communication Channels, Complexity Guarantees, and Denial-of-Service Protection.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection
from enum import Enum
import threading
import time

from veridyn.server.session import ServerConfig


class ErrorCode(str, Enum):
    """Enumeration of distinct security and protocol failure error codes."""
    NONCE_NOT_FOUND = "NONCE_NOT_FOUND"
    NONCE_EXPIRED = "NONCE_EXPIRED"
    NONCE_ALREADY_USED = "NONCE_ALREADY_USED"
    SESSION_ATTEMPTS_EXHAUSTED = "SESSION_ATTEMPTS_EXHAUSTED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    INVALID_ANSWER = "INVALID_ANSWER"
    INVALID_LEVEL = "INVALID_LEVEL"
    CHALLENGE_GENERATION_FAILED = "CHALLENGE_GENERATION_FAILED"


class SecurityError(Exception):
    """Exception raised for security violations or invalid protocol states."""

    def __init__(self, error_code: ErrorCode | str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.error_code = str(error_code.value if isinstance(error_code, ErrorCode) else error_code)
        self.message = message
        self.status_code = status_code


class RateLimiter:
    """Thread-safe sliding window rate limiter per IP address."""

    def __init__(self, config: ServerConfig | None = None) -> None:
        self.config = config or ServerConfig()
        self._history: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, ip: str, now: float | None = None) -> None:
        """Verify that the given IP does not exceed the sliding window request limit."""
        current_time = time.time() if now is None else now
        cutoff = current_time - self.config.rate_limit_window_seconds

        with self._lock:
            timestamps = self._history[ip]
            # Prune events older than the sliding window cutoff
            valid_timestamps = [t for t in timestamps if t >= cutoff]
            if len(valid_timestamps) >= self.config.rate_limit_requests:
                self._history[ip] = valid_timestamps
                raise SecurityError(
                    error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
                    message=f"Rate limit exceeded: maximum {self.config.rate_limit_requests} requests per {int(self.config.rate_limit_window_seconds)}s allowed.",
                    status_code=429,
                )

            valid_timestamps.append(current_time)
            self._history[ip] = valid_timestamps

    def reset(self, ip: str | None = None) -> None:
        """Reset rate limit history for a specific IP or all IPs."""
        with self._lock:
            if ip is None:
                self._history.clear()
            else:
                self._history.pop(ip, None)


def validate_answers_payload(
    answers: dict[str, str],
    expected_ids: Collection[str],
    response_length_cap: int = 8,
) -> None:
    """Validate submitted classification answers against protocol constraints."""
    if not isinstance(answers, dict):
        raise SecurityError(
            error_code=ErrorCode.INVALID_PAYLOAD,
            message="Answers field must be a JSON object mapping test IDs to verdicts.",
            status_code=400,
        )

    expected_set = set(expected_ids)
    provided_set = set(answers.keys())

    if expected_set != provided_set:
        missing = expected_set - provided_set
        extra = provided_set - expected_set
        msg_parts = []
        if missing:
            msg_parts.append(f"Missing answers for test IDs: {sorted(missing)}")
        if extra:
            msg_parts.append(f"Unexpected test IDs: {sorted(extra)}")
        raise SecurityError(
            error_code=ErrorCode.INVALID_ANSWER,
            message="; ".join(msg_parts),
            status_code=400,
        )

    valid_verdicts = {"valid", "invalid"}
    for tid, verdict in answers.items():
        if not isinstance(verdict, str):
            raise SecurityError(
                error_code=ErrorCode.INVALID_ANSWER,
                message=f"Verdict for test {tid} must be a string.",
                status_code=400,
            )

        if len(verdict) > response_length_cap:
            raise SecurityError(
                error_code=ErrorCode.INVALID_PAYLOAD,
                message=f"Verdict for test {tid} exceeds maximum allowed length of {response_length_cap}.",
                status_code=400,
            )

        if verdict.lower() not in valid_verdicts:
            raise SecurityError(
                error_code=ErrorCode.INVALID_ANSWER,
                message=f"Verdict '{verdict}' for test {tid} is invalid. Must be 'valid' or 'invalid'.",
                status_code=400,
            )


__all__ = [
    "ErrorCode",
    "SecurityError",
    "RateLimiter",
    "validate_answers_payload",
]
