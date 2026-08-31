#!/usr/bin/env python3
"""Verify the frozen, deterministic Antichess engineering bench."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "antichess" / "fixtures" / "bench-v1.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run(binary: Path, commands: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(binary)],
        input=commands + "quit\n",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


def canonical_digest(records: list[dict[str, Any]]) -> str:
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_records(output: str) -> list[dict[str, Any]]:
    infos: list[dict[str, Any]] = []
    bestmoves: list[str] = []
    pattern = re.compile(
        r"^info depth (?P<depth>\d+) .*? score (?P<score_type>mate|cp) "
        r"(?P<score>-?\d+) nodes (?P<nodes>\d+) .*? pv (?P<pv>.+)$"
    )
    for line in output.splitlines():
        if match := pattern.match(line):
            require(int(match.group("depth")) == 2, "unexpected bench depth")
            infos.append(
                {
                    "score_type": match.group("score_type"),
                    "score": int(match.group("score")),
                    "nodes": int(match.group("nodes")),
                    "pv": match.group("pv"),
                }
            )
        elif line.startswith("bestmove "):
            bestmoves.append(line.split()[1])
    require(len(infos) == len(bestmoves), "search info/bestmove count mismatch")
    return [
        {"index": index, **info, "bestmove": bestmove}
        for index, (info, bestmove) in enumerate(zip(infos, bestmoves, strict=True), start=1)
    ]


def verify_run(binary: Path, fixture: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    completed = run(
        binary,
        "uci\n"
        "setoption name Antichess_Evaluator value legacy-v1\n"
        "setoption name Antichess_Search value alpha-beta-v1\n"
        f"{fixture['command']}\n"
        "antichess-info\n",
    )
    require(completed.returncode == 0, f"bench exited {completed.returncode}")
    header = (
        f"info string Antichess bench profile={fixture['profile']} "
        "evaluator=engineering-neutral search=exhaustive-v1 depth=2 "
        f"positions={fixture['position_count']}"
    )
    require(header in completed.stdout, "missing or drifted bench identity header")
    records = parse_records(completed.stdout)
    require(records == fixture["records"], "bench search records drifted")
    require(
        "|evaluator=legacy-v1|" in completed.stdout,
        "bench did not restore the caller evaluator",
    )
    require(
        "|search=alpha-beta-v1|" in completed.stdout,
        "bench did not restore the caller search",
    )
    node_match = re.search(r"^Nodes searched\s*:\s*(\d+)$", completed.stderr, re.MULTILINE)
    require(node_match is not None, "missing aggregate node count")
    require(int(node_match.group(1)) == fixture["total_nodes"], "aggregate nodes drifted")
    digest = canonical_digest(records)
    require(digest == fixture["canonical_sha256"], "canonical bench digest drifted")
    return records, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True, type=Path)
    args = parser.parse_args()
    binary = args.engine.resolve()
    require(binary.is_file(), f"engine not found: {binary}")
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    first_records, first_digest = verify_run(binary, fixture)
    second_records, second_digest = verify_run(binary, fixture)
    require(first_records == second_records, "repeated bench records differ")
    require(first_digest == second_digest, "repeated bench digests differ")

    speedtest = run(binary, "speedtest\n")
    require(speedtest.returncode == 0, "speedtest guard exited non-zero")
    require(
        "speedtest is unavailable before the Antichess P7 search gate" in speedtest.stdout,
        "speedtest was not rejected by the P7 guard",
    )
    require("Nodes searched" not in speedtest.stdout + speedtest.stderr, "speedtest executed")

    invalid = run(binary, "bench 2 1 2 default depth\n")
    require(invalid.returncode != 0, "invalid Antichess bench parameters were accepted")
    require(
        "Antichess bench accepts only" in invalid.stdout + invalid.stderr,
        "invalid bench failed without the expected diagnostic",
    )

    print(
        "Antichess bench verification passed: "
        f"2 identical runs, {fixture['position_count']} positions, "
        f"{fixture['total_nodes']} nodes, sha256={first_digest}; "
        "speedtest guarded; invalid parameters rejected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
