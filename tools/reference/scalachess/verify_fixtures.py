#!/usr/bin/env python3
"""Run the frozen fixtures against an exact external scalachess checkout."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


EXPECTED_SCALACHESS_COMMIT = "cbffc9d7e2c6f8ba33381c5403e1b4f992199626"
OUTPUT_FIELDS = {
    "canonical_fen",
    "legal_moves",
    "end",
    "auto_draw",
    "threefold",
    "fivefold",
    "variant_end",
    "status",
    "winner",
    "check",
    "player_insufficient",
    "opponent_insufficient",
    "halfmove_clock",
    "ep_square",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        text=True,
        encoding="utf-8",
        errors="strict",
    ).strip()


def encode(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def expected_output(expected: dict[str, Any]) -> dict[str, str]:
    status = {None: "-", "draw": "Draw", "variant_end": "VariantEnd"}[expected["status"]]
    winner = "-" if expected["winner"] is None else expected["winner"].title()
    return {
        "canonical_fen": expected["canonical_fen"],
        "legal_moves": ",".join(expected["legal_moves"]),
        "end": str(expected["end"]).lower(),
        "auto_draw": str(expected["automatic_draw"]).lower(),
        "threefold": str(expected["threefold"]).lower(),
        "fivefold": str(expected["fivefold"]).lower(),
        "variant_end": str(expected["variant_end"]).lower(),
        "status": status,
        "winner": winner,
        "check": str(expected["check"]).lower(),
        "player_insufficient": str(expected["player_insufficient"]).lower(),
        "opponent_insufficient": str(expected["opponent_insufficient"]).lower(),
        "halfmove_clock": str(expected["halfmove_clock"]),
        "ep_square": expected["effective_ep"] or "-",
    }


def parse_batches(output: str) -> dict[str, list[dict[str, str]]]:
    batches: dict[str, list[dict[str, str]]] = {}
    kind: str | None = None
    current: dict[str, str] | None = None
    for line in output.splitlines():
        if line.startswith("batch_kind\t"):
            kind = line.split("\t", 1)[1]
            batches.setdefault(kind, [])
            current = None
        elif line.startswith("fixture_index\t"):
            require(kind is not None, "fixture block appeared before batch kind")
            current = {"fixture_index": line.split("\t", 1)[1]}
        elif line == "fixture_end\ttrue":
            require(kind is not None and current is not None, "malformed fixture block terminator")
            missing = OUTPUT_FIELDS - current.keys()
            require(not missing, f"scalachess output block missing fields: {sorted(missing)}")
            batches[kind].append(current)
            current = None
        elif current is not None and "\t" in line:
            key, value = line.split("\t", 1)
            if key in OUTPUT_FIELDS:
                current[key] = value
    require(current is None, "unterminated scalachess output block")
    return batches


def verify_batch(
    fixtures: list[dict[str, Any]],
    actual: list[dict[str, str]],
    batch_name: str,
) -> None:
    require(len(actual) == len(fixtures), f"{batch_name}: fixture count mismatch")
    for index, (fixture, observed) in enumerate(zip(fixtures, actual, strict=True)):
        require(observed["fixture_index"] == str(index), f"{fixture['id']}: output order mismatch")
        expected = expected_output(fixture["expected"])
        for field, value in expected.items():
            require(
                observed[field] == value,
                f"{fixture['id']} {field}: expected {value!r}, got {observed[field]!r}",
            )


def main() -> int:
    project_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument("--scalachess-root", required=True, type=Path)
    parser.add_argument("--java", required=True, type=Path)
    parser.add_argument("--sbt-launcher", required=True, type=Path)
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=project_root / "tests" / "antichess" / "fixtures" / "core-v1.json",
    )
    parser.add_argument(
        "--probe-source",
        type=Path,
        default=Path(__file__).resolve().with_name("ScalachessProbe.scala"),
    )
    args = parser.parse_args()

    scalachess_root = args.scalachess_root.resolve()
    java = args.java.resolve()
    sbt_launcher = args.sbt_launcher.resolve()
    fixture_path = args.fixtures.resolve()
    probe_source = args.probe_source.resolve()
    for path in (scalachess_root, java, sbt_launcher, fixture_path, probe_source):
        require(path.exists(), f"required path does not exist: {path}")

    commit = git(scalachess_root, "rev-parse", "HEAD")
    require(commit == EXPECTED_SCALACHESS_COMMIT, f"wrong scalachess checkout: {commit}")
    tracked_status = git(scalachess_root, "status", "--porcelain", "--untracked-files=no")
    require(not tracked_status, f"pinned scalachess checkout has tracked changes:\n{tracked_status}")

    document = json.loads(fixture_path.read_text(encoding="utf-8"))
    positions = document["position_fixtures"]
    histories = document["history_fixtures"]
    encoded_positions = [encode(fixture["fen"]) for fixture in positions]
    encoded_histories = [
        encode("\n".join([fixture["initial_fen"], *fixture["moves"]])) for fixture in histories
    ]

    source_directory = probe_source.parent.as_posix().replace('"', '\\"')
    commands = [
        "set scalachess / semanticdbEnabled := false",
        f'set scalachess / Compile / unmanagedSourceDirectories += file("{source_directory}")',
        "scalachess/runMain antichess.reference.ScalachessProbe --fens64 "
        + " ".join(encoded_positions),
        "scalachess/runMain antichess.reference.ScalachessProbe --plays64 "
        + " ".join(encoded_histories),
    ]
    completed = subprocess.run(
        [
            str(java),
            "-Dsbt.task.cpus=2",
            "-jar",
            str(sbt_launcher),
            *commands,
        ],
        cwd=scalachess_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stdout)
        raise RuntimeError(f"scalachess probe failed with exit code {completed.returncode}")

    batches = parse_batches(completed.stdout)
    require(set(batches) == {"positions", "histories"}, f"unexpected probe batches: {sorted(batches)}")
    verify_batch(positions, batches["positions"], "positions")
    verify_batch(histories, batches["histories"], "histories")

    positions_by_fen = {
        fixture["fen"]: batches["positions"][index]
        for index, fixture in enumerate(positions)
    }
    for fixture in document["move_rejection_fixtures"]:
        observed = positions_by_fen.get(fixture["fen"])
        require(observed is not None, f"{fixture['id']}: rejection FEN lacks a primary position fixture")
        legal = set(filter(None, observed["legal_moves"].split(",")))
        require(fixture["move"] not in legal, f"{fixture['id']}: rejected move is primary-legal")

    probe_sha256 = hashlib.sha256(probe_source.read_bytes()).hexdigest()
    print(
        f"scalachess {commit}: verified {len(positions)} positions, {len(histories)} histories, "
        f"and {len(document['move_rejection_fixtures'])} rejected moves; probe sha256 {probe_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
