#!/usr/bin/env python3
"""Replay the S3 comparator plumbing smoke through AC_REFEREE_V1."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.strength.panel_contract_v1 import (  # noqa: E402
    EXPECTED_REFEREE_PROBE_SHA256,
    PROFILE,
    REFEREE,
    assert_exact_hash,
    require,
    validate_completed_pair,
    write_json_exclusive,
)
from tools.strength.run_fsf_pair_smoke_v1 import EVIDENCE_CLASS  # noqa: E402


DIAGNOSTIC_PREFIX = "referee-info "


def parse_diagnostic(output: str) -> dict[str, str]:
    lines = [line for line in output.splitlines() if line.startswith(DIAGNOSTIC_PREFIX)]
    require(len(lines) == 1, f"expected one referee diagnostic, got {len(lines)}")
    fields: dict[str, str] = {}
    for item in lines[0][len(DIAGNOSTIC_PREFIX) :].split("|"):
        key, separator, value = item.partition("=")
        require(bool(separator) and key not in fields, f"malformed or duplicate diagnostic field: {item!r}")
        fields[key] = value
    return fields


def run_probe(probe: Path, fen: str, moves: list[str], environment: dict[str, str]) -> dict[str, str]:
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
    require(completed.returncode == 0, f"referee rejected PGN replay: {completed.stdout}")
    return parse_diagnostic(completed.stdout)


def parse_games(text: str) -> list[tuple[dict[str, str], list[str], int]]:
    chunks = [chunk for chunk in re.split(r"(?m)(?=^\[Event )", text) if chunk.strip()]
    games: list[tuple[dict[str, str], list[str], int]] = []
    for chunk in chunks:
        tags = dict(re.findall(r'(?m)^\[([A-Za-z0-9_]+) "((?:\\.|[^"\\])*)"\]$', chunk))
        require(bool(tags), "PGN game has no tags")
        movetext = "\n".join(line for line in chunk.splitlines() if not line.startswith("["))
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
        move, separator, san = entry.partition("=")
        require(bool(separator) and move not in result, f"malformed or duplicate notation: {entry}")
        result[move] = san
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
    for path in (pgn, launch_path, qt_bin / "Qt6Core.dll"):
        require(path.is_file(), f"required input not found: {path}")
    require(not output.exists(), f"refusing to overwrite audit: {output}")
    assert_exact_hash(probe, EXPECTED_REFEREE_PROBE_SHA256, "AC_REFEREE_V1 probe")

    launch = json.loads(launch_path.read_text(encoding="utf-8"))
    require(launch.get("profile") == PROFILE, "launch profile drift")
    require(launch.get("referee") == REFEREE, "launch referee drift")
    require(launch.get("evidence_class") == EVIDENCE_CLASS, "evidence class drift")
    require(launch.get("games") == 2, "plumbing smoke must contain exactly two games")

    environment = os.environ.copy()
    environment["PATH"] = str(qt_bin) + os.pathsep + environment.get("PATH", "")
    games = parse_games(pgn.read_text(encoding="utf-8", errors="strict"))
    require(len(games) == 2, f"PGN game count {len(games)} != 2")

    mandatory_positions = 0
    terminal_san = 0
    total_clock_comments = 0
    total_plies = 0
    result_counts: Counter[str] = Counter()
    pair_records: list[dict[str, Any]] = []
    audited_games: list[dict[str, Any]] = []
    for game_index, (tags, sans, clock_comments) in enumerate(games, start=1):
        require(tags.get("Event") == "Antichess S3 plumbing smoke; not strength", f"game {game_index}: Event tag drift")
        require(tags.get("Variant") == "Antichess", f"game {game_index}: Variant tag drift")
        require(tags.get("FEN") == launch["opening_fen"], f"game {game_index}: FEN tag drift")
        require(tags.get("SetUp") == "1", f"game {game_index}: SetUp tag drift")
        require(tags.get("TimeControl") == launch["tc"], f"game {game_index}: time control drift")
        require(tags.get("Result") in {"1-0", "0-1", "1/2-1/2"}, f"game {game_index}: unfinished")
        require(int(tags.get("PlyCount", "-1")) == len(sans), f"game {game_index}: PlyCount drift")
        require(clock_comments == len(sans), f"game {game_index}: missing per-ply clock comments")

        moves: list[str] = []
        game_mandatory = 0
        for ply, san in enumerate(sans, start=1):
            fields = run_probe(probe, launch["opening_fen"], moves, environment)
            mapping = notation_map(fields)
            matches = [move for move, expected_san in mapping.items() if expected_san == san]
            require(len(matches) == 1, f"game {game_index} ply {ply}: SAN {san!r} is not uniquely legal")
            if fields["must_capture"] == "1":
                mandatory_positions += 1
                game_mandatory += 1
                require("x" in san, f"game {game_index} ply {ply}: compulsory capture lost in SAN")
            if san.endswith("#"):
                terminal_san += 1
                require(ply == len(sans), f"game {game_index}: terminal SAN before final ply")
            moves.append(matches[0])

        final = run_probe(probe, launch["opening_fen"], moves, environment)
        expected_winner = "white" if tags["Result"] == "1-0" else "black" if tags["Result"] == "0-1" else "none"
        require(final["end"] == "1", f"game {game_index}: PGN ended in an ongoing position")
        require(final["board_result"] == ("draw" if expected_winner == "none" else "win"), f"game {game_index}: result-class drift")
        require(final["board_result_winner"] == expected_winner, f"game {game_index}: winner drift")
        if expected_winner != "none":
            require(bool(sans) and sans[-1].endswith("#"), f"game {game_index}: winning move lacks terminal SAN")

        pair_records.append(
            {
                "black": tags["Black"],
                "defects": [],
                "fen": tags["FEN"],
                "result": tags["Result"],
                "terminal_marker": final["end"] == "1",
                "time_control": tags["TimeControl"],
                "variant": tags["Variant"],
                "white": tags["White"],
            }
        )
        audited_games.append(
            {
                "black": tags["Black"],
                "final_board_result": final["board_result"],
                "final_winner": final["board_result_winner"],
                "mandatory_positions": game_mandatory,
                "plies": len(sans),
                "result": tags["Result"],
                "white": tags["White"],
            }
        )
        result_counts[tags["Result"]] += 1
        total_clock_comments += clock_comments
        total_plies += len(sans)

    validate_completed_pair(
        pair_records,
        candidate=launch["candidate_name"],
        comparator=launch["comparator_name"],
        opening_fen=launch["opening_fen"],
        time_control=launch["tc"],
    )
    require(mandatory_positions > 0, "PGN never exercised compulsory capture")
    require(terminal_san == 2, f"terminal SAN count {terminal_san} != 2")

    audit = {
        "evidence_class": EVIDENCE_CLASS,
        "games": audited_games,
        "mandatory_positions": mandatory_positions,
        "profile": PROFILE,
        "referee": REFEREE,
        "result_counts": dict(sorted(result_counts.items())),
        "terminal_san_moves": terminal_san,
        "total_clock_comments": total_clock_comments,
        "total_plies": total_plies,
    }
    write_json_exclusive(output, audit)
    print(
        f"{REFEREE} S3 PGN audit passed: 2 games, {total_plies} plies, "
        f"{mandatory_positions} compulsory-capture positions, {terminal_san} terminal SAN moves"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"s3-pair-audit-error: {error}", file=sys.stderr)
        raise SystemExit(1)
