#!/usr/bin/env python3
"""Run the single preregistered two-game S3 plumbing smoke."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.strength.panel_contract_v1 import (  # noqa: E402
    EXPECTED_FSF_BINARY_SHA256,
    EXPECTED_NETWORK_SHA256,
    EXPECTED_QT_CORE_SHA256,
    EXPECTED_REFEREE_CLI_SHA256,
    PROFILE,
    REFEREE,
    assert_exact_hash,
    load_json,
    require,
    scan_forbidden_log,
    sha256_file,
    write_json_exclusive,
)


OPENING_FEN = "8/8/8/3p4/4B3/8/8/8 w - - 0 1"
OPENING_EPD = "8/8/8/3p4/4B3/8/8/8 w - -"
EVIDENCE_CLASS = "S3_PAIR_PLUMBING_SMOKE_NOT_STRENGTH"
AUTHORIZATION_SCHEMA = "ANTICHESS_S3_PAIR_PLUMBING_SMOKE_V1_AUTHORIZATION"
CANDIDATE_NAME = "Antichess-Stockfish"
COMPARATOR_NAME = "Fairy-Stockfish"


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def validate_authorization(authorization: dict[str, Any], output_dir: Path) -> str:
    require(authorization.get("schema") == AUTHORIZATION_SCHEMA, "plumbing-smoke authorization schema drift")
    require(authorization.get("authorized") is True, "plumbing smoke is not authorized")
    require(authorization.get("profile") == PROFILE, "plumbing-smoke profile drift")
    require(authorization.get("referee") == REFEREE, "plumbing-smoke referee drift")
    require(authorization.get("evidence_class") == EVIDENCE_CLASS, "plumbing-smoke evidence class drift")
    require(authorization.get("games") == 2, "plumbing-smoke game authorization drift")
    require(authorization.get("strength_games") == 0, "plumbing smoke was mislabeled as strength")
    require(Path(str(authorization.get("output_dir"))).resolve() == output_dir, "plumbing-smoke output authorization drift")
    candidate_expected_sha256 = authorization.get("candidate_binary_sha256")
    require(isinstance(candidate_expected_sha256, str), "authorized candidate hash missing")
    return candidate_expected_sha256


def terminate_owned_tree(process: subprocess.Popen[bytes]) -> int:
    if process.poll() is not None:
        return int(process.returncode)
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        )
    else:
        process.kill()
    return process.wait(timeout=30)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--comparator", required=True, type=Path)
    parser.add_argument("--net", required=True, type=Path)
    parser.add_argument("--qt-bin", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--expected-authorization-sha256", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()

    cli = args.cli.resolve()
    candidate = args.candidate.resolve()
    comparator = args.comparator.resolve()
    net = args.net.resolve()
    qt_bin = args.qt_bin.resolve()
    output_dir = args.output_dir.resolve()
    authorization_path = args.authorization.resolve()
    require(not output_dir.exists(), f"refusing to overwrite evidence directory: {output_dir}")
    require(args.timeout_seconds > 0, "timeout must be positive")

    authorization_sha256 = assert_exact_hash(
        authorization_path,
        args.expected_authorization_sha256.lower(),
        "plumbing-smoke authorization",
    )
    authorization = load_json(authorization_path)
    candidate_expected_sha256 = validate_authorization(authorization, output_dir)

    identities = {
        "authorization_sha256": authorization_sha256,
        "candidate_sha256": assert_exact_hash(candidate, candidate_expected_sha256, "candidate"),
        "cli_sha256": assert_exact_hash(cli, EXPECTED_REFEREE_CLI_SHA256, "AC_REFEREE_V1 CLI"),
        "comparator_sha256": assert_exact_hash(comparator, EXPECTED_FSF_BINARY_SHA256, "Fairy-Stockfish comparator"),
        "network_sha256": assert_exact_hash(net, EXPECTED_NETWORK_SHA256, "legacy network"),
        "qt_core_sha256": assert_exact_hash(qt_bin / "Qt6Core.dll", EXPECTED_QT_CORE_SHA256, "Qt6Core runtime"),
    }
    for key, actual in (
        ("candidate_binary_sha256", identities["candidate_sha256"]),
        ("comparator_binary_sha256", identities["comparator_sha256"]),
        ("network_sha256", identities["network_sha256"]),
        ("referee_cli_sha256", identities["cli_sha256"]),
        ("qt_core_sha256", identities["qt_core_sha256"]),
    ):
        require(authorization.get(key) == actual, f"plumbing-smoke authorized {key} drift")

    output_dir.mkdir(parents=True)
    raw_log = output_dir / "raw.log"
    pgn = output_dir / "games.pgn"
    epd_output = output_dir / "end-positions.epd"
    opening = output_dir / "forced-terminal-opening.epd"
    opening.write_text(OPENING_EPD + "\n", encoding="ascii", newline="\n")

    command = [
        str(cli),
        "-engine",
        f"name={CANDIDATE_NAME}",
        f"cmd={candidate}",
        f"dir={candidate.parent}",
        "proto=uci",
        "restart=on",
        "option.UCI_Variant=antichess",
        "option.Antichess_Evaluator=legacy-v1",
        "option.Antichess_Search=alpha-beta-v1",
        f"option.EvalFile={net}",
        "option.Threads=1",
        "option.Hash=512",
        "-engine",
        f"name={COMPARATOR_NAME}",
        f"cmd={comparator}",
        f"dir={comparator.parent}",
        "proto=uci",
        "restart=on",
        "option.UCI_Variant=antichess",
        "option.Use NNUE=true",
        f"option.EvalFile={net}",
        "option.Threads=1",
        "option.Hash=512",
        "-each",
        "tc=2+0.05",
        "depth=1",
        "timemargin=200",
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
        "-maxmoves",
        "20",
        "-openings",
        f"file={opening}",
        "format=epd",
        "order=sequential",
        "plies=1024",
        "start=1",
        "-debug",
        "-pgnout",
        str(pgn),
        "fi",
        "-epdout",
        str(epd_output),
        "-event",
        "Antichess S3 plumbing smoke; not strength",
    ]

    environment = os.environ.copy()
    environment["PATH"] = str(qt_bin) + os.pathsep + environment.get("PATH", "")
    started_at = utc_now()
    started = time.monotonic()
    with raw_log.open("xb") as log:
        process = subprocess.Popen(
            command,
            cwd=output_dir,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        write_json_exclusive(
            output_dir / "launch.json",
            {
                "candidate_name": CANDIDATE_NAME,
                "command": command,
                "comparator_name": COMPARATOR_NAME,
                "depth": 1,
                "evidence_class": EVIDENCE_CLASS,
                "games": 2,
                "host": {
                    "machine": platform.machine(),
                    "node": platform.node(),
                    "platform": platform.platform(),
                },
                "identities": identities,
                "opening_fen": OPENING_FEN,
                "pid": process.pid,
                "profile": PROFILE,
                "referee": REFEREE,
                "started_at": started_at,
                "tc": "2+0.05",
                "timeout_seconds": args.timeout_seconds,
            },
        )
        timed_out = False
        try:
            return_code = process.wait(timeout=args.timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            return_code = terminate_owned_tree(process)

    elapsed = time.monotonic() - started
    log_text = raw_log.read_text(encoding="utf-8", errors="replace")
    forbidden = scan_forbidden_log(log_text)
    required = {
        "candidate_variant": len(re.findall(r"setoption name UCI_Variant value antichess", log_text, re.IGNORECASE)),
        "candidate_evaluator": len(re.findall(r"setoption name Antichess_Evaluator value legacy-v1", log_text, re.IGNORECASE)),
        "candidate_search": len(re.findall(r"setoption name Antichess_Search value alpha-beta-v1", log_text, re.IGNORECASE)),
        "network_path": log_text.count(str(net)),
        "network_loaded_candidate": len(re.findall(r"Loaded Antichess legacy-v1 network", log_text)),
        "network_loaded_comparator": len(re.findall(r"NNUE evaluation using .* enabled", log_text)),
        "hash_512": len(re.findall(r"setoption name Hash value 512", log_text, re.IGNORECASE)),
        "threads_1": len(re.findall(r"setoption name Threads value 1", log_text, re.IGNORECASE)),
        "bestmove": len(re.findall(r"\bbestmove\b", log_text, re.IGNORECASE)),
    }
    artifacts: dict[str, dict[str, Any]] = {}
    for artifact in (raw_log, pgn, epd_output, opening):
        if artifact.is_file():
            artifacts[artifact.name] = {"bytes": artifact.stat().st_size, "sha256": sha256_file(artifact)}
    result = {
        "artifacts": artifacts,
        "elapsed_seconds": elapsed,
        "finished_at": utc_now(),
        "forbidden_pattern_counts": forbidden,
        "required_pattern_counts": required,
        "return_code": return_code,
        "timed_out": timed_out,
    }
    write_json_exclusive(output_dir / "result.json", result)

    require(not timed_out, "plumbing smoke timed out; owned process-tree evidence was preserved")
    require(return_code == 0, f"Cute Chess exited {return_code}; inspect raw.log")
    require(pgn.is_file() and pgn.stat().st_size > 0, "plumbing smoke produced no PGN")
    require(all(value > 0 for value in required.values()), "raw UCI option/load evidence is incomplete")
    require(all(value == 0 for value in forbidden.values()), "raw log contains a forbidden failure marker")
    require('[Variant "Antichess"]' in pgn.read_text(encoding="utf-8"), "PGN lacks exact Variant tag")
    print(
        f"{REFEREE} S3 plumbing smoke completed: 2 games, {elapsed:.3f}s, "
        f"raw={artifacts['raw.log']['sha256']}, pgn={artifacts['games.pgn']['sha256']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"s3-pair-smoke-error: {error}", file=sys.stderr)
        raise SystemExit(1)
