#!/usr/bin/env python3
"""Run the frozen Antichess-Stockfish versus Fairy-Stockfish S3 panel."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.strength.audit_fsf_pair_smoke_v1 import (  # noqa: E402
    notation_map,
    parse_games,
    run_probe,
)
from tools.strength.panel_contract_v1 import (  # noqa: E402
    EXPECTED_BOOK_SHA256,
    EXPECTED_CANDIDATE_COMMIT,
    EXPECTED_CANDIDATE_TREE,
    EXPECTED_FSF_BINARY_SHA256,
    EXPECTED_NETWORK_SHA256,
    EXPECTED_QT_CORE_SHA256,
    EXPECTED_REFEREE_CLI_SHA256,
    EXPECTED_REFEREE_PROBE_SHA256,
    PROFILE,
    REFEREE,
    TIME_CONTROLS_MS,
    ContractError,
    Opening,
    assert_exact_hash,
    normalize_epd_book,
    require,
    scan_forbidden_log,
    sha256_file,
    validate_completed_pair,
    validate_strength_authorization,
    wld_statistics,
    write_json_exclusive,
)


EXPERIMENT_ID = "s3-fsf-same-net-3tc-v1-r1"
EVIDENCE_CLASS = "S3_STRENGTH"
CANDIDATE_NAME = "Antichess-Stockfish"
COMPARATOR_NAME = "Fairy-Stockfish"
PREREGISTRATION_PATH = ROOT / "tests" / "antichess" / "fixtures" / "s3-fsf-same-net-3tc-v1-prereg.json"
TEST_PATH = ROOT / "tests" / "antichess" / "test_s3_strength_runner_v1.py"
EXPECTED_PREREGISTRATION_SHA256 = "96272e45f1c6404f86673e769bb7fe0a16de4c1d2ec5249f4be7d4e71f222862"
EXPECTED_CANDIDATE_BINARY_SHA256 = "5459225015a9734a3f0322b3fa4a9accdb74c5d3cb82a4efe371ae5715286213"
EXPECTED_SCHEDULE_SHA256 = "62f5efe976a690412daa03703ad31041804b1a67d715fc1c81a5606dca9cc4db"
EXPECTED_CERTIFICATION_RECEIPT_SHA256 = "74ae97afa1738f15a68339c6e646ffc1b25ebdac955c6615c3b3ae36d9b5bc5e"
EXPECTED_PYTHON_SHA256 = "42ac541168e97dedb9aabd8be335539fc41c682e414b9e8d137b164fb68683b0"
EXPECTED_PYTHON_DLL_SHA256 = "e7890e38256f04ee0b55ac5276bbf3ac61392c3a3ce150bb5497b709803e17ce"
TC_ORDER = ("VSTC", "STC", "LTC")
MINIMUM_GAMES_EXCLUSIVE = 100
MAXIMUM_GAMES = 64000
TARGET_DISPLAYED_LOS = "100.0"
LOSS_DISPLAYED_LOS = "0.0"
GAMES_PER_PAIR = 2
TIME_MARGIN_MS = 200
NO_COMPLETED_PAIR_TIMEOUT_SECONDS = 900
OWNED_SHUTDOWN_TIMEOUT_SECONDS = 30
EXPECTED_LEASE_SCHEMA = "ANTICHESS_LOCAL_RESOURCE_LEASE_V1"
EXPECTED_LEASE_RESOURCE = "ANTICHESS_S3_STRENGTH_EXCLUSIVE"
EXPECTED_RESOURCE_SNAPSHOT_SCHEMA = "ANTICHESS_RESOURCE_SNAPSHOT_V1"
EXPECTED_COMPILER_MARKERS = ("g++ (GNUC) 16.1.0 on MinGW64", "64bit SSE2")
HEX40_RE = re.compile(r"[0-9a-f]{40}")
HEX64_RE = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class PanelPaths:
    authorization: Path
    candidate: Path
    comparator: Path
    network: Path
    book: Path
    cli: Path
    probe: Path
    qt_bin: Path
    output_dir: Path
    lease: Path


@dataclass(frozen=True)
class GateDecision:
    state: str
    total: int
    displayed_los: str | None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_path(path: Path) -> str:
    return str(path.resolve())


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    with path.open("ab") as destination:
        destination.write(payload)
        destination.flush()
        os.fsync(destination.fileno())


def time_control_text(base_ms: int, increment_ms: int) -> str:
    def seconds(value: int) -> str:
        whole, remainder = divmod(value, 1000)
        if remainder == 0:
            return str(whole)
        return f"{whole}.{remainder:03d}".rstrip("0")

    return f"{seconds(base_ms)}+{seconds(increment_ms)}"


def gate_decision(wins: int, losses: int, draws: int) -> GateDecision:
    statistics = wld_statistics(wins, losses, draws)
    total = statistics.total
    if total % GAMES_PER_PAIR != 0:
        return GateDecision("INVALID_ODD_TOTAL", total, statistics.displayed_los)
    if total > MINIMUM_GAMES_EXCLUSIVE:
        if statistics.displayed_los == TARGET_DISPLAYED_LOS:
            return GateDecision("PASS", total, statistics.displayed_los)
        if statistics.displayed_los == LOSS_DISPLAYED_LOS:
            return GateDecision("REJECTED_LOSS_GATE", total, statistics.displayed_los)
    if total >= MAXIMUM_GAMES:
        return GateDecision("REJECTED_MAXIMUM_MISS", total, statistics.displayed_los)
    return GateDecision("CONTINUE", total, statistics.displayed_los)


def pair_score_bucket(outcomes: Sequence[str]) -> str:
    require(len(outcomes) == 2, "a pentanomial block requires two outcomes")
    points = {"loss": 0.0, "draw": 0.5, "win": 1.0}
    require(all(outcome in points for outcome in outcomes), "invalid candidate outcome")
    return f"{sum(points[outcome] for outcome in outcomes):.1f}"


def candidate_outcome(tags: Mapping[str, str]) -> str:
    result = tags.get("Result")
    require(result in {"1-0", "0-1", "1/2-1/2"}, "unfinished game result")
    if result == "1/2-1/2":
        return "draw"
    candidate_is_white = tags.get("White") == CANDIDATE_NAME
    candidate_is_black = tags.get("Black") == CANDIDATE_NAME
    require(candidate_is_white != candidate_is_black, "candidate color identity drift")
    candidate_won = (candidate_is_white and result == "1-0") or (candidate_is_black and result == "0-1")
    return "win" if candidate_won else "loss"


def pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    process_query_limited_information = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True


def validate_lease(path: Path, expected_sha256: str) -> dict[str, Any]:
    assert_exact_hash(path, expected_sha256, "exclusive strength lease")
    lease = load_json(path)
    require(lease.get("schema") == EXPECTED_LEASE_SCHEMA, "lease schema drift")
    require(lease.get("status") == "ACTIVE", "strength lease is not ACTIVE")
    require(lease.get("project") == "Antichess-Stockfish", "lease project drift")
    require(lease.get("experiment_id") == EXPERIMENT_ID, "lease experiment drift")
    require(lease.get("resource") == EXPECTED_LEASE_RESOURCE, "lease resource drift")
    require(lease.get("host") == platform.node(), "lease host drift")
    owner_pid = lease.get("owner_pid")
    require(isinstance(owner_pid, int) and pid_exists(owner_pid), "lease owner PID is not live")
    require(lease.get("candidate_binary_sha256") == EXPECTED_CANDIDATE_BINARY_SHA256, "lease candidate drift")
    require(lease.get("comparator_binary_sha256") == EXPECTED_FSF_BINARY_SHA256, "lease comparator drift")
    require(lease.get("network_sha256") == EXPECTED_NETWORK_SHA256, "lease network drift")
    return lease


def _require_hash(document: Mapping[str, Any], key: str, expected: str | None = None) -> str:
    value = document.get(key)
    require(isinstance(value, str) and HEX64_RE.fullmatch(value) is not None, f"missing or malformed {key}")
    if expected is not None:
        require(value == expected, f"{key} drift")
    return value


def validate_final_authorization(
    authorization: Mapping[str, Any],
    *,
    paths: PanelPaths,
    authorization_sha256: str,
) -> dict[str, Path]:
    validate_strength_authorization(authorization)
    require(authorization.get("experiment_id") == EXPERIMENT_ID, "authorization experiment drift")
    require(authorization.get("evidence_class") == EVIDENCE_CLASS, "authorization evidence class drift")
    require(authorization.get("strength_games_before_authorization") == 0, "authorization admits prior strength games")
    _require_hash(authorization, "preregistration_sha256", EXPECTED_PREREGISTRATION_SHA256)
    _require_hash(authorization, "candidate_binary_sha256", EXPECTED_CANDIDATE_BINARY_SHA256)
    _require_hash(authorization, "comparator_binary_sha256", EXPECTED_FSF_BINARY_SHA256)
    _require_hash(authorization, "network_sha256", EXPECTED_NETWORK_SHA256)
    _require_hash(authorization, "book_sha256", EXPECTED_BOOK_SHA256)
    _require_hash(authorization, "certification_receipt_sha256", EXPECTED_CERTIFICATION_RECEIPT_SHA256)
    _require_hash(authorization, "schedule_sha256", EXPECTED_SCHEDULE_SHA256)
    _require_hash(authorization, "referee_cli_sha256", EXPECTED_REFEREE_CLI_SHA256)
    _require_hash(authorization, "referee_probe_sha256", EXPECTED_REFEREE_PROBE_SHA256)
    _require_hash(authorization, "qt_core_sha256", EXPECTED_QT_CORE_SHA256)
    _require_hash(authorization, "python_executable_sha256", EXPECTED_PYTHON_SHA256)
    _require_hash(authorization, "python_dll_sha256", EXPECTED_PYTHON_DLL_SHA256)
    runner_sha256 = _require_hash(authorization, "runner_sha256")
    tests_sha256 = _require_hash(authorization, "runner_tests_sha256")
    _require_hash(authorization, "runner_git_blob_sha256")
    _require_hash(authorization, "runner_tests_git_blob_sha256")
    lease_sha256 = _require_hash(authorization, "lease_sha256")
    require(runner_sha256 == sha256_file(Path(__file__).resolve()), "running runner hash drift")
    require(tests_sha256 == sha256_file(TEST_PATH), "runner test hash drift")
    require(authorization_sha256 == sha256_file(paths.authorization), "authorization hash drift")

    expected_paths = {
        "candidate": paths.candidate,
        "comparator": paths.comparator,
        "network": paths.network,
        "book": paths.book,
        "cli": paths.cli,
        "probe": paths.probe,
        "qt_bin": paths.qt_bin,
        "output_dir": paths.output_dir,
        "lease": paths.lease,
    }
    authorized_paths = authorization.get("paths")
    require(isinstance(authorized_paths, dict), "authorized paths missing")
    for key, value in expected_paths.items():
        require(authorized_paths.get(key) == canonical_path(value), f"authorized {key} path drift")

    require(authorization.get("controllers") == 1, "controller count drift")
    require(authorization.get("concurrency") == 1, "concurrency drift")
    require(authorization.get("time_margin_ms") == TIME_MARGIN_MS, "time margin drift")
    require(
        authorization.get("no_completed_pair_timeout_seconds") == NO_COMPLETED_PAIR_TIMEOUT_SECONDS,
        "no-progress timeout drift",
    )
    require(authorization.get("time_control_order") == list(TC_ORDER), "time-control order drift")
    require(authorization.get("sprt") is False, "SPRT is prohibited")
    require(authorization.get("score_adjudication") is False, "score adjudication is prohibited")
    require(authorization.get("tablebases") is False, "tablebases are prohibited")
    require(authorization.get("output_root_create_once") is True, "output overwrite contract missing")
    require(authorization.get("host") == platform.node(), "authorization host drift")

    merge_commit = authorization.get("implementation_merge_commit")
    merge_tree = authorization.get("implementation_merge_tree")
    require(isinstance(merge_commit, str) and HEX40_RE.fullmatch(merge_commit) is not None, "implementation merge missing")
    require(isinstance(merge_tree, str) and HEX40_RE.fullmatch(merge_tree) is not None, "implementation tree missing")
    require(authorization.get("exact_head_review_status") == "PASS", "exact-head review did not pass")
    require(authorization.get("postmerge_ci_status") == "PASS", "post-merge CI did not pass")
    require(str(authorization.get("postmerge_ci_run", "")).isdigit(), "post-merge CI run missing")

    snapshots = authorization.get("resource_snapshots")
    require(isinstance(snapshots, list) and len(snapshots) == 2, "two resource snapshots required")
    snapshot_paths: dict[str, Path] = {}
    for index, snapshot in enumerate(snapshots, start=1):
        require(isinstance(snapshot, dict), "malformed resource snapshot")
        require(snapshot.get("foreign_variant_load") is False, "foreign variant load was present")
        require(snapshot.get("foreign_active_lease") is False, "foreign active lease was present")
        expected_snapshot_sha256 = _require_hash(snapshot, "snapshot_sha256")
        snapshot_path_value = snapshot.get("path")
        require(isinstance(snapshot_path_value, str), "resource snapshot path missing")
        snapshot_path = Path(snapshot_path_value).resolve()
        assert_exact_hash(snapshot_path, expected_snapshot_sha256, f"resource snapshot {index}")
        snapshot_document = load_json(snapshot_path)
        require(snapshot_document.get("schema") == EXPECTED_RESOURCE_SNAPSHOT_SCHEMA, "resource snapshot schema drift")
        require(snapshot_document.get("host") == platform.node(), "resource snapshot host drift")
        require(snapshot_document.get("foreign_variant_load") is False, "resource snapshot recorded foreign load")
        require(snapshot_document.get("foreign_active_lease") is False, "resource snapshot recorded foreign lease")
        snapshot_paths[f"resource_snapshot_{index}"] = snapshot_path
    validate_lease(paths.lease, lease_sha256)
    return snapshot_paths


def asset_paths(paths: PanelPaths, extra_paths: Mapping[str, Path] | None = None) -> dict[str, Path]:
    python_executable = Path(sys.executable).resolve()
    python_dll = python_executable.parent / "python312.dll"
    result = {
        "authorization": paths.authorization,
        "book": paths.book,
        "candidate": paths.candidate,
        "cli": paths.cli,
        "comparator": paths.comparator,
        "lease": paths.lease,
        "network": paths.network,
        "preregistration": PREREGISTRATION_PATH,
        "probe": paths.probe,
        "python_dll": python_dll,
        "python_executable": python_executable,
        "qt_core": paths.qt_bin / "Qt6Core.dll",
        "runner": Path(__file__).resolve(),
        "runner_tests": TEST_PATH,
    }
    if extra_paths:
        for label, path in extra_paths.items():
            require(label not in result, f"duplicate asset label: {label}")
            result[label] = path
    return result


def fingerprint_assets(
    paths: PanelPaths,
    extra_paths: Mapping[str, Path] | None = None,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for label, path in sorted(asset_paths(paths, extra_paths).items()):
        require(path.is_file(), f"required {label} input not found: {path}")
        result[label] = {
            "bytes": path.stat().st_size,
            "path": canonical_path(path),
            "sha256": sha256_file(path),
        }
    return result


def validate_asset_identities(fingerprints: Mapping[str, Mapping[str, Any]]) -> None:
    expected = {
        "book": EXPECTED_BOOK_SHA256,
        "candidate": EXPECTED_CANDIDATE_BINARY_SHA256,
        "cli": EXPECTED_REFEREE_CLI_SHA256,
        "comparator": EXPECTED_FSF_BINARY_SHA256,
        "network": EXPECTED_NETWORK_SHA256,
        "preregistration": EXPECTED_PREREGISTRATION_SHA256,
        "probe": EXPECTED_REFEREE_PROBE_SHA256,
        "python_dll": EXPECTED_PYTHON_DLL_SHA256,
        "python_executable": EXPECTED_PYTHON_SHA256,
        "qt_core": EXPECTED_QT_CORE_SHA256,
    }
    for label, sha256 in expected.items():
        require(fingerprints[label]["sha256"] == sha256, f"{label} fingerprint drift")


def validate_compiler_output(output: str, *, label: str) -> dict[str, str]:
    for marker in EXPECTED_COMPILER_MARKERS:
        require(marker in output, f"{label} compiler output missing {marker!r}")
    return {"compiler": EXPECTED_COMPILER_MARKERS[0], "target": EXPECTED_COMPILER_MARKERS[1]}


def compiler_preflight(engine: Path, output_path: Path, *, label: str) -> dict[str, str]:
    completed = subprocess.run(
        [str(engine), "compiler"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    with output_path.open("xb") as destination:
        destination.write(completed.stdout.encode("utf-8"))
    require(completed.returncode == 0, f"{label} compiler command exited {completed.returncode}")
    return validate_compiler_output(completed.stdout, label=label)


def uci_playing_preflight(
    engine: Path,
    options: Sequence[tuple[str, str]],
    output: Path,
    *,
    expected_markers: Sequence[str],
) -> None:
    commands = ["uci", *(f"setoption name {name} value {value}" for name, value in options), "isready", "position startpos", "go nodes 1", "quit"]
    completed = subprocess.run(
        [str(engine)],
        input="\n".join(commands) + "\n",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    with output.open("xb") as destination:
        destination.write(completed.stdout.encode("utf-8"))
    require(completed.returncode == 0, f"playing preflight exited {completed.returncode}: {engine}")
    require("uciok" in completed.stdout and "readyok" in completed.stdout, f"UCI handshake failed: {engine}")
    require(re.search(r"(?m)^bestmove\s+\S+", completed.stdout) is not None, f"one-node search failed: {engine}")
    for marker in expected_markers:
        require(marker in completed.stdout, f"playing preflight missing marker {marker!r}: {engine}")


def build_cutechess_command(
    paths: PanelPaths,
    *,
    tc_name: str,
    pair_index: int,
    opening_path: Path,
    pgn_path: Path,
) -> tuple[list[str], str, str]:
    base_ms, increment_ms = TIME_CONTROLS_MS[tc_name]
    tc = time_control_text(base_ms, increment_ms)
    event = f"Antichess S3 same-net {tc_name} pair {pair_index:05d}"
    command = [
        str(paths.cli),
        "-engine",
        f"name={CANDIDATE_NAME}",
        f"cmd={paths.candidate}",
        f"dir={paths.candidate.parent}",
        "proto=uci",
        "restart=on",
        "option.UCI_Variant=antichess",
        "option.Antichess_Evaluator=legacy-v1",
        "option.Antichess_Search=alpha-beta-v1",
        f"option.EvalFile={paths.network}",
        "option.Threads=1",
        "option.Hash=512",
        "-engine",
        f"name={COMPARATOR_NAME}",
        f"cmd={paths.comparator}",
        f"dir={paths.comparator.parent}",
        "proto=uci",
        "restart=on",
        "option.UCI_Variant=antichess",
        "option.Use NNUE=true",
        f"option.EvalFile={paths.network}",
        "option.Threads=1",
        "option.Hash=512",
        "-each",
        f"tc={tc}",
        f"timemargin={TIME_MARGIN_MS}",
        "-variant",
        "antichess",
        "-tournament",
        "round-robin",
        "-games",
        "2",
        "-rounds",
        "1",
        "-repeat",
        "2",
        "-concurrency",
        "1",
        "-openings",
        f"file={opening_path}",
        "format=epd",
        "order=sequential",
        "plies=1024",
        "start=1",
        "-debug",
        "-pgnout",
        str(pgn_path),
        "fi",
        "-event",
        event,
    ]
    return command, tc, event


def terminate_owned_tree(process: subprocess.Popen[bytes]) -> int:
    if process.poll() is not None:
        return int(process.returncode)
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=OWNED_SHUTDOWN_TIMEOUT_SECONDS,
            check=False,
        )
    else:
        process.kill()
    return process.wait(timeout=OWNED_SHUTDOWN_TIMEOUT_SECONDS)


def verify_raw_pair_log(text: str, network: Path) -> dict[str, Any]:
    forbidden = scan_forbidden_log(text)
    required = {
        "candidate_evaluator": len(re.findall(r"setoption name Antichess_Evaluator value legacy-v1", text, re.IGNORECASE)),
        "candidate_search": len(re.findall(r"setoption name Antichess_Search value alpha-beta-v1", text, re.IGNORECASE)),
        "candidate_network_loaded": len(re.findall(r"Loaded Antichess legacy-v1 network", text)),
        "comparator_network_loaded": len(re.findall(r"NNUE evaluation using .* enabled", text)),
        "hash_512": len(re.findall(r"setoption name Hash value 512", text, re.IGNORECASE)),
        "threads_1": len(re.findall(r"setoption name Threads value 1", text, re.IGNORECASE)),
        "uci_variant": len(re.findall(r"setoption name UCI_Variant value antichess", text, re.IGNORECASE)),
        "use_nnue": len(re.findall(r"setoption name Use NNUE value true", text, re.IGNORECASE)),
        "network_path": text.count(str(network)),
        "bestmove": len(re.findall(r"\bbestmove\b", text, re.IGNORECASE)),
    }
    require(all(value == 0 for value in forbidden.values()), "raw log contains a forbidden failure marker")
    require(all(value > 0 for value in required.values()), "raw log lacks required option, network, or search evidence")
    return {"forbidden_pattern_counts": forbidden, "required_pattern_counts": required}


def audit_pair(
    pgn_path: Path,
    launch: Mapping[str, Any],
    probe: Path,
    qt_bin: Path,
    *,
    probe_runner: Callable[[Path, str, list[str], dict[str, str]], dict[str, str]] = run_probe,
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PATH"] = str(qt_bin) + os.pathsep + environment.get("PATH", "")
    games = parse_games(pgn_path.read_text(encoding="utf-8", errors="strict"))
    require(len(games) == 2, f"PGN game count {len(games)} != 2")

    pair_records: list[dict[str, Any]] = []
    audited_games: list[dict[str, Any]] = []
    outcomes: list[str] = []
    mandatory_positions = 0
    total_clock_comments = 0
    total_plies = 0
    for game_index, (tags, sans, clock_comments) in enumerate(games, start=1):
        require(tags.get("Event") == launch["event"], f"game {game_index}: Event tag drift")
        require(tags.get("Variant") == "Antichess", f"game {game_index}: Variant tag drift")
        require(tags.get("FEN") == launch["opening_fen"], f"game {game_index}: FEN tag drift")
        require(tags.get("SetUp") == "1", f"game {game_index}: SetUp tag drift")
        require(tags.get("TimeControl") == launch["time_control"], f"game {game_index}: time-control drift")
        require(tags.get("Result") in {"1-0", "0-1", "1/2-1/2"}, f"game {game_index}: unfinished")
        require(int(tags.get("PlyCount", "-1")) == len(sans), f"game {game_index}: PlyCount drift")
        require(clock_comments == len(sans), f"game {game_index}: missing per-ply clock comments")

        moves: list[str] = []
        game_mandatory = 0
        for ply, san in enumerate(sans, start=1):
            fields = probe_runner(probe, launch["opening_fen"], moves, environment)
            mapping = notation_map(fields)
            matches = [move for move, expected_san in mapping.items() if expected_san == san]
            require(len(matches) == 1, f"game {game_index} ply {ply}: SAN {san!r} is not uniquely legal")
            if fields["must_capture"] == "1":
                require("x" in san, f"game {game_index} ply {ply}: compulsory capture lost in SAN")
                mandatory_positions += 1
                game_mandatory += 1
            if san.endswith("#"):
                require(ply == len(sans), f"game {game_index}: terminal SAN before final ply")
            moves.append(matches[0])

        final = probe_runner(probe, launch["opening_fen"], moves, environment)
        expected_winner = "white" if tags["Result"] == "1-0" else "black" if tags["Result"] == "0-1" else "none"
        require(final["end"] == "1", f"game {game_index}: PGN ended in an ongoing position")
        require(final["board_result"] == ("draw" if expected_winner == "none" else "win"), f"game {game_index}: result-class drift")
        require(final["board_result_winner"] == expected_winner, f"game {game_index}: winner drift")
        if expected_winner != "none":
            require(bool(sans) and sans[-1].endswith("#"), f"game {game_index}: winning move lacks terminal SAN")

        outcome = candidate_outcome(tags)
        outcomes.append(outcome)
        pair_records.append(
            {
                "black": tags["Black"],
                "defects": [],
                "fen": tags["FEN"],
                "result": tags["Result"],
                "terminal_marker": True,
                "time_control": tags["TimeControl"],
                "variant": tags["Variant"],
                "white": tags["White"],
            }
        )
        audited_games.append(
            {
                "black": tags["Black"],
                "candidate_outcome": outcome,
                "final_board_result": final["board_result"],
                "final_winner": final["board_result_winner"],
                "mandatory_positions": game_mandatory,
                "plies": len(sans),
                "result": tags["Result"],
                "white": tags["White"],
            }
        )
        total_clock_comments += clock_comments
        total_plies += len(sans)

    validate_completed_pair(
        pair_records,
        candidate=CANDIDATE_NAME,
        comparator=COMPARATOR_NAME,
        opening_fen=str(launch["opening_fen"]),
        time_control=str(launch["time_control"]),
    )
    require(mandatory_positions > 0, "audited pair never exercised compulsory capture")
    return {
        "candidate_outcomes": outcomes,
        "games": audited_games,
        "mandatory_positions": mandatory_positions,
        "pentanomial_bucket": pair_score_bucket(outcomes),
        "profile": PROFILE,
        "referee": REFEREE,
        "total_clock_comments": total_clock_comments,
        "total_plies": total_plies,
    }


def pair_artifact_fingerprints(pair_dir: Path) -> dict[str, dict[str, Any]]:
    names = ("opening.epd", "launch.json", "raw.log", "games.pgn", "audit.json")
    result: dict[str, dict[str, Any]] = {}
    for name in names:
        path = pair_dir / name
        require(path.is_file() and path.stat().st_size > 0, f"missing pair artifact: {path}")
        result[name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    return result


def run_pair(
    paths: PanelPaths,
    *,
    authorization_sha256: str,
    tc_name: str,
    pair_index: int,
    opening: Opening,
    pair_dir: Path,
) -> dict[str, Any]:
    pair_dir.mkdir(parents=True, exist_ok=False)
    opening_path = pair_dir / "opening.epd"
    with opening_path.open("xb") as destination:
        destination.write((opening.source_epd + "\n").encode("ascii"))
    pgn_path = pair_dir / "games.pgn"
    raw_log_path = pair_dir / "raw.log"
    command, tc, event = build_cutechess_command(
        paths,
        tc_name=tc_name,
        pair_index=pair_index,
        opening_path=opening_path,
        pgn_path=pgn_path,
    )
    started_at = utc_now()
    environment = os.environ.copy()
    environment["PATH"] = str(paths.qt_bin) + os.pathsep + environment.get("PATH", "")
    with raw_log_path.open("xb") as raw_log:
        process = subprocess.Popen(command, stdout=raw_log, stderr=subprocess.STDOUT, env=environment)
        launch = {
            "authorization_sha256": authorization_sha256,
            "candidate_name": CANDIDATE_NAME,
            "command": command,
            "comparator_name": COMPARATOR_NAME,
            "evidence_class": EVIDENCE_CLASS,
            "event": event,
            "experiment_id": EXPERIMENT_ID,
            "opening_fen": opening.fen,
            "opening_schedule_key": opening.schedule_key,
            "opening_source_index": opening.source_index,
            "pair_index": pair_index,
            "pid": process.pid,
            "profile": PROFILE,
            "referee": REFEREE,
            "started_at": started_at,
            "tc_name": tc_name,
            "time_control": tc,
        }
        write_json_exclusive(pair_dir / "launch.json", launch)
        timed_out = False
        try:
            return_code = process.wait(timeout=NO_COMPLETED_PAIR_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            timed_out = True
            return_code = terminate_owned_tree(process)

    raw_text = raw_log_path.read_text(encoding="utf-8", errors="replace")
    require(not timed_out, "pair exceeded the 900-second no-completed-pair watchdog")
    require(return_code == 0, f"Cute Chess exited {return_code}")
    require(pgn_path.is_file() and pgn_path.stat().st_size > 0, "pair produced no PGN")
    log_audit = verify_raw_pair_log(raw_text, paths.network)
    pair_audit = audit_pair(pgn_path, launch, paths.probe, paths.qt_bin)
    pair_audit["finished_at"] = utc_now()
    pair_audit["raw_log_audit"] = log_audit
    pair_audit["return_code"] = return_code
    pair_audit["timed_out"] = timed_out
    write_json_exclusive(pair_dir / "audit.json", pair_audit)
    return {
        "artifacts": pair_artifact_fingerprints(pair_dir),
        "candidate_outcomes": pair_audit["candidate_outcomes"],
        "mandatory_positions": pair_audit["mandatory_positions"],
        "opening_schedule_key": opening.schedule_key,
        "opening_source_index": opening.source_index,
        "pair_index": pair_index,
        "pentanomial_bucket": pair_audit["pentanomial_bucket"],
        "tc_name": tc_name,
        "time_control": tc,
        "total_plies": pair_audit["total_plies"],
    }


def statistics_document(wld: Counter[str], penta: Counter[str]) -> dict[str, Any]:
    stats = wld_statistics(wld["win"], wld["loss"], wld["draw"])
    return {
        "decision": asdict(gate_decision(wld["win"], wld["loss"], wld["draw"])),
        "elo": stats.elo,
        "elo95": stats.elo95,
        "los": stats.los,
        "displayed_los": stats.displayed_los,
        "pentanomial": {bucket: penta[bucket] for bucket in ("0.0", "0.5", "1.0", "1.5", "2.0")},
        "wld": {"wins": wld["win"], "losses": wld["loss"], "draws": wld["draw"], "total": stats.total},
    }


def run_time_control(
    paths: PanelPaths,
    *,
    authorization_sha256: str,
    tc_name: str,
    openings: Sequence[Opening],
) -> dict[str, Any]:
    tc_dir = paths.output_dir / tc_name
    pairs_dir = tc_dir / "pairs"
    pairs_dir.mkdir(parents=True, exist_ok=False)
    ledger_path = tc_dir / "pair-ledger.jsonl"
    ledger_path.touch(exist_ok=False)
    wld: Counter[str] = Counter()
    penta: Counter[str] = Counter()
    try:
        for pair_index in range(1, MAXIMUM_GAMES // 2 + 1):
            opening = openings[(pair_index - 1) % len(openings)]
            pair_record = run_pair(
                paths,
                authorization_sha256=authorization_sha256,
                tc_name=tc_name,
                pair_index=pair_index,
                opening=opening,
                pair_dir=pairs_dir / f"pair-{pair_index:05d}",
            )
            for outcome in pair_record["candidate_outcomes"]:
                wld[outcome] += 1
            penta[pair_record["pentanomial_bucket"]] += 1
            pair_record["cumulative"] = statistics_document(wld, penta)
            append_jsonl(ledger_path, pair_record)
            decision = gate_decision(wld["win"], wld["loss"], wld["draw"])
            print(
                f"{tc_name} pair={pair_index} total={decision.total} "
                f"WLD={wld['win']}/{wld['loss']}/{wld['draw']} "
                f"LOS={decision.displayed_los or 'unavailable'} state={decision.state}",
                flush=True,
            )
            if decision.state != "CONTINUE":
                statistics = statistics_document(wld, penta)
                write_json_exclusive(tc_dir / "wld-penta.json", statistics)
                result = {
                    "completed_pairs": pair_index,
                    "defects": {},
                    "evidence_class": EVIDENCE_CLASS,
                    "experiment_id": EXPERIMENT_ID,
                    "finished_at": utc_now(),
                    "profile": PROFILE,
                    "referee": REFEREE,
                    "statistics": statistics,
                    "status": decision.state,
                    "tc_name": tc_name,
                    "time_control_ms": list(TIME_CONTROLS_MS[tc_name]),
                }
                write_json_exclusive(tc_dir / "result.json", result)
                return result
    except Exception as error:
        failure = {
            "error": str(error),
            "evidence_class": EVIDENCE_CLASS,
            "experiment_id": EXPERIMENT_ID,
            "finished_at": utc_now(),
            "status": "INVALIDATED_NO_STRENGTH_CONCLUSION",
            "tc_name": tc_name,
        }
        if not (tc_dir / "result.json").exists():
            write_json_exclusive(tc_dir / "result.json", failure)
        raise
    raise ContractError(f"{tc_name}: exhausted pair loop without terminal decision")


def run_campaign(
    paths: PanelPaths,
    *,
    authorization_sha256: str,
    openings: Sequence[Opening],
) -> tuple[int, dict[str, Any]]:
    results: dict[str, Any] = {}
    for tc_name in TC_ORDER:
        result = run_time_control(
            paths,
            authorization_sha256=authorization_sha256,
            tc_name=tc_name,
            openings=openings,
        )
        results[tc_name] = result
        if result["status"] != "PASS":
            aggregate = {
                "evidence_class": EVIDENCE_CLASS,
                "experiment_id": EXPERIMENT_ID,
                "finished_at": utc_now(),
                "profile": PROFILE,
                "status": "REJECTED_STRENGTH",
                "tc_results": results,
            }
            return 1, aggregate
    aggregate = {
        "evidence_class": EVIDENCE_CLASS,
        "experiment_id": EXPERIMENT_ID,
        "finished_at": utc_now(),
        "profile": PROFILE,
        "status": "PASS_ALL_THREE_TCS",
        "tc_results": results,
    }
    return 0, aggregate


def verify_git_ancestry() -> dict[str, str]:
    candidate_tree = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", f"{EXPECTED_CANDIDATE_COMMIT}^{{tree}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    require(candidate_tree.returncode == 0, f"candidate object missing: {candidate_tree.stdout}")
    require(candidate_tree.stdout.strip() == EXPECTED_CANDIDATE_TREE, "candidate tree drift")
    ancestor = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", "8bc5caa2e4b1d4c189b1428e93158b10d3edb0b6", EXPECTED_CANDIDATE_COMMIT],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    require(ancestor.returncode == 0, f"official Stockfish ancestry failed: {ancestor.stdout}")
    return {"candidate_commit": EXPECTED_CANDIDATE_COMMIT, "candidate_tree": EXPECTED_CANDIDATE_TREE}


def verify_implementation_provenance(authorization: Mapping[str, Any]) -> dict[str, str]:
    merge_commit = str(authorization["implementation_merge_commit"])
    expected_tree = str(authorization["implementation_merge_tree"])
    tree = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", f"{merge_commit}^{{tree}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    require(tree.returncode == 0, f"implementation merge object missing: {tree.stdout}")
    require(tree.stdout.strip() == expected_tree, "implementation merge tree drift")
    ancestor = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", merge_commit, "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    require(ancestor.returncode == 0, "implementation merge is not in the running checkout ancestry")
    tracked = {
        "tools/strength/run_fsf_same_net_3tc_v1.py": str(authorization["runner_git_blob_sha256"]),
        "tests/antichess/test_s3_strength_runner_v1.py": str(authorization["runner_tests_git_blob_sha256"]),
    }
    for repository_path, expected_sha256 in tracked.items():
        blob = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{merge_commit}:{repository_path}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        require(blob.returncode == 0, f"implementation merge lacks {repository_path}")
        require(hashlib.sha256(blob.stdout).hexdigest() == expected_sha256, f"merged {repository_path} hash drift")
        working_bytes = (ROOT / repository_path).read_bytes().replace(b"\r\n", b"\n")
        require(hashlib.sha256(working_bytes).hexdigest() == expected_sha256, f"working {repository_path} content drift")
    return {"implementation_merge_commit": merge_commit, "implementation_merge_tree": expected_tree}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--expected-authorization-sha256", required=True)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--comparator", required=True, type=Path)
    parser.add_argument("--network", required=True, type=Path)
    parser.add_argument("--book", required=True, type=Path)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--probe", required=True, type=Path)
    parser.add_argument("--qt-bin", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--lease", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    require(os.name == "nt", "the frozen S3 strength runner is Windows-only")
    require(HEX64_RE.fullmatch(args.expected_authorization_sha256.lower()) is not None, "malformed authorization hash")
    paths = PanelPaths(
        authorization=args.authorization.resolve(),
        candidate=args.candidate.resolve(),
        comparator=args.comparator.resolve(),
        network=args.network.resolve(),
        book=args.book.resolve(),
        cli=args.cli.resolve(),
        probe=args.probe.resolve(),
        qt_bin=args.qt_bin.resolve(),
        output_dir=args.output_dir.resolve(),
        lease=args.lease.resolve(),
    )
    require(not paths.output_dir.exists(), f"refusing to overwrite output root: {paths.output_dir}")
    authorization_sha256 = assert_exact_hash(
        paths.authorization,
        args.expected_authorization_sha256.lower(),
        "final strength authorization",
    )
    authorization = load_json(paths.authorization)
    snapshot_paths = validate_final_authorization(
        authorization,
        paths=paths,
        authorization_sha256=authorization_sha256,
    )
    fingerprints = fingerprint_assets(paths, snapshot_paths)
    validate_asset_identities(fingerprints)
    ancestry = verify_git_ancestry()
    implementation_provenance = verify_implementation_provenance(authorization)
    openings, schedule_sha256 = normalize_epd_book(paths.book.read_bytes())
    require(schedule_sha256 == EXPECTED_SCHEDULE_SHA256, "opening schedule identity drift")

    paths.output_dir.mkdir(parents=True, exist_ok=False)
    write_json_exclusive(paths.output_dir / "input-fingerprints.json", fingerprints)
    preflight = {
        "ancestry": ancestry,
        "authorization_sha256": authorization_sha256,
        "evidence_class": EVIDENCE_CLASS,
        "experiment_id": EXPERIMENT_ID,
        "host": {"machine": platform.machine(), "node": platform.node(), "platform": platform.platform()},
        "implementation_provenance": implementation_provenance,
        "opening_count": len(openings),
        "profile": PROFILE,
        "referee": REFEREE,
        "schedule_sha256": schedule_sha256,
        "started_at": utc_now(),
        "strength_games_started": 0,
    }
    write_json_exclusive(paths.output_dir / "preflight.json", preflight)

    candidate_options = (
        ("UCI_Variant", "antichess"),
        ("Antichess_Evaluator", "legacy-v1"),
        ("Antichess_Search", "alpha-beta-v1"),
        ("EvalFile", str(paths.network)),
        ("Threads", "1"),
        ("Hash", "512"),
    )
    comparator_options = (
        ("UCI_Variant", "antichess"),
        ("Use NNUE", "true"),
        ("EvalFile", str(paths.network)),
        ("Threads", "1"),
        ("Hash", "512"),
    )
    aggregate: dict[str, Any] | None = None
    try:
        candidate_compiler = compiler_preflight(
            paths.candidate,
            paths.output_dir / "candidate-compiler.log",
            label="candidate",
        )
        comparator_compiler = compiler_preflight(
            paths.comparator,
            paths.output_dir / "comparator-compiler.log",
            label="comparator",
        )
        require(candidate_compiler == comparator_compiler, "candidate/comparator compiler target mismatch")
        uci_playing_preflight(
            paths.candidate,
            candidate_options,
            paths.output_dir / "candidate-playing-preflight.log",
            expected_markers=("Loaded Antichess legacy-v1 network", str(paths.network)),
        )
        uci_playing_preflight(
            paths.comparator,
            comparator_options,
            paths.output_dir / "comparator-playing-preflight.log",
            expected_markers=("NNUE evaluation using", str(paths.network), "enabled"),
        )
        return_code, aggregate = run_campaign(
            paths,
            authorization_sha256=authorization_sha256,
            openings=openings,
        )
    except KeyboardInterrupt:
        failure = {
            "evidence_class": EVIDENCE_CLASS,
            "error": "operator interruption",
            "experiment_id": EXPERIMENT_ID,
            "finished_at": utc_now(),
            "status": "INVALIDATED_NO_STRENGTH_CONCLUSION",
        }
        if not (paths.output_dir / "campaign-failure.json").exists():
            write_json_exclusive(paths.output_dir / "campaign-failure.json", failure)
        return_code = 130
    except Exception as error:
        failure = {
            "evidence_class": EVIDENCE_CLASS,
            "error": str(error),
            "experiment_id": EXPERIMENT_ID,
            "finished_at": utc_now(),
            "status": "INVALIDATED_NO_STRENGTH_CONCLUSION",
        }
        if not (paths.output_dir / "campaign-failure.json").exists():
            write_json_exclusive(paths.output_dir / "campaign-failure.json", failure)
        return_code = 2

    postflight = fingerprint_assets(paths, snapshot_paths)
    drift = {
        label: {"before": fingerprints[label], "after": postflight.get(label)}
        for label in fingerprints
        if postflight.get(label) != fingerprints[label]
    }
    postflight_document = {
        "drift": drift,
        "finished_at": utc_now(),
        "input_fingerprints": postflight,
        "status": "PASS" if not drift else "FAIL_INPUT_DRIFT",
    }
    write_json_exclusive(paths.output_dir / "postflight.json", postflight_document)
    if drift:
        if not (paths.output_dir / "campaign-failure.json").exists():
            write_json_exclusive(
                paths.output_dir / "campaign-failure.json",
                {
                    "evidence_class": EVIDENCE_CLASS,
                    "error": "postflight input drift",
                    "experiment_id": EXPERIMENT_ID,
                    "finished_at": utc_now(),
                    "status": "INVALIDATED_NO_STRENGTH_CONCLUSION",
                },
            )
        return 2
    if return_code in {2, 130}:
        return return_code
    require(aggregate is not None, "campaign returned no aggregate result")
    write_json_exclusive(paths.output_dir / "aggregate-result.json", aggregate)
    return return_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as error:
        print(f"s3-strength-contract-error: {error}", file=sys.stderr)
        raise SystemExit(2)
