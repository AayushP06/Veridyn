"""Experiment 7: Zero-Knowledge Verification and API Leakage Audit.

TOC Concept: Information-Theoretic Zero-Knowledge Proofs, Data Minimization, and Secret Separation.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from fastapi.testclient import TestClient

from veridyn.server.app import create_app
from veridyn.server.db import Database
from veridyn.server.session import ServerConfig

RESULTS_DIR = Path(__file__).resolve().parent / "results"
CSV_PATH = RESULTS_DIR / "api_leak_check.csv"

FORBIDDEN_SECRET_KEYS = [
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


def check_for_leaks(body_text: str, context: str) -> list[str]:
    """Scan response string for any forbidden secret fields or state representations."""
    leaks = []
    text_lower = body_text.lower()
    for key in FORBIDDEN_SECRET_KEYS:
        # Check quoted JSON key patterns
        if f'"{key}"' in text_lower or f"'{key}'" in text_lower:
            leaks.append(key)
    return leaks


def run_experiment() -> list[dict[str, str | int]]:
    """Audit all API endpoints and response payloads for secrecy violations."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    cfg = ServerConfig(db_path=":memory:")
    db = Database(":memory:")
    app = create_app(cfg, db=db)
    client = TestClient(app)

    print(f"\n{'='*80}")
    print("EXPERIMENT 7: Zero-Knowledge API Secrecy and Data Leakage Audit")
    print(f"{'='*80}")
    print(f"{'Endpoint':<22} | {'Scenario':<26} | {'Bytes Audited':<14} | {'Leaks Found':<12} | {'Status'}")
    print("-" * 88)

    results = []

    # 1. GET /
    r_get = client.get("/")
    leaks_get = check_for_leaks(r_get.text, "GET /")
    results.append({
        "endpoint": "GET /",
        "scenario": "Static Landing Page",
        "bytes_audited": len(r_get.content),
        "leaks_found": len(leaks_get),
        "status": "SECURE" if not leaks_get else "LEAK_DETECTED",
    })
    print(f"{'GET /':<22} | {'Static Landing Page':<26} | {len(r_get.content):<14} | {len(leaks_get):<12} | {results[-1]['status']}")

    # 2. POST /api/challenge (Levels 1 to 5)
    for lvl in range(1, 6):
        r_chal = client.post("/api/challenge", json={"level": lvl})
        chal_data = r_chal.json()
        leaks_chal = check_for_leaks(r_chal.text, f"POST /api/challenge (L{lvl})")

        # Also inspect test objects directly
        for t in chal_data.get("tests", []):
            if "label" in t or "verdict" in t:
                leaks_chal.append(f"test_{t.get('id')}_label")

        results.append({
            "endpoint": "POST /api/challenge",
            "scenario": f"Challenge Gen (Level {lvl})",
            "bytes_audited": len(r_chal.content),
            "leaks_found": len(leaks_chal),
            "status": "SECURE" if not leaks_chal else "LEAK_DETECTED",
        })
        print(f"{'POST /api/challenge':<22} | {f'Challenge Gen (Level {lvl})':<26} | {len(r_chal.content):<14} | {len(leaks_chal):<12} | {results[-1]['status']}")

        # 3. POST /api/submit (Correct Answers)
        record = db.get_challenge(chal_data["nonce"])
        assert record is not None
        correct_answers = record["correct_labels"]

        r_sub_pass = client.post("/api/submit", json={"nonce": chal_data["nonce"], "answers": correct_answers})
        leaks_pass = check_for_leaks(r_sub_pass.text, f"POST /api/submit Pass (L{lvl})")
        results.append({
            "endpoint": "POST /api/submit",
            "scenario": f"Correct Solution (Level {lvl})",
            "bytes_audited": len(r_sub_pass.content),
            "leaks_found": len(leaks_pass),
            "status": "SECURE" if not leaks_pass else "LEAK_DETECTED",
        })
        print(f"{'POST /api/submit':<22} | {f'Correct Solution (Level {lvl})':<26} | {len(r_sub_pass.content):<14} | {len(leaks_pass):<12} | {results[-1]['status']}")

    # 4. POST /api/submit (Failed Attempt)
    chal_fail = client.post("/api/challenge", json={"level": 1}).json()
    wrong_answers = {t["id"]: "invalid" for t in chal_fail["tests"]}
    r_sub_fail = client.post("/api/submit", json={"nonce": chal_fail["nonce"], "answers": wrong_answers})
    leaks_fail = check_for_leaks(r_sub_fail.text, "POST /api/submit Failed Attempt")
    results.append({
        "endpoint": "POST /api/submit",
        "scenario": "Failed Attempt (Incorrect)",
        "bytes_audited": len(r_sub_fail.content),
        "leaks_found": len(leaks_fail),
        "status": "SECURE" if not leaks_fail else "LEAK_DETECTED",
    })
    print(f"{'POST /api/submit':<22} | {'Failed Attempt (Incorrect)':<26} | {len(r_sub_fail.content):<14} | {len(leaks_fail):<12} | {results[-1]['status']}")

    # 5. POST /api/submit (Error Branch: Nonce Not Found)
    r_err = client.post("/api/submit", json={"nonce": "nonce_invalid_fake", "answers": {}})
    leaks_err = check_for_leaks(r_err.text, "POST /api/submit Error Branch")
    results.append({
        "endpoint": "POST /api/submit",
        "scenario": "Error Branch (404 Nonce)",
        "bytes_audited": len(r_err.content),
        "leaks_found": len(leaks_err),
        "status": "SECURE" if not leaks_err else "LEAK_DETECTED",
    })
    print(f"{'POST /api/submit':<22} | {'Error Branch (404 Nonce)':<26} | {len(r_err.content):<14} | {len(leaks_err):<12} | {results[-1]['status']}")

    print("-" * 88)
    total_leaks = sum(r["leaks_found"] for r in results)
    print(f"Total Secrecy Violations Detected: {total_leaks} (Expected: 0)")
    assert total_leaks == 0, f"Expected 0 leaks, found {total_leaks}!"

    # Write CSV
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    print(f"CSV saved to {CSV_PATH}")
    return results


if __name__ == "__main__":
    run_experiment()
