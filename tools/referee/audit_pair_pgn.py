#!/usr/bin/env python3
"""Replay a pair-smoke PGN through the exact AC_REFEREE_V1 probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"
EXPECTED_PROBE_SHA256 = "fd45f1f066ce6ff3017a193d5333ccc95e676f9fc795cdd74722abac7564b109"
DIAGNOSTIC_PREFIX = "referee-info "


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_diagnostic(output: str) -> dict[str, str]:
    lines = [line for line in output.splitlines() if line.startswith(DIAGNOSTIC_PREFIX)]
    require(len(lines) == 1, f"expected one referee diagnostic, got {len(lines)}")
    fields: dict[str, str] = {}
    for item in lines[0][len(DIAGNOSTIC_PREFIX) :].split("|"):
        key, separator, value = item.partition("=")
        require(bool(separator), f"malformed diagnostic field: {item!r}")
        fields[key] = value
    return fields


def run_probe(
    probe: Path,
    fen: str,
    moves: list[str],
    environment: dict[str, str],
) -> dict[str, str]:
    completed = subprocess.run(
        [str(probe), fen, *moves],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    require(completed.returncode == 0, f"referee rejected replay: {completed.stdout}")
    return parse_diagnostic(completed.stdout)


def parse_games(text: str) -> list[tuple[dict[str, str], list[str], int]]:
    chunks = [chunk for chunk in re.split(r"(?m)(?=^\[Event )", text) if chunk.strip()]
    games: list[tuple[dict[str, str], list[str], int]] = []
    for chunk in chunks:
        tags = dict(re.findall(r'(?m)^\[([A-Za-z0-9_]+) "((?:\\.|[^"\\])*)"\]$', chunk))
        require(bool(tags), "PGN game has no tags")
        movetext_lines = [line for line in chunk.splitlines() if not line.startswith("[")]
        movetext = "\n".join(movetext_lines)
        clock_comments = len(re.findall(r"\{[^{}]*\b\d+(?:\.\d+)?s(?:, [^{}]*)?\}", movetext))
        movetext = re.sub(r"\{[^{}]*\}", " ", movetext)
        movetext = re.sub(r"(?m);.*$", " ", movetext)
        require("(" not in movetext and ")" not in movetext, "PGN variations are not allowed")
        movetext = re.sub(r"\b\d+\.(?:\.\.)?", " ", movetext)
        tokens = [token for token in movetext.split() if not token.startswith("$")]
        results = [token for token in tokens if token in {"1-0", "0-1", "1/2-1/2", "*"}]
        require(results == [tags.get("Result")], "PGN movetext result disagrees with Result tag")
        sans = [token for token in tokens if token not in {"1-0", "0-1", "1/2-1/2", "*"}]
        games.append((tags, sans, clock_comments))
    return games


def notation_map(fields: dict[str, str]) -> dict[str, str]:
    entries = [entry for entry in fields["notation"].split(",") if entry]
    result: dict[str, str] = {}
    for entry in entries:
        uci, separator, san = entry.partition("=")
        require(bool(separator) and uci not in result, f"malformed or duplicate notation: {entry}")
        result[uci] = san
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pgn", required=True, type=Path)
    parser.add_argument("--launch", required=True, type=Path)
    parser.add_argument("--probe", required=True, type=Path)
    parser.add_argument("--qt-bin", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    pgn = args.pgn.resolve()
    launch_path = args.launch.resolve()
    probe = args.probe.resolve()
    qt_bin = args.qt_bin.resolve()
    output = args.output.resolve()
    for path in (pgn, launch_path, probe, qt_bin / "Qt6Core.dll"):
        require(path.exists(), f"required input not found: {path}")
    require(not output.exists(), f"refusing to overwrite audit: {output}")
    require(sha256(probe) == EXPECTED_PROBE_SHA256, "referee probe hash drift")

    launch = json.loads(launch_path.read_text(encoding="utf-8"))
    require(launch["profile"] == "LICHESS_ANTICHESS_V1", "launch profile drift")
    require(launch["referee"] == "AC_REFEREE_V1", "launch referee drift")
    require(launch["evidence_class"] == "P4_PAIR_SMOKE_NOT_STRENGTH", "evidence class drift")

    environment = os.environ.copy()
    environment["PATH"] = str(qt_bin) + os.pathsep + environment.get("PATH", "")
    games = parse_games(pgn.read_text(encoding="utf-8", errors="strict"))
    require(len(games) == launch["games"], "PGN game count disagrees with launch")

    color_counts: Counter[tuple[str, str]] = Counter()
    result_counts: Counter[str] = Counter()
    total_plies = 0
    total_clock_comments = 0
    mandatory_positions = 0
    terminal_san = 0
    per_game: list[dict[str, Any]] = []
    for game_index, (tags, sans, clock_comments) in enumerate(games, start=1):
        require(tags.get("Variant") == "Antichess", f"game {game_index}: wrong Variant tag")
        require(tags.get("TimeControl") == launch["tc"], f"game {game_index}: time control drift")
        require(tags.get("Result") in {"1-0", "0-1", "1/2-1/2"}, f"game {game_index}: unfinished")
        require(int(tags.get("PlyCount", "-1")) == len(sans), f"game {game_index}: PlyCount drift")
        require(clock_comments == len(sans), f"game {game_index}: missing per-ply clock comments")
        color_counts[(tags["White"], tags["Black"])] += 1
        result_counts[tags["Result"]] += 1

        initial_fen = tags.get("FEN", START_FEN)
        moves: list[str] = []
        game_mandatory = 0
        for ply, san in enumerate(sans, start=1):
            fields = run_probe(probe, initial_fen, moves, environment)
            mapping = notation_map(fields)
            matches = [uci for uci, expected_san in mapping.items() if expected_san == san]
            require(len(matches) == 1, f"game {game_index} ply {ply}: SAN {san!r} is not uniquely legal")
            if fields["must_capture"] == "1":
                mandatory_positions += 1
                game_mandatory += 1
                require("x" in san, f"game {game_index} ply {ply}: capture obligation lost in SAN")
            if san.endswith("#"):
                terminal_san += 1
                require(ply == len(sans), f"game {game_index}: terminal SAN before final ply")
            moves.append(matches[0])

        final = run_probe(probe, initial_fen, moves, environment)
        expected_winner = "white" if tags["Result"] == "1-0" else "black" if tags["Result"] == "0-1" else "none"
        require(final["end"] == "1", f"game {game_index}: PGN ended in an ongoing position")
        require(final["board_result"] == ("draw" if expected_winner == "none" else "win"), f"game {game_index}: result-class drift")
        require(final["board_result_winner"] == expected_winner, f"game {game_index}: winner drift")
        if expected_winner != "none":
            require(sans[-1].endswith("#"), f"game {game_index}: winning move lacks terminal SAN")

        total_plies += len(sans)
        total_clock_comments += clock_comments
        per_game.append(
            {
                "black": tags["Black"],
                "mandatory_positions": game_mandatory,
                "plies": len(sans),
                "result": tags["Result"],
                "white": tags["White"],
            }
        )

    require(color_counts[("Candidate-A", "Candidate-B")] == 1, "Candidate-A white balance drift")
    require(color_counts[("Candidate-B", "Candidate-A")] == 1, "Candidate-B white balance drift")
    require(mandatory_positions > 0, "PGN never exercised compulsory capture")
    require(terminal_san == sum(count for result, count in result_counts.items() if result != "1/2-1/2"), "terminal SAN count drift")

    audit = {
        "games": per_game,
        "identities": {
            "pgn_sha256": sha256(pgn),
            "probe_sha256": sha256(probe),
        },
        "mandatory_positions": mandatory_positions,
        "profile": launch["profile"],
        "referee": launch["referee"],
        "result_counts": dict(sorted(result_counts.items())),
        "terminal_san_moves": terminal_san,
        "total_clock_comments": total_clock_comments,
        "total_plies": total_plies,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as destination:
        json.dump(audit, destination, indent=2, sort_keys=True)
        destination.write("\n")

    print(
        f"AC_REFEREE_V1 PGN audit passed: {len(games)} games, {total_plies} plies, "
        f"{mandatory_positions} mandatory-capture positions, {terminal_san} terminal SAN moves"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
