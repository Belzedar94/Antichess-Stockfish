#!/usr/bin/env python3
"""Run the frozen P7 Antichess TT512 v1 fixed-work experiment."""

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
HASHFULL_RE = re.compile(r"\bhashfull\s+(\d+)\b")
BESTMOVE_RE = re.compile(r"^bestmove\s+(\S+)")
HASH_OPTION_RE = re.compile(
    r"^option name Hash type spin default (\d+) min (\d+) max (\d+)$"
)
DIAGNOSTIC_PREFIX = "antichess-info "
TT_COUNTER_FIELDS = (
    "tt_probes",
    "tt_hits",
    "tt_usable_hits",
    "tt_cutoffs",
    "tt_stores",
    "tt_max_remaining",
    "tt_hashfull",
)


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


def parse_diagnostic(line: str) -> dict[str, str]:
    require(line.startswith(DIAGNOSTIC_PREFIX), "invalid antichess-info line")
    fields: dict[str, str] = {}
    for token in line[len(DIAGNOSTIC_PREFIX) :].split("|"):
        require("=" in token, f"invalid antichess-info token: {token}")
        name, value = token.split("=", 1)
        fields[name] = value
    return fields


def exact_result(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(left[key] == right[key] for key in ("score_type", "score", "bestmove"))


def counters_are_zero(fields: dict[str, str]) -> bool:
    return all(int(fields[name]) == 0 for name in TT_COUNTER_FIELDS)


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
        self.uci_lines = self.command_until("uci", lambda line: line == "uciok")
        for option_name in (
            "UCI_Variant",
            "Antichess_Evaluator",
            "Antichess_Search",
            "Threads",
            "Hash",
            "Clear Hash",
            "EvalFile",
        ):
            require(
                any(line.startswith(f"option name {option_name} ") for line in self.uci_lines),
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

    def set_option(self, name: str, value: str | None = None) -> None:
        suffix = "" if value is None else f" value {value}"
        self.send(f"setoption name {name}{suffix}")

    def ready(self) -> None:
        self.command_until("isready", lambda line: line == "readyok")

    def new_game(self) -> None:
        self.send("ucinewgame")
        self.ready()

    def hash_contract(self) -> tuple[int, int, int]:
        lines = [line for line in self.uci_lines if line.startswith("option name Hash ")]
        require(len(lines) == 1, "Hash option count drift")
        match = HASH_OPTION_RE.fullmatch(lines[0])
        require(match is not None, "Hash option declaration drift")
        return tuple(int(value) for value in match.groups())

    def configure(
        self,
        network: Path | None,
        hash_mib: int,
        evaluator: str = "legacy-v1",
        search: str = "alpha-beta-v1",
    ) -> dict[str, str]:
        for name, value in (
            ("UCI_Variant", "antichess"),
            ("Antichess_Search", search),
            ("Threads", "1"),
            ("Hash", str(hash_mib)),
        ):
            self.set_option(name, value)
        if network is not None:
            self.set_option("EvalFile", str(network))
        self.set_option("Antichess_Evaluator", evaluator)
        self.ready()
        self.send("position startpos")
        fields = self.diagnostic()
        require(fields["profile"] == "LICHESS_ANTICHESS_V1", "profile handshake drift")
        require(fields["search"] == search, "search option drift")
        require(fields["evaluator"] == evaluator, "evaluator option drift")
        require(int(fields["threads"]) == 1, "Threads option drift")
        require(int(fields["hash_mb"]) == hash_mib, "Hash option drift")
        if evaluator == "legacy-v1":
            require(fields["network_loaded"] == "1", "legacy network is not loaded")
            require(fields["network_format"] == "legacy-v1", "legacy format drift")
        return fields

    def diagnostic(self) -> dict[str, str]:
        lines = self.command_until(
            "antichess-info", lambda line: line.startswith(DIAGNOSTIC_PREFIX)
        )
        return parse_diagnostic(lines[-1])

    def context_key(self, position: str) -> str:
        self.send("position fen " + position)
        fields = self.diagnostic()
        require("tt_context_key" in fields, "tt_context_key diagnostic is missing")
        require(fields["tt_context_key"].startswith("0x"), "tt_context_key format drift")
        return fields["tt_context_key"]

    def search(self, position: str, depth: int, clear: bool) -> dict[str, Any]:
        if clear:
            self.new_game()
        self.send("position fen " + position)
        lines = self.command_until(
            f"go depth {depth}", lambda line: BESTMOVE_RE.match(line) is not None
        )
        info_lines = [line for line in lines if line.startswith("info ") and SCORE_RE.search(line)]
        require(info_lines, "search produced no parseable score line")
        info = info_lines[-1]
        score_match = SCORE_RE.search(info)
        nodes_match = NODES_RE.search(info)
        hashfull_match = HASHFULL_RE.search(info)
        bestmove_match = BESTMOVE_RE.match(lines[-1])
        require(score_match is not None, "search score is missing")
        require(nodes_match is not None, "search node count is missing")
        require(bestmove_match is not None, "bestmove is missing")
        fields = self.diagnostic()
        result: dict[str, Any] = {
            "score_type": score_match.group(1),
            "score": int(score_match.group(2)),
            "nodes": int(nodes_match.group(1)),
            "bestmove": bestmove_match.group(1),
            "info_hashfull": int(hashfull_match.group(1)) if hashfull_match else None,
            "info": info,
            "diagnostic": fields,
        }
        return result

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
    fixture: dict[str, Any],
    network: Path,
    hash_mib: int,
    expect_tt: bool,
    timeout: float,
) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    maximum_tt_remaining = int(fixture["configuration"]["maximum_tt_remaining_depth"])
    with UciEngine(executable, timeout) as engine:
        expected_hash = (1, 1, 512) if expect_tt else (1, 1, 1)
        require(engine.hash_contract() == expected_hash, "Hash option contract drift")
        engine.configure(network, hash_mib)
        for case in fixture["cases"]:
            result = engine.search(str(case["position"]), int(case["depth"]), clear=True)
            if expect_tt:
                fields = result["diagnostic"]
                require(fields["tt_enabled"] == "1", f"{case['id']}: TT is not enabled")
                require(
                    int(fields["tt_horizon"]) == maximum_tt_remaining,
                    f"{case['id']}: TT horizon drift",
                )
                require(int(fields["hash_mb"]) == hash_mib, f"{case['id']}: Hash drift")
                for name in TT_COUNTER_FIELDS:
                    require(name in fields, f"{case['id']}: missing {name}")
                require(
                    int(fields["tt_max_remaining"]) <= maximum_tt_remaining,
                    f"{case['id']}: TT used above the frozen horizon",
                )
                require(
                    result["info_hashfull"] == int(fields["tt_hashfull"]),
                    f"{case['id']}: hashfull diagnostic mismatch",
                )
            records.append(
                {
                    "id": str(case["id"]),
                    "signal": bool(case["signal"]),
                    "activity_required": bool(case["activity_required"]),
                    **result,
                }
            )
        transcript = list(engine.transcript)
    return records, transcript


def compare_mode(
    baseline: list[dict[str, Any]], observed: list[dict[str, Any]], expect_tt: bool
) -> dict[str, Any]:
    require(len(baseline) == len(observed), "case count mismatch")
    cases: list[dict[str, Any]] = []
    exact_all = True
    nodes_lte_all = True
    aggregate = 0
    signal_cutoff_cases = 0
    usable_hits = 0
    cutoffs = 0
    activity_all = True
    maximum_tt_remaining_observed = 0
    for expected, actual in zip(baseline, observed, strict=True):
        require(expected["id"] == actual["id"], "case order or identity mismatch")
        exact = exact_result(expected, actual)
        nodes_lte = int(actual["nodes"]) <= int(expected["nodes"])
        exact_all = exact_all and exact
        nodes_lte_all = nodes_lte_all and nodes_lte
        aggregate += int(actual["nodes"])
        activity = True
        if expect_tt:
            fields = actual["diagnostic"]
            probes = int(fields["tt_probes"])
            stores = int(fields["tt_stores"])
            usable = int(fields["tt_usable_hits"])
            case_cutoffs = int(fields["tt_cutoffs"])
            usable_hits += usable
            cutoffs += case_cutoffs
            maximum_tt_remaining_observed = max(
                maximum_tt_remaining_observed, int(fields["tt_max_remaining"])
            )
            if actual["activity_required"]:
                activity = probes > 0 and stores > 0
                activity_all = activity_all and activity
            if actual["signal"] and case_cutoffs > 0:
                signal_cutoff_cases += 1
        cases.append(
            {
                "id": expected["id"],
                "exact_score_and_bestmove": exact,
                "nodes_lte_comparator": nodes_lte,
                "tt_activity_passed": activity,
                "comparator": expected,
                "candidate": actual,
            }
        )
    return {
        "exact_all": exact_all,
        "nodes_lte_all": nodes_lte_all,
        "activity_all": activity_all,
        "aggregate_nodes": aggregate,
        "aggregate_usable_hits": usable_hits,
        "aggregate_cutoffs": cutoffs,
        "signal_cases_with_cutoff": signal_cutoff_cases,
        "maximum_tt_remaining_observed": maximum_tt_remaining_observed,
        "cases": cases,
    }


def verify_context_relations(
    executable: Path, fixture: dict[str, Any], network: Path, timeout: float
) -> tuple[dict[str, Any], list[str]]:
    contract = fixture["context_key_relations"]
    with UciEngine(executable, timeout) as engine:
        engine.configure(network, 512)
        raw_a = engine.context_key(str(contract["raw_position"]))
        raw_b = engine.context_key(str(contract["raw_position"]))
        claim_a = engine.context_key(str(contract["claim_history_position"]))
        claim_b = engine.context_key(str(contract["claim_history_position"]))
        r50_zero = engine.context_key(str(contract["rule50_zero_position"]))
        r50_99 = engine.context_key(str(contract["rule50_ninety_nine_position"]))
        ep = engine.context_key(str(contract["en_passant_position"]))
        no_ep = engine.context_key(str(contract["no_en_passant_position"]))
        unique_a = engine.context_key(str(contract["unique_history_transposition_a"]))
        unique_b = engine.context_key(str(contract["unique_history_transposition_b"]))
        count_two = engine.context_key(str(contract["count_two_history_position"]))
        count_three = engine.context_key(str(contract["count_three_history_position"]))
        relations = {
            "raw_repeat_equal": raw_a == raw_b,
            "claim_repeat_equal": claim_a == claim_b,
            "raw_vs_claim_different": raw_a != claim_a,
            "rule50_zero_vs_ninety_nine_different": r50_zero != r50_99,
            "en_passant_vs_none_different": ep != no_ep,
            "unique_history_transpositions_equal": unique_a == unique_b,
            "count_two_vs_count_three_different": count_two != count_three,
        }
        require(relations == contract["required"], "context-key relation drift")
        values = {
            "raw": raw_a,
            "claim_history": claim_a,
            "rule50_zero": r50_zero,
            "rule50_ninety_nine": r50_99,
            "en_passant": ep,
            "no_en_passant": no_ep,
            "unique_history_transposition_a": unique_a,
            "unique_history_transposition_b": unique_b,
            "count_two_history": count_two,
            "count_three_history": count_three,
        }
        transcript = list(engine.transcript)
    return {"passed": True, "relations": relations, "values": values}, transcript


def verify_isolation(
    executable: Path, fixture: dict[str, Any], network: Path, timeout: float
) -> tuple[dict[str, Any], list[str]]:
    records: list[dict[str, Any]] = []
    transcript: list[str] = []
    for case in fixture["isolation_cases"]:
        with UciEngine(executable, timeout) as warmed:
            warmed.configure(network, 512)
            warm_result = warmed.search(
                str(case["warm_position"]), int(case["depth"]), clear=True
            )
            warmed_probe = warmed.search(
                str(case["probe_position"]), int(case["depth"]), clear=False
            )
            transcript.extend(warmed.transcript)
        with UciEngine(executable, timeout) as fresh:
            fresh.configure(network, 512)
            fresh_probe = fresh.search(
                str(case["probe_position"]), int(case["depth"]), clear=True
            )
            transcript.extend(fresh.transcript)
        exact = exact_result(warmed_probe, fresh_probe)
        require(exact, f"{case['id']}: warmed TT contaminated the raw result")
        records.append(
            {
                "id": str(case["id"]),
                "passed": exact,
                "warm": warm_result,
                "warmed_probe": warmed_probe,
                "fresh_probe": fresh_probe,
            }
        )
    return {"passed": True, "cases": records}, transcript


def verify_protocol_and_resets(
    executable: Path, fixture: dict[str, Any], network: Path, timeout: float
) -> tuple[dict[str, Any], list[str]]:
    missing_network = network.with_name(network.name + ".missing")
    require(not missing_network.exists(), "negative EvalFile probe unexpectedly exists")
    start = str(fixture["cases"][0]["position"])
    records: dict[str, Any] = {}
    expected_horizon = int(fixture["configuration"]["maximum_tt_remaining_depth"])
    with UciEngine(executable, timeout) as engine:
        require(engine.hash_contract() == (1, 1, 512), "candidate Hash declaration drift")
        engine.send("position startpos")
        initial = engine.diagnostic()
        require(initial["search"] == "exhaustive-v1", "default search changed")
        require(initial["tt_enabled"] == "0", "default exhaustive search enabled TT")
        require(int(initial["tt_horizon"]) == expected_horizon, "TT horizon drift")
        require(int(initial["hash_mb"]) == 1, "default Hash changed")
        require(counters_are_zero(initial), "initial TT counters are not zero")

        engine.configure(network, 16)
        at_16 = engine.diagnostic()
        engine.set_option("Hash", "0")
        engine.ready()
        after_0 = engine.diagnostic()
        engine.set_option("Hash", "513")
        engine.ready()
        after_513 = engine.diagnostic()
        require(int(at_16["hash_mb"]) == 16, "Hash 16 did not persist")
        require(int(after_0["hash_mb"]) == 16, "invalid Hash 0 changed state")
        require(int(after_513["hash_mb"]) == 16, "invalid Hash 513 changed state")

        engine.set_option("Hash", "512")
        engine.ready()
        at_512 = engine.diagnostic()
        require(int(at_512["hash_mb"]) == 512, "Hash 512 did not persist")
        require(counters_are_zero(at_512), "Hash resize did not reset TT counters")

        warm = engine.search(start, 5, clear=True)
        require(int(warm["diagnostic"]["tt_stores"]) > 0, "reset warmup stored no entries")
        engine.set_option("Clear Hash")
        engine.ready()
        after_clear = engine.diagnostic()
        require(counters_are_zero(after_clear), "Clear Hash did not reset TT state")

        engine.search(start, 5, clear=False)
        engine.new_game()
        after_new_game = engine.diagnostic()
        require(counters_are_zero(after_new_game), "ucinewgame did not reset TT state")

        engine.search(start, 5, clear=False)
        engine.set_option("Antichess_Evaluator", "engineering-neutral")
        engine.ready()
        after_evaluator = engine.diagnostic()
        require(counters_are_zero(after_evaluator), "evaluator change did not reset TT state")
        require(after_evaluator["evaluator"] == "engineering-neutral", "evaluator switch drift")
        switched_neutral = engine.search(start, 4, clear=False)

        engine.set_option("EvalFile", str(network))
        engine.ready()
        after_valid_load = engine.diagnostic()
        require(counters_are_zero(after_valid_load), "valid EvalFile load did not reset TT state")
        require(after_valid_load["network_loaded"] == "1", "valid network reload failed")
        engine.set_option("Antichess_Evaluator", "legacy-v1")
        engine.ready()
        engine.search(start, 4, clear=False)
        engine.set_option("EvalFile", str(missing_network))
        engine.ready()
        after_failed_load = engine.diagnostic()
        require(counters_are_zero(after_failed_load), "failed EvalFile load did not reset TT state")
        require(after_failed_load["network_loaded"] == "0", "failed network remained loaded")
        transcript = list(engine.transcript)

    with UciEngine(executable, timeout) as fresh_neutral_engine:
        fresh_neutral_engine.configure(None, 512, evaluator="engineering-neutral")
        fresh_neutral = fresh_neutral_engine.search(start, 4, clear=True)
        transcript.extend(fresh_neutral_engine.transcript)
    require(
        exact_result(switched_neutral, fresh_neutral),
        "evaluator switch retained a stale legacy TT result",
    )

    records.update(
        {
            "passed": True,
            "hash_contract": {"default": 1, "minimum": 1, "maximum": 512},
            "invalid_hash_0_persisted": int(after_0["hash_mb"]) == 16,
            "invalid_hash_513_persisted": int(after_513["hash_mb"]) == 16,
            "hash_resize_reset": counters_are_zero(at_512),
            "clear_hash_reset": counters_are_zero(after_clear),
            "ucinewgame_reset": counters_are_zero(after_new_game),
            "evaluator_change_reset": counters_are_zero(after_evaluator),
            "valid_evalfile_reset": counters_are_zero(after_valid_load),
            "failed_evalfile_reset": counters_are_zero(after_failed_load),
            "evaluator_isolation_exact": exact_result(switched_neutral, fresh_neutral),
        }
    )
    return records, transcript


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
    parser.add_argument("--network", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixture_path = args.fixture.resolve()
    comparator_path = args.comparator.resolve()
    network_path = args.network.resolve()
    output_path = args.output.resolve()
    runner_path = Path(__file__).resolve()
    record: dict[str, Any] = {
        "schema": "ANTICHESS_P7_TT512_V1_R2_RESULT",
        "schema_version": 1,
        "phase": args.phase,
        "experiment_id": "p7-antichess-tt512-v1-r2",
        "evidence_class": "DETERMINISTIC_FIXED_WORK_ENGINEERING_NOT_STRENGTH",
        "fixture_sha256": sha256(fixture_path),
        "runner_sha256": sha256(runner_path),
        "comparator_binary_sha256": sha256(comparator_path),
        "network_sha256": sha256(network_path),
        "candidate_binary_sha256": None,
        "passed": False,
        "error": None,
        "comparator": None,
        "candidate_hash1": None,
        "candidate_hash512": None,
        "comparison": None,
        "protocol_and_resets": None,
        "context_key_relations": None,
        "isolation": None,
        "transcripts": {},
        "non_claim": "No game, Elo, strength, speed, OpenBench, DATAGEN, model-selection, release, or monitoring inference.",
    }
    try:
        require(args.timeout_seconds > 0, "timeout must be positive")
        fixture = load_json(fixture_path)
        require(
            fixture.get("schema") == "ANTICHESS_P7_TT512_V1_R2_PREREG",
            "wrong fixture",
        )
        require(fixture.get("experiment_id") == record["experiment_id"], "experiment drift")
        require(
            fixture.get("status") == "PREREGISTERED_INPUTS_UNEXECUTED",
            "fixture status drift",
        )
        require(len(fixture.get("cases", [])) == 14, "expected 14 frozen cases")
        require(
            record["comparator_binary_sha256"]
            == fixture["source_identity"]["comparator_windows_binary_sha256"],
            "comparator SHA-256 mismatch",
        )
        require(
            record["network_sha256"] == fixture["configuration"]["external_network_sha256"],
            "external network SHA-256 mismatch",
        )

        if args.phase == "comparator-baseline":
            require(args.comparator_record is None, "comparator record forbidden in baseline")
            require(args.candidate is None, "candidate forbidden in comparator baseline")
            require(args.candidate_sha256 is None, "candidate SHA forbidden in baseline")
            cases, transcript = run_cases(
                comparator_path,
                fixture,
                network_path,
                int(fixture["configuration"]["comparator_hash_mib"]),
                expect_tt=False,
                timeout=args.timeout_seconds,
            )
            record["comparator"] = {
                "records": cases,
                "aggregate_nodes": sum(int(case["nodes"]) for case in cases),
            }
            record["transcripts"]["comparator"] = transcript
            record["passed"] = True
        else:
            require(args.candidate is not None, "candidate is required")
            require(args.candidate_sha256 is not None, "candidate SHA-256 is required")
            require(args.comparator_record is not None, "comparator record is required")
            candidate_path = args.candidate.resolve()
            candidate_sha = sha256(candidate_path)
            require(candidate_sha == args.candidate_sha256.lower(), "candidate SHA-256 mismatch")
            record["candidate_binary_sha256"] = candidate_sha

            baseline_path = args.comparator_record.resolve()
            baseline = load_json(baseline_path)
            require(baseline.get("schema") == record["schema"], "wrong comparator record")
            require(baseline.get("phase") == "comparator-baseline", "wrong baseline phase")
            require(baseline.get("passed") is True, "comparator baseline did not pass")
            for field in (
                "fixture_sha256",
                "runner_sha256",
                "comparator_binary_sha256",
                "network_sha256",
            ):
                require(baseline.get(field) == record[field], f"baseline {field} drift")
            baseline_cases = baseline["comparator"]["records"]

            hash1, transcript1 = run_cases(
                candidate_path, fixture, network_path, 1, expect_tt=True, timeout=args.timeout_seconds
            )
            hash512, transcript512 = run_cases(
                candidate_path,
                fixture,
                network_path,
                512,
                expect_tt=True,
                timeout=args.timeout_seconds,
            )
            hash1_cmp = compare_mode(baseline_cases, hash1, expect_tt=True)
            hash512_cmp = compare_mode(baseline_cases, hash512, expect_tt=True)
            comparator_nodes = int(baseline["comparator"]["aggregate_nodes"])
            require(comparator_nodes > 0, "comparator aggregate nodes are zero")
            reduction = (comparator_nodes - hash512_cmp["aggregate_nodes"]) / comparator_nodes
            rule = fixture["decision_rule"]
            comparison_passed = all(
                (
                    hash1_cmp["exact_all"],
                    hash512_cmp["exact_all"],
                    hash1_cmp["nodes_lte_all"],
                    hash512_cmp["nodes_lte_all"],
                    hash1_cmp["activity_all"],
                    hash512_cmp["activity_all"],
                    reduction
                    >= float(rule["minimum_hash512_aggregate_node_reduction_fraction"]),
                    hash512_cmp["aggregate_nodes"] <= hash1_cmp["aggregate_nodes"],
                    hash512_cmp["aggregate_usable_hits"] > 0,
                    hash512_cmp["aggregate_cutoffs"] > 0,
                    hash512_cmp["signal_cases_with_cutoff"]
                    >= int(rule["minimum_signal_cases_with_cutoff"]),
                    hash1_cmp["maximum_tt_remaining_observed"]
                    <= int(rule["maximum_tt_remaining_depth"]),
                    hash512_cmp["maximum_tt_remaining_observed"]
                    <= int(rule["maximum_tt_remaining_depth"]),
                )
            )
            record["candidate_hash1"] = {"records": hash1, "comparison": hash1_cmp}
            record["candidate_hash512"] = {"records": hash512, "comparison": hash512_cmp}
            record["comparison"] = {
                "passed": comparison_passed,
                "comparator_aggregate_nodes": comparator_nodes,
                "hash1_aggregate_nodes": hash1_cmp["aggregate_nodes"],
                "hash512_aggregate_nodes": hash512_cmp["aggregate_nodes"],
                "hash512_reduction_fraction": reduction,
                "required_reduction_fraction": float(
                    rule["minimum_hash512_aggregate_node_reduction_fraction"]
                ),
                "maximum_tt_remaining_depth": int(rule["maximum_tt_remaining_depth"]),
                "hash1_maximum_tt_remaining_observed": hash1_cmp[
                    "maximum_tt_remaining_observed"
                ],
                "hash512_maximum_tt_remaining_observed": hash512_cmp[
                    "maximum_tt_remaining_observed"
                ],
            }
            require(comparison_passed, "fixed-work TT decision rule failed")

            protocol, protocol_transcript = verify_protocol_and_resets(
                candidate_path, fixture, network_path, args.timeout_seconds
            )
            context, context_transcript = verify_context_relations(
                candidate_path, fixture, network_path, args.timeout_seconds
            )
            isolation, isolation_transcript = verify_isolation(
                candidate_path, fixture, network_path, args.timeout_seconds
            )
            record["protocol_and_resets"] = protocol
            record["context_key_relations"] = context
            record["isolation"] = isolation
            record["transcripts"] = {
                "candidate_hash1": transcript1,
                "candidate_hash512": transcript512,
                "protocol_and_resets": protocol_transcript,
                "context_key_relations": context_transcript,
                "isolation": isolation_transcript,
            }
            record["passed"] = True
    except Exception as exc:  # noqa: BLE001 - preserve fail-closed evidence
        record["error"] = f"{type(exc).__name__}: {exc}"

    write_json(output_path, record)
    print(json.dumps({"passed": record["passed"], "output": str(output_path), "error": record["error"]}))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
