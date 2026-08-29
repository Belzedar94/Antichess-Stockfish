#!/usr/bin/env python3
"""Compare the dedicated legacy-v1 evaluator with a pinned Fairy-Stockfish probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_NET_BYTES = 953_248
EXPECTED_NET_SHA256 = "dd3cbe53cd4e1ca5b7f41cf090873ebe732d84d27f9ed7b14c62ff7a633712cc"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def run(binary: Path, commands: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(binary)],
        input="\n".join([*commands, "quit", ""]),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def fixture_fens() -> list[tuple[str, str]]:
    core = load("tests/antichess/fixtures/core-v1.json")
    material = load("tests/antichess/fixtures/material-boundaries-v1.json")

    entries: list[tuple[str, str]] = []
    for fixture in [
        *core["position_fixtures"],
        *core["history_fixtures"],
        *material["history_cases"],
    ]:
        entries.append((fixture["id"], fixture["expected"]["canonical_fen"]))

    unique: dict[str, str] = {}
    for fixture_id, fen in entries:
        unique.setdefault(fen, fixture_id)
    return [(fixture_id, fen) for fen, fixture_id in unique.items()]


def extract(pattern: str, output: str) -> list[int]:
    return [int(match.group(1)) for match in re.finditer(pattern, output, flags=re.MULTILINE)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--network", required=True, type=Path)
    args = parser.parse_args()

    candidate = args.candidate.resolve()
    reference = args.reference.resolve()
    network = args.network.resolve()
    for label, path in (("candidate", candidate), ("reference", reference), ("network", network)):
        require(path.is_file(), f"{label} not found: {path}")

    network_bytes = network.read_bytes()
    require(len(network_bytes) == EXPECTED_NET_BYTES, "legacy network size mismatch")
    require(
        hashlib.sha256(network_bytes).hexdigest() == EXPECTED_NET_SHA256,
        "legacy network SHA-256 mismatch",
    )

    physical_cases = fixture_fens()
    golden = load("tests/antichess/fixtures/legacy-evaluator-v1.json")
    golden_cases = golden["cases"]
    cases = [*physical_cases, *((case["id"], case["fen"]) for case in golden_cases)]
    position_commands = [command for _, fen in cases for command in (f"position fen {fen}", "eval")]

    candidate_run = run(
        candidate,
        [
            f"setoption name EvalFile value {network}",
            "setoption name Antichess_Evaluator value legacy-v1",
            "isready",
            *position_commands,
        ],
    )
    reference_run = run(
        reference,
        [
            "setoption name UCI_Variant value antichess",
            f"setoption name EvalFile value {network}",
            "setoption name Use NNUE value true",
            "isready",
            *position_commands,
        ],
    )

    require(candidate_run.returncode == 0, f"candidate exited {candidate_run.returncode}")
    require(reference_run.returncode == 0, f"reference exited {reference_run.returncode}")
    candidate_values = extract(r"^info string Antichess legacy-v1 raw value (-?\d+)$", candidate_run.stdout)
    reference_values = extract(r"^reference-legacy-raw (-?\d+)$", reference_run.stdout)
    require(len(candidate_values) == len(cases), "candidate evaluation count mismatch")
    require(len(reference_values) == len(cases), "reference evaluation count mismatch")

    failures = []
    for (fixture_id, fen), candidate_value, reference_value in zip(
        cases, candidate_values, reference_values, strict=True
    ):
        if candidate_value != reference_value:
            failures.append(
                f"{fixture_id}: candidate={candidate_value}, reference={reference_value}, fen={fen}"
            )
    require(not failures, "legacy evaluator parity failed:\n" + "\n".join(failures))

    golden_offset = len(physical_cases)
    for case, candidate_value, reference_value in zip(
        golden_cases,
        candidate_values[golden_offset:],
        reference_values[golden_offset:],
        strict=True,
    ):
        require(reference_value == case["expected_raw"], f"{case['id']}: frozen reference drift")
        require(candidate_value == case["expected_raw"], f"{case['id']}: frozen candidate drift")
        require(
            case["bucket"] == min((case["piece_count"] - 1) * 8 // 32, 7),
            f"{case['id']}: bucket contract mismatch",
        )

    buckets = {case["bucket"] for case in golden_cases}
    require(buckets == set(range(8)), f"incomplete legacy bucket coverage: {sorted(buckets)}")
    print(
        "legacy-v1 evaluator parity passed: "
        f"{len(physical_cases)} unique rules positions, {len(golden_cases)} frozen bucket cases, "
        f"{len(candidate_values)} exact values, "
        f"buckets={','.join(map(str, sorted(buckets)))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
