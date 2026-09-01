#!/usr/bin/env python3
"""Verify the frozen P7 clocked iterative-deepening engineering experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import queue
import re
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


DEPTH_RE = re.compile(r"\bdepth\s+(\d+)\b")
SCORE_RE = re.compile(r"\bscore\s+(cp|mate)\s+(-?\d+)\b")
NODES_RE = re.compile(r"\bnodes\s+(\d+)\b")
TIME_RE = re.compile(r"\btime\s+(\d+)\b")
BESTMOVE_RE = re.compile(r"^bestmove\s+(\S+)")
UCI_MOVE_RE = re.compile(r"^[a-h][1-8][a-h][1-8][nbrq]?$", re.IGNORECASE)


class PhaseFailure(RuntimeError):
    def __init__(
        self,
        phase: str,
        message: str,
        transcript: list[str],
        partial_result: dict[str, Any],
    ) -> None:
        super().__init__(message)
        self.phase = phase
        self.transcript = transcript
        self.partial_result = partial_result


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
    def __init__(self, executable: Path, timeout: float) -> None:
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
        for option_name in (
            "UCI_Variant",
            "Antichess_Evaluator",
            "Antichess_Search",
            "Threads",
            "Hash",
            "EvalFile",
        ):
            require(
                any(line.startswith(f"option name {option_name} ") for line in uci_lines),
                f"engine does not advertise {option_name}",
            )

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

    def set_option(self, name: str, value: str) -> None:
        self.send(f"setoption name {name} value {value}")

    def ready(self) -> None:
        self.command_until("isready", lambda line: line == "readyok")

    def configure_fixed_depth(self) -> None:
        for name, value in (
            ("UCI_Variant", "antichess"),
            ("Antichess_Evaluator", "engineering-neutral"),
            ("Antichess_Search", "alpha-beta-v1"),
            ("Threads", "1"),
            ("Hash", "1"),
        ):
            self.set_option(name, value)
        self.ready()

    def configure_clocked(self, network: Path) -> None:
        for name, value in (
            ("UCI_Variant", "antichess"),
            ("Antichess_Search", "alpha-beta-v1"),
            ("Threads", "1"),
            ("Hash", "1"),
            ("EvalFile", str(network)),
            ("Antichess_Evaluator", "legacy-v1"),
        ):
            self.set_option(name, value)
        self.ready()
        info = self.command_until(
            "antichess-info", lambda line: line.startswith("antichess-info ")
        )[-1]
        require("profile=LICHESS_ANTICHESS_V1" in info, "profile handshake failed")
        require("network_loaded=1" in info, "legacy network is not loaded")
        require("network_format=legacy-v1" in info, "legacy network format drift")
        require("search=alpha-beta-v1" in info, "clocked search option drift")
        require("threads=1" in info and "hash_mb=1" in info, "resource option drift")

    @staticmethod
    def parse_search(lines: list[str], wall_ms: float) -> dict[str, Any]:
        info_lines = [line for line in lines if line.startswith("info ") and SCORE_RE.search(line)]
        require(info_lines, "search produced no parseable score line")
        info = info_lines[-1]
        depth_match = DEPTH_RE.search(info)
        score_match = SCORE_RE.search(info)
        nodes_match = NODES_RE.search(info)
        time_match = TIME_RE.search(info)
        bestmove_match = BESTMOVE_RE.match(lines[-1])
        require(depth_match is not None, "search depth is missing")
        require(score_match is not None, "search score is missing")
        require(nodes_match is not None, "search node count is missing")
        require(time_match is not None, "search time is missing")
        require(bestmove_match is not None, "bestmove is missing")
        return {
            "depth": int(depth_match.group(1)),
            "score_type": score_match.group(1),
            "score": int(score_match.group(2)),
            "nodes": int(nodes_match.group(1)),
            "engine_time_ms": int(time_match.group(1)),
            "wall_time_ms": round(wall_ms, 3),
            "bestmove": bestmove_match.group(1),
            "info": info,
        }

    def search(self, position: str, command: str) -> dict[str, Any]:
        self.send("ucinewgame")
        self.ready()
        self.send("position fen " + position)
        started = time.monotonic()
        lines = self.command_until(command, lambda line: BESTMOVE_RE.match(line) is not None)
        wall_ms = (time.monotonic() - started) * 1000.0
        return self.parse_search(lines, wall_ms)

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


def run_fixed_depth(
    executable: Path, fixture: dict[str, Any], timeout: float
) -> tuple[dict[str, Any], list[str]]:
    records: list[dict[str, Any]] = []
    all_exact = True
    engine = UciEngine(executable, timeout)
    try:
        engine.configure_fixed_depth()
        for case in fixture["fixed_depth_cases"]:
            result = engine.search(str(case["position"]), f"go depth {int(case['depth'])}")
            expected = case["expected"]
            exact = all(
                result[key] == expected[key]
                for key in ("score_type", "score", "bestmove", "nodes")
            )
            all_exact = all_exact and exact
            records.append(
                {"id": str(case["id"]), "exact": exact, "expected": expected, "observed": result}
            )
        transcript = list(engine.transcript)
        require(all_exact, "fixed-depth score, bestmove, or node identity drift")
    except Exception as exc:
        raise PhaseFailure(
            "fixed_depth",
            str(exc),
            list(engine.transcript),
            {"passed": False, "cases": records},
        ) from exc
    finally:
        engine.close()
    return {"passed": True, "cases": records}, transcript


def validate_clock_result(
    result: dict[str, Any], hard_budget_ms: int, overrun_ms: int, base_time_ms: int | None
) -> None:
    require(result["depth"] >= 1, "clocked search completed no full iteration")
    require(UCI_MOVE_RE.fullmatch(result["bestmove"]) is not None, "invalid clocked bestmove")
    maximum = hard_budget_ms + overrun_ms
    require(result["wall_time_ms"] <= maximum, "clocked wall-time budget overrun")
    require(result["engine_time_ms"] <= maximum, "clocked engine-time budget overrun")
    if base_time_ms is not None:
        require(result["wall_time_ms"] < base_time_ms, "clocked search reached base time")


def run_clock_scaling(
    executable: Path, network: Path, fixture: dict[str, Any], timeout: float
) -> tuple[dict[str, Any], list[str]]:
    contract = fixture["clock_scaling"]
    position = str(contract["position"])
    time_controls = contract["time_controls"]
    overrun_ms = int(contract["maximum_budget_overrun_ms"])
    records: list[dict[str, Any]] = []
    movetime_result: dict[str, Any] | None = None
    engine = UciEngine(executable, timeout)
    try:
        engine.configure_clocked(network)
        for block_index, order in enumerate(contract["balanced_block_orders"], start=1):
            for rung in order:
                tc = time_controls[rung]
                base = int(tc["time_ms"])
                increment = int(tc["increment_ms"])
                hard_budget = int(tc["expected_hard_budget_ms"])
                command = (
                    f"go wtime {base} btime {base} "
                    f"winc {increment} binc {increment}"
                )
                result = engine.search(position, command)
                validate_clock_result(result, hard_budget, overrun_ms, base)
                records.append(
                    {
                        "block": block_index,
                        "rung": rung,
                        "command": command,
                        "hard_budget_ms": hard_budget,
                        **result,
                    }
                )

        movetime = contract["movetime_probe"]
        movetime_ms = int(movetime["movetime_ms"])
        movetime_budget = int(movetime["expected_hard_budget_ms"])
        movetime_result = engine.search(position, f"go movetime {movetime_ms}")
        validate_clock_result(movetime_result, movetime_budget, overrun_ms, None)
        transcript = list(engine.transcript)
    except Exception as exc:
        raise PhaseFailure(
            "clock_scaling",
            str(exc),
            list(engine.transcript),
            {"passed": False, "records": records, "movetime_probe": movetime_result},
        ) from exc
    finally:
        engine.close()

    aggregates: dict[str, dict[str, Any]] = {}
    for rung in ("VSTC", "STC", "LTC"):
        rung_records = [record for record in records if record["rung"] == rung]
        require(
            len(rung_records) == int(contract["repetitions"]),
            f"{rung}: repetition count drift",
        )
        aggregates[rung] = {
            "nodes": sum(int(record["nodes"]) for record in rung_records),
            "median_depth": statistics.median(int(record["depth"]) for record in rung_records),
        }

    ratio_required = float(contract["minimum_adjacent_aggregate_node_ratio"])
    vstc_nodes = int(aggregates["VSTC"]["nodes"])
    stc_nodes = int(aggregates["STC"]["nodes"])
    ltc_nodes = int(aggregates["LTC"]["nodes"])
    require(vstc_nodes > 0, "VSTC aggregate nodes are zero")
    require(stc_nodes / vstc_nodes >= ratio_required, "STC/VSTC work scaling failed")
    require(ltc_nodes / stc_nodes >= ratio_required, "LTC/STC work scaling failed")

    vstc_depth = float(aggregates["VSTC"]["median_depth"])
    stc_depth = float(aggregates["STC"]["median_depth"])
    ltc_depth = float(aggregates["LTC"]["median_depth"])
    require(vstc_depth <= stc_depth <= ltc_depth, "median depth is not nondecreasing")
    require(ltc_depth > vstc_depth, "LTC median depth did not exceed VSTC")

    return (
        {
            "passed": True,
            "records": records,
            "movetime_probe": movetime_result,
            "aggregates": aggregates,
            "stc_to_vstc_nodes_ratio": stc_nodes / vstc_nodes,
            "ltc_to_stc_nodes_ratio": ltc_nodes / stc_nodes,
        },
        transcript,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("fixed-depth", "clock-scaling", "all"))
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--fixture-sha256", required=True)
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--engine-sha256", required=True)
    parser.add_argument("--network", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixture_path = args.fixture.resolve()
    engine_path = args.engine.resolve()
    output_path = args.output.resolve()
    record: dict[str, Any] = {
        "schema": "ANTICHESS_P7_CLOCKED_ITERATIVE_V1_RESULT",
        "schema_version": 1,
        "experiment_id": "p7-clocked-iterative-v1-r1",
        "phase": args.phase,
        "evidence_class": "ENGINEERING_TIMING_CAPABILITY_NOT_STRENGTH",
        "fixture": str(fixture_path),
        "fixture_sha256": sha256(fixture_path),
        "engine": str(engine_path),
        "engine_sha256": sha256(engine_path),
        "network": None,
        "network_sha256": None,
        "fixed_depth": None,
        "clock_scaling": None,
        "transcripts": {},
        "passed": False,
        "error": None,
        "non_claim": "No game, Elo, strength, OpenBench, DATAGEN, model-selection, release, or monitoring inference.",
    }
    try:
        require(args.timeout_seconds > 0, "timeout must be positive")
        require(record["fixture_sha256"] == args.fixture_sha256, "fixture SHA-256 mismatch")
        require(record["engine_sha256"] == args.engine_sha256, "engine SHA-256 mismatch")
        fixture = load_json(fixture_path)
        require(
            fixture.get("schema") == "ANTICHESS_P7_CLOCKED_ITERATIVE_V1_PREREG",
            "wrong fixture schema",
        )
        require(
            fixture.get("status") == "PREREGISTERED_INPUTS_UNEXECUTED",
            "fixture status drift",
        )
        require(len(fixture.get("fixed_depth_cases", [])) == 13, "expected 13 fixed cases")

        if args.phase in ("fixed-depth", "all"):
            fixed, transcript = run_fixed_depth(engine_path, fixture, args.timeout_seconds)
            record["fixed_depth"] = fixed
            record["transcripts"]["fixed_depth"] = transcript

        if args.phase in ("clock-scaling", "all"):
            require(args.network is not None, "clock-scaling requires --network")
            network_path = args.network.resolve()
            network_hash = sha256(network_path)
            require(
                network_hash == fixture["configuration"]["external_network_sha256"],
                "external network SHA-256 mismatch",
            )
            record["network"] = str(network_path)
            record["network_sha256"] = network_hash
            clocked, transcript = run_clock_scaling(
                engine_path, network_path, fixture, args.timeout_seconds
            )
            record["clock_scaling"] = clocked
            record["transcripts"]["clock_scaling"] = transcript

        record["passed"] = True
    except Exception as exc:  # noqa: BLE001 - preserve a fail-closed result record
        if isinstance(exc, PhaseFailure):
            record["transcripts"][exc.phase] = exc.transcript
            record[exc.phase] = exc.partial_result
        record["error"] = f"{type(exc).__name__}: {exc}"

    write_json(output_path, record)
    print(json.dumps({"passed": record["passed"], "output": str(output_path), "error": record["error"]}))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
