"""Session state and one-time cryptographic nonce lifecycle management.

TOC Concept: Interactive Proof Sessions, Single-Query Verification, and Challenge-Response Protocols.
"""

from __future__ import annotations

from dataclasses import dataclass
import secrets
import time


@dataclass(frozen=True)
class ServerConfig:
    """Configuration limits and defaults for VeriDyn server."""
    nonce_expiry_seconds: float = 120.0
    max_attempts_per_session: int = 3
    rate_limit_requests: int = 30
    rate_limit_window_seconds: float = 60.0
    response_length_cap: int = 8
    db_path: str = ":memory:"
    mandatory_note: str = "This is a rule-inference check, not identity verification"
    allow_multiple_use: bool = True


DEFAULT_CONFIG = ServerConfig(
    nonce_expiry_seconds=86400.0,
    allow_multiple_use=True,
)


@dataclass(frozen=True)
class SessionState:
    """State metadata for an interactive verification session."""
    session_id: str
    level: int
    attempts_left: int
    created_at: float
    updated_at: float


def generate_session_id() -> str:
    """Generate a cryptographically random session identifier."""
    return f"sess_{secrets.token_hex(16)}"


def generate_nonce() -> str:
    """Generate a cryptographically random one-time verification nonce."""
    return f"nonce_{secrets.token_urlsafe(32)}"


def current_timestamp() -> float:
    """Return the current epoch timestamp in seconds."""
    return time.time()


__all__ = [
    "ServerConfig",
    "DEFAULT_CONFIG",
    "SessionState",
    "generate_session_id",
    "generate_nonce",
    "current_timestamp",
]
