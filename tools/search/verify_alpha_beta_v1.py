#!/usr/bin/env python3
"""Run the frozen P7 exhaustive/alpha-beta fixed-work Antichess experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


SCORE_RE = re.compile(r"\bscore\s+(cp|mate)\s+(-?\d+)\b")
NODES_RE = re.compile(r"\bnodes\s+(\d+)\b")
BESTMOVE_RE = re.compile(r"^bestmove\s+(\S+)")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as source:
        value = json.load(source)
    require(isinstance(value, dict), f"{path}: JSON root must be an object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as destination:
        json.dump(value, destination, indent=2, sort_keys=True)
        destination.write("\n")


class UciEngine:
    def __init__(self, executable: Path, search_mode: str | None, timeout: float) -> None:
        self.executable = executable
        self.timeout = timeout
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.transcript: list[str] = []
        self.process = subprocess.Popen(
            [str(executable)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        require(self.process.stdin is not None, "engine stdin was not created")
        require(self.process.stdout is not None, "engine stdout was not created")
        self.reader = threading.Thread(target=self._read_stdout, daemon=True)
        self.reader.start()

        uci_lines = self.command_until("uci", lambda line: line == "uciok")
        require(
            any(line.startswith("option name UCI_Variant ") for line in uci_lines),
            "engine does not advertise UCI_Variant",
        )
        require(
            any(line.startswith("option name Antichess_Evaluator ") for line in uci_lines),
            "engine does not advertise Antichess_Evaluator",
        )
        if search_mode is not None:
            require(
                any(line.startswith("option name Antichess_Search ") for line in uci_lines),
                "candidate does not advertise Antichess_Search",
            )

        for name, value in (
            ("UCI_Variant", "antichess"),
            ("Antichess_Evaluator", "engineering-neutral"),
            ("Threads", "1"),
            ("Hash", "1"),
        ):
            self.send(f"setoption name {name} value {value}")
        if search_mode is not None:
            self.send(f"setoption name Antichess_Search value {search_mode}")
        self.command_until("isready", lambda line: line == "readyok")

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        try:
            for raw in self.process.stdout:
                self.lines.put(raw.rstrip("\r\n"))
        finally:
            self.lines.put(None)

    def send(self, command: str) -> None:
        require(self.process.poll() is None, "engine exited before command")
        assert self.process.stdin is not None
        self.transcript.append(f"> {command}")
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def command_until(self, command: str, predicate: Any) -> list[str]:
        self.send(command)
        observed: list[str] = []
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            require(remaining > 0, f"timeout after command: {command}")
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty as exc:
                raise RuntimeError(f"timeout after command: {command}") from exc
            require(line is not None, f"engine exited after command: {command}")
            self.transcript.append(line)
            observed.append(line)
            if predicate(line):
                return observed

    def search(self, position: str, depth: int) -> dict[str, Any]:
        self.send("ucinewgame")
        self.command_until("isready", lambda line: line == "readyok")
        self.send("position fen " + position)
        lines = self.command_until(
            f"go depth {depth}", lambda line: BESTMOVE_RE.match(line) is not None
        )
        info_lines = [line for line in lines if line.startswith("info ") and SCORE_RE.search(line)]
        require(info_lines, "search produced no parseable score line")
        info = info_lines[-1]
        score_match = SCORE_RE.search(info)
        nodes_match = NODES_RE.search(info)
        bestmove_match = BESTMOVE_RE.match(lines[-1])
        require(score_match is not None, "search score is missing")
        require(nodes_match is not None, "search node count is missing")
        require(bestmove_match is not None, "bestmove is missing")
        return {
            "score_type": score_match.group(1),
            "score": int(score_match.group(2)),
            "nodes": int(nodes_match.group(1)),
            "bestmove": bestmove_match.group(1),
            "info": info,
        }

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                self.send("quit")
                self.process.wait(timeout=2)
            except (RuntimeError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait(timeout=2)

    def __enter__(self) -> "UciEngine":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def run_cases(
    executable: Path,
    cases: list[dict[str, Any]],
    search_mode: str | None,
    timeout: float,
) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    with UciEngine(executable, search_mode, timeout) as engine:
        for case in cases:
            result = engine.search(str(case["position"]), int(case["depth"]))
            records.append({"id": str(case["id"]), **result})
        transcript = list(engine.transcript)
    return records, transcript


def compare_records(
    comparator: list[dict[str, Any]], candidate: list[dict[str, Any]], threshold: float
) -> dict[str, Any]:
    require(len(comparator) == len(candidate), "record count mismatch")
    comparisons: list[dict[str, Any]] = []
    comparator_nodes = 0
    candidate_nodes = 0
    all_exact = True
    all_nodes_lte = True
    for expected, observed in zip(comparator, candidate, strict=True):
        require(expected["id"] == observed["id"], "case order or identity mismatch")
        score_exact = (
            expected["score_type"] == observed["score_type"]
            and int(expected["score"]) == int(observed["score"])
        )
        bestmove_exact = expected["bestmove"] == observed["bestmove"]
        nodes_lte = int(observed["nodes"]) <= int(expected["nodes"])
        all_exact = all_exact and score_exact and bestmove_exact
        all_nodes_lte = all_nodes_lte and nodes_lte
        comparator_nodes += int(expected["nodes"])
        candidate_nodes += int(observed["nodes"])
        comparisons.append(
            {
                "id": expected["id"],
                "score_exact": score_exact,
                "bestmove_exact": bestmove_exact,
                "candidate_nodes_lte_comparator": nodes_lte,
                "comparator": expected,
                "candidate": observed,
            }
        )
    require(comparator_nodes > 0, "comparator aggregate node count is zero")
    reduction = (comparator_nodes - candidate_nodes) / comparator_nodes
    passed = all_exact and all_nodes_lte and reduction >= threshold
    return {
        "passed": passed,
        "all_scores_and_bestmoves_exact": all_exact,
        "all_candidate_nodes_lte_comparator": all_nodes_lte,
        "comparator_nodes": comparator_nodes,
        "candidate_nodes": candidate_nodes,
        "aggregate_node_reduction_fraction": reduction,
        "required_node_reduction_fraction": threshold,
        "cases": comparisons,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase", required=True, choices=("comparator-baseline", "candidate-compare")
    )
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--comparator", required=True, type=Path)
    parser.add_argument("--comparator-record", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--candidate-sha256")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixture_path = args.fixture.resolve()
    comparator_path = args.comparator.resolve()
    output_path = args.output.resolve()
    fixture = load_json(fixture_path)
    require(fixture.get("schema") == "ANTICHESS_P7_ALPHA_BETA_V1_PREREG", "wrong fixture")
    require(fixture.get("status") == "PREREGISTERED_INPUTS_UNEXECUTED", "fixture status drift")
    cases = fixture.get("cases")
    require(isinstance(cases, list) and len(cases) == 13, "expected 13 frozen cases")
    require(args.timeout_seconds > 0, "timeout must be positive")

    expected_comparator_sha = fixture["source_identity"]["comparator_windows_binary_sha256"]
    actual_comparator_sha = sha256(comparator_path)
    require(actual_comparator_sha == expected_comparator_sha, "comparator SHA-256 mismatch")
    fixture_sha = sha256(fixture_path)

    if args.phase == "comparator-baseline":
        require(args.candidate is None, "candidate is forbidden in comparator phase")
        require(args.comparator_record is None, "comparator record is forbidden in baseline phase")
        records, transcript = run_cases(comparator_path, cases, None, args.timeout_seconds)
        value = {
            "schema": "ANTICHESS_P7_ALPHA_BETA_V1_COMPARATOR_RECORD",
            "schema_version": 1,
            "experiment_id": fixture["experiment_id"],
            "profile": fixture["profile"],
            "fixture_sha256": fixture_sha,
            "comparator_binary_sha256": actual_comparator_sha,
            "search": "exhaustive-v1",
            "records": records,
            "aggregate_nodes": sum(int(record["nodes"]) for record in records),
            "transcript": transcript,
            "non_claim": "Deterministic fixed-work engineering evidence; not timing or strength.",
        }
        write_json(output_path, value)
        return 0

    require(args.candidate is not None, "candidate is required for comparison")
    require(args.candidate_sha256 is not None, "candidate SHA-256 is required")
    require(args.comparator_record is not None, "comparator record is required")
    candidate_path = args.candidate.resolve()
    candidate_sha = sha256(candidate_path)
    require(candidate_sha == args.candidate_sha256.lower(), "candidate SHA-256 mismatch")
    baseline_path = args.comparator_record.resolve()
    baseline = load_json(baseline_path)
    require(
        baseline.get("schema") == "ANTICHESS_P7_ALPHA_BETA_V1_COMPARATOR_RECORD",
        "wrong comparator record",
    )
    require(baseline.get("fixture_sha256") == fixture_sha, "comparator corpus drift")
    require(
        baseline.get("comparator_binary_sha256") == actual_comparator_sha,
        "comparator record binary drift",
    )
    candidate_records, transcript = run_cases(
        candidate_path, cases, "alpha-beta-v1", args.timeout_seconds
    )
    threshold = float(fixture["decision_rule"]["minimum_aggregate_node_reduction_fraction"])
    comparison = compare_records(baseline["records"], candidate_records, threshold)
    value = {
        "schema": "ANTICHESS_P7_ALPHA_BETA_V1_CANDIDATE_COMPARISON",
        "schema_version": 1,
        "experiment_id": fixture["experiment_id"],
        "profile": fixture["profile"],
        "fixture_sha256": fixture_sha,
        "comparator_record_sha256": sha256(baseline_path),
        "comparator_binary_sha256": actual_comparator_sha,
        "candidate_binary_sha256": candidate_sha,
        "search": "alpha-beta-v1",
        "comparison": comparison,
        "transcript": transcript,
        "non_claim": "Deterministic fixed-work engineering evidence; not timing or strength.",
    }
    write_json(output_path, value)
    return 0 if comparison["passed"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
