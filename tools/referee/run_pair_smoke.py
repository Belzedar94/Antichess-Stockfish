#!/usr/bin/env python3
"""Run one bounded AC_REFEREE_V1 self-pair and preserve raw evidence."""

from __future__ import annotations

import argparse
import hashlib
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


PROFILE = "LICHESS_ANTICHESS_V1"
REFEREE = "AC_REFEREE_V1"
EXPECTED_NET_SHA256 = "dd3cbe53cd4e1ca5b7f41cf090873ebe732d84d27f9ed7b14c62ff7a633712cc"
EXPECTED_CLI_SHA256 = "62377837474f166edfae5dcc5801b19bdf0ee28c89ac4bc66832d535be73ae9f"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as destination:
        json.dump(value, destination, indent=2, sort_keys=True)
        destination.write("\n")


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--net", required=True, type=Path)
    parser.add_argument("--qt-bin", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-engine-sha256", required=True)
    parser.add_argument("--games", type=int, default=2)
    parser.add_argument("--tc", default="2+0.05")
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--maxmoves", type=int, default=80)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()

    cli = args.cli.resolve()
    engine = args.engine.resolve()
    net = args.net.resolve()
    qt_bin = args.qt_bin.resolve()
    output_dir = args.output_dir.resolve()
    require(cli.is_file(), f"Cute Chess CLI not found: {cli}")
    require(engine.is_file(), f"candidate engine not found: {engine}")
    require(net.is_file(), f"legacy network not found: {net}")
    require((qt_bin / "Qt6Core.dll").is_file(), f"Qt runtime not found: {qt_bin}")
    require(not output_dir.exists(), f"refusing to overwrite evidence directory: {output_dir}")
    require(args.games > 0 and args.games % 2 == 0, "games must be a positive even number")
    require(args.depth > 0, "depth must be positive")
    require(args.maxmoves > 0, "maxmoves must be positive for a bounded smoke")
    require(args.timeout_seconds > 0, "timeout must be positive")

    identities = {
        "cli_sha256": sha256(cli),
        "engine_sha256": sha256(engine),
        "net_sha256": sha256(net),
    }
    require(identities["cli_sha256"] == EXPECTED_CLI_SHA256, "unexpected referee CLI")
    require(
        identities["engine_sha256"] == args.expected_engine_sha256.lower(),
        "candidate engine hash drift",
    )
    require(identities["net_sha256"] == EXPECTED_NET_SHA256, "legacy network hash drift")

    output_dir.mkdir(parents=True)
    raw_log = output_dir / "raw.log"
    pgn = output_dir / "games.pgn"
    epd = output_dir / "end-positions.epd"

    engine_options = [
        "proto=uci",
        "restart=off",
        "option.Antichess_Evaluator=legacy-v1",
        f"option.EvalFile={net}",
    ]
    command = [
        str(cli),
        "-engine",
        "name=Candidate-A",
        f"cmd={engine}",
        f"dir={engine.parent}",
        *engine_options,
        "-engine",
        "name=Candidate-B",
        f"cmd={engine}",
        f"dir={engine.parent}",
        *engine_options,
        "-each",
        f"tc={args.tc}",
        f"depth={args.depth}",
        "timemargin=200",
        "-variant",
        "antichess",
        "-tournament",
        "round-robin",
        "-games",
        str(args.games),
        "-rounds",
        "1",
        "-concurrency",
        "1",
        "-maxmoves",
        str(args.maxmoves),
        "-debug",
        "-pgnout",
        str(pgn),
        "fi",
        "-epdout",
        str(epd),
    ]

    environment = os.environ.copy()
    environment["PATH"] = str(qt_bin) + os.pathsep + environment.get("PATH", "")
    started_at = utc_now()
    start = time.monotonic()
    with raw_log.open("xb") as log:
        process = subprocess.Popen(
            command,
            cwd=output_dir,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        write_json(
            output_dir / "launch.json",
            {
                "command": command,
                "evidence_class": "P4_PAIR_SMOKE_NOT_STRENGTH",
                "depth": args.depth,
                "games": args.games,
                "host": {
                    "machine": platform.machine(),
                    "node": platform.node(),
                    "platform": platform.platform(),
                },
                "identities": identities,
                "maxmoves": args.maxmoves,
                "pid": process.pid,
                "profile": PROFILE,
                "referee": REFEREE,
                "started_at": started_at,
                "tc": args.tc,
                "timeout_seconds": args.timeout_seconds,
            },
        )
        timed_out = False
        try:
            return_code = process.wait(timeout=args.timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            return_code = process.wait(timeout=30)

    elapsed = time.monotonic() - start
    log_text = raw_log.read_text(encoding="utf-8", errors="replace")
    required_patterns = {
        "variant_option": r"setoption name UCI_Variant value antichess",
        "evaluator_option": r"setoption name Antichess_Evaluator value legacy-v1",
        "network_option": r"setoption name EvalFile value ",
        "network_loaded": r"Loaded Antichess legacy-v1 network",
        "clock_search": r"\bgo\b.*\b[wb]time\b",
        "bestmove": r"\bbestmove\b",
        "readyok": r"\breadyok\b",
        "uciok": r"\buciok\b",
    }
    pattern_counts = {
        name: len(re.findall(pattern, log_text, flags=re.IGNORECASE))
        for name, pattern in required_patterns.items()
    }
    forbidden_patterns = {
        "crash": r"\bcrash(?:ed)?\b",
        "disconnect": r"\bdisconnect(?:ed)?\b",
        "illegal_move": r"\billegal move\b",
        "stall": r"\bstall(?:ed)?\b",
        "time_loss": r"\blost on time\b|\btime forfeit\b",
    }
    forbidden_counts = {
        name: len(re.findall(pattern, log_text, flags=re.IGNORECASE))
        for name, pattern in forbidden_patterns.items()
    }

    artifacts: dict[str, dict[str, Any]] = {}
    for artifact in (raw_log, pgn, epd):
        if artifact.is_file():
            artifacts[artifact.name] = {
                "bytes": artifact.stat().st_size,
                "sha256": sha256(artifact),
            }
    result = {
        "artifacts": artifacts,
        "elapsed_seconds": elapsed,
        "finished_at": utc_now(),
        "forbidden_pattern_counts": forbidden_counts,
        "pattern_counts": pattern_counts,
        "return_code": return_code,
        "timed_out": timed_out,
    }
    write_json(output_dir / "result.json", result)

    require(not timed_out, "pair smoke timed out; inspect preserved process/log evidence")
    require(return_code == 0, f"Cute Chess exited {return_code}; inspect raw.log")
    require(pgn.is_file() and pgn.stat().st_size > 0, "pair smoke produced no PGN")
    require(all(count > 0 for count in pattern_counts.values()), "raw UCI mapping evidence incomplete")
    require(all(count == 0 for count in forbidden_counts.values()), "raw log contains a forbidden failure marker")
    require('[Variant "Antichess"]' in pgn.read_text(encoding="utf-8", errors="strict"), "PGN lacks exact Variant tag")

    print(
        f"{REFEREE} pair smoke passed: {args.games} games, "
        f"{elapsed:.3f}s, raw={artifacts['raw.log']['sha256']}, "
        f"pgn={artifacts['games.pgn']['sha256']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"pair-smoke-error: {error}", file=sys.stderr)
        raise SystemExit(1)
