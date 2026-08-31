#!/usr/bin/env python3
"""Verify the dedicated UCI binary against the frozen Antichess contracts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PREFIX = "antichess-info "


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def command(fen: str, moves: list[str] | None = None) -> str:
    suffix = "" if not moves else " moves " + " ".join(moves)
    return f"position fen {fen}{suffix}\nantichess-info\n"


def run(binary: Path, text: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(binary)],
        input=text + "quit\n",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def parse_line(line: str) -> dict[str, str]:
    require(line.startswith(PREFIX), f"unexpected diagnostic prefix: {line!r}")
    fields: dict[str, str] = {}
    for item in line[len(PREFIX) :].split("|"):
        key, separator, value = item.partition("=")
        require(bool(separator), f"malformed diagnostic field: {item!r}")
        fields[key] = value
    return fields


def parse_searches(output: str) -> list[tuple[str, int, str]]:
    infos: list[tuple[str, int]] = []
    bestmoves: list[str] = []
    for line in output.splitlines():
        match = re.search(r"^info depth \d+ .* score (mate|cp) (-?\d+) .* pv (\S+)", line)
        if match:
            infos.append((match.group(1), int(match.group(2))))
        if line.startswith("bestmove "):
            bestmoves.append(line.split()[1])
    require(len(infos) == len(bestmoves), "search info/bestmove count mismatch")
    return [(kind, score, bestmove) for (kind, score), bestmove in zip(infos, bestmoves, strict=True)]


def bool_text(value: bool) -> str:
    return "1" if value else "0"


def expected_text(value: Any) -> str:
    return "none" if value is None else str(value)


def verify_expected(fixture_id: str, actual: dict[str, str], expected: dict[str, Any]) -> int:
    checks = {
        "profile": "LICHESS_ANTICHESS_V1",
        "fen": expected["canonical_fen"],
        "legal": ",".join(expected["legal_moves"]),
        "end": bool_text(expected["end"]),
        "variant_end": bool_text(expected["variant_end"]),
        "automatic_draw": bool_text(expected["automatic_draw"]),
        "threefold": bool_text(expected["threefold"]),
        "fivefold": bool_text(expected["fivefold"]),
        "status": expected_text(expected["status"]),
        "winner": expected_text(expected["winner"]),
        "check": bool_text(expected["check"]),
        "player_insufficient": bool_text(expected["player_insufficient"]),
        "opponent_insufficient": bool_text(expected["opponent_insufficient"]),
        "halfmove_clock": str(expected["halfmove_clock"]),
        "uci_variant": "antichess",
        "evaluator": "engineering-neutral",
        "search": "exhaustive-v1",
        "threads": "1",
        "hash_mb": "1",
        "network_loaded": "0",
        "network_format": "none",
        "network_file": "none",
        "network_description_bytes": "0",
    }
    for key, value in checks.items():
        require(actual.get(key) == value, f"{fixture_id}: {key}: {actual.get(key)!r} != {value!r}")
    return len(checks)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True, type=Path)
    args = parser.parse_args()
    binary = args.engine.resolve()
    require(binary.is_file(), f"engine not found: {binary}")

    option_probe = run(
        binary,
        "uci\n"
        "setoption name UCI_Variant value chess\n"
        "setoption name Antichess_Evaluator value orthodox\n"
        "setoption name Antichess_Search value orthodox\n"
        "setoption name Threads value 1\n"
        "setoption name Hash value 1\n"
        "position startpos\n"
        "antichess-info\n",
    )
    require(option_probe.returncode == 0, "UCI option probe failed")
    option_names = [
        match.group(1)
        for line in option_probe.stdout.splitlines()
        if (match := re.match(r"^option name (.+?) type ", line))
    ]
    require(
        option_names
        == [
            "Debug Log File",
            "NumaPolicy",
            "Threads",
            "Hash",
            "Clear Hash",
            "UCI_Variant",
            "Antichess_Evaluator",
            "Antichess_Search",
            "EvalFile",
        ],
        f"unexpected UCI option surface: {option_names}",
    )
    option_info = next(
        parse_line(line) for line in option_probe.stdout.splitlines() if line.startswith(PREFIX)
    )
    require(option_info["uci_variant"] == "antichess", "invalid variant option persisted")
    require(option_info["evaluator"] == "engineering-neutral", "invalid evaluator persisted")
    require(option_info["search"] == "exhaustive-v1", "invalid search option persisted")
    require(option_info["threads"] == "1", "thread option did not persist")
    require(option_info["hash_mb"] == "1", "hash option did not persist")

    search_option_probe = run(
        binary,
        "uci\n"
        "setoption name Antichess_Search value alpha-beta-v1\n"
        "ucinewgame\n"
        "isready\n"
        "position startpos\n"
        "antichess-info\n"
        "setoption name Antichess_Search value invalid\n"
        "antichess-info\n",
    )
    require(search_option_probe.returncode == 0, "search option persistence probe failed")
    search_option_info = [
        parse_line(line)
        for line in search_option_probe.stdout.splitlines()
        if line.startswith(PREFIX)
    ]
    require(len(search_option_info) == 2, "search option diagnostic count mismatch")
    require(
        all(info["search"] == "alpha-beta-v1" for info in search_option_info),
        "alpha-beta search option did not persist",
    )

    core = load("tests/antichess/fixtures/core-v1.json")
    material = load("tests/antichess/fixtures/material-boundaries-v1.json")
    repetition = load("tests/antichess/fixtures/repetition-boundaries-v1.json")
    parser_boundaries = load("tests/antichess/fixtures/parser-boundaries-v1.json")
    search_boundaries = load("tests/antichess/fixtures/search-boundaries-v1.json")

    cases: list[tuple[str, str, list[str] | None, dict[str, Any]]] = []
    for fixture in core["position_fixtures"]:
        cases.append((fixture["id"], fixture["fen"], None, fixture["expected"]))
    for fixture in core["history_fixtures"]:
        cases.append((fixture["id"], fixture["initial_fen"], fixture["moves"], fixture["expected"]))
    for fixture in material["history_cases"]:
        cases.append((fixture["id"], fixture["initial_fen"], fixture["moves"], fixture["expected"]))

    batch = "uci\nisready\n" + "".join(command(fen, moves) for _, fen, moves, _ in cases)
    completed = run(binary, batch, timeout=max(30, len(cases) * 2))
    require(completed.returncode == 0, f"valid fixture batch exited {completed.returncode}:\n{completed.stdout}")
    lines = [line for line in completed.stdout.splitlines() if line.startswith(PREFIX)]
    require(len(lines) == len(cases), f"expected {len(cases)} diagnostics, got {len(lines)}")

    check_count = 0
    for (fixture_id, _, _, expected), line in zip(cases, lines, strict=True):
        check_count += verify_expected(fixture_id, parse_line(line), expected)

    # Repetition boundary cases intentionally carry a smaller result schema.
    boundary_commands: list[tuple[str, str, list[str] | None, dict[str, bool]]] = []
    for fixture in repetition["position_cases"]:
        boundary_commands.append((fixture["id"], fixture["fen"], None, fixture["expected"]))
    for fixture in repetition["history_cases"]:
        boundary_commands.append(
            (fixture["id"], fixture["initial_fen"], fixture["moves"], fixture["expected"])
        )
    completed = run(
        binary,
        "".join(command(fen, moves) for _, fen, moves, _ in boundary_commands),
    )
    require(completed.returncode == 0, f"repetition boundary batch exited {completed.returncode}")
    lines = [line for line in completed.stdout.splitlines() if line.startswith(PREFIX)]
    require(len(lines) == len(boundary_commands), "repetition diagnostic count mismatch")
    for (fixture_id, _, _, expected), line in zip(boundary_commands, lines, strict=True):
        actual = parse_line(line)
        require(actual["threefold"] == bool_text(expected["claimable"]), f"{fixture_id}: claim")
        require(actual["automatic_draw"] == bool_text(expected["automatic"]), f"{fixture_id}: auto")
        check_count += 2

    accepted = [
        fixture
        for fixture in [*core["parser_fixtures"], *parser_boundaries["cases"]]
        if fixture["project_policy"] == "accept"
    ]
    completed = run(binary, "".join(command(fixture["fen"]) for fixture in accepted))
    require(completed.returncode == 0, f"accepted parser batch exited {completed.returncode}")
    lines = [line for line in completed.stdout.splitlines() if line.startswith(PREFIX)]
    require(len(lines) == len(accepted), "accepted parser diagnostic count mismatch")
    check_count += len(accepted)

    rejected = [
        fixture
        for fixture in [*core["parser_fixtures"], *parser_boundaries["cases"]]
        if fixture["project_policy"] == "reject"
    ]
    for fixture in rejected:
        completed = run(binary, command(fixture["fen"]))
        require(completed.returncode != 0, f"{fixture['id']}: malformed FEN was accepted")
        require("Invalid en-passant square" in completed.stdout, f"{fixture['id']}: wrong rejection")
        check_count += 2

    for fixture in core["move_rejection_fixtures"]:
        completed = run(binary, command(fixture["fen"], [fixture["move"]]))
        require(completed.returncode != 0, f"{fixture['id']}: illegal move was accepted")
        require(f"Illegal move: {fixture['move']}" in completed.stdout, f"{fixture['id']}: wrong rejection")
        check_count += 2

    search_text = ""
    for fixture in search_boundaries["cases"]:
        search_text += command(fixture["initial_fen"], fixture["moves"]).replace(
            "antichess-info\n", f"go depth {fixture['depth']}\n"
        )
    completed = run(binary, search_text)
    require(completed.returncode == 0, f"search boundary batch exited {completed.returncode}")
    searches = parse_searches(completed.stdout)
    require(len(searches) == len(search_boundaries["cases"]), "search boundary count mismatch")
    for fixture, (kind, score, bestmove) in zip(
        search_boundaries["cases"], searches, strict=True
    ):
        expected = fixture["expected"]
        require(bestmove in expected["bestmoves"], f"{fixture['id']}: bestmove {bestmove}")
        if "score_type" in expected:
            require(kind == expected["score_type"], f"{fixture['id']}: score type {kind}")
            require(score == expected["score"], f"{fixture['id']}: score {score}")
            check_count += 3
        else:
            require(kind == "cp", f"{fixture['id']}: expected cp score")
            require(score >= expected["minimum_score_cp"], f"{fixture['id']}: score floor")
            check_count += 3

    alpha_beta_completed = run(
        binary,
        "uci\n"
        "setoption name Antichess_Search value alpha-beta-v1\n"
        "isready\n"
        + search_text,
    )
    require(
        alpha_beta_completed.returncode == 0,
        f"alpha-beta search boundary batch exited {alpha_beta_completed.returncode}",
    )
    alpha_beta_searches = parse_searches(alpha_beta_completed.stdout)
    require(
        alpha_beta_searches == searches,
        f"alpha-beta search boundary drift: {alpha_beta_searches!r} != {searches!r}",
    )
    check_count += 3 * len(alpha_beta_searches)

    automatic_cases = [
        fixture
        for fixture in [*core["position_fixtures"], *core["history_fixtures"]]
        if fixture["expected"]["automatic_draw"]
        and not fixture["expected"]["variant_end"]
    ]
    automatic_text = ""
    for fixture in automatic_cases:
        automatic_text += command(
            fixture.get("fen", fixture.get("initial_fen", "")), fixture.get("moves")
        ).replace("antichess-info\n", "go depth 2\n")
    completed = run(binary, automatic_text)
    require(completed.returncode == 0, f"automatic draw batch exited {completed.returncode}")
    automatic_searches = parse_searches(completed.stdout)
    require(len(automatic_searches) == len(automatic_cases), "automatic draw count mismatch")
    for fixture, (kind, score, bestmove) in zip(
        automatic_cases, automatic_searches, strict=True
    ):
        require(kind == "cp", f"{fixture['id']}: automatic draw score type")
        require(score == 0, f"{fixture['id']}: automatic draw score")
        require(
            bestmove in fixture["expected"]["legal_moves"],
            f"{fixture['id']}: automatic draw fallback {bestmove}",
        )
        check_count += 3

    precedence = next(
        fixture
        for fixture in core["position_fixtures"]
        if fixture["id"] == "variant_end_precedes_fifty_move_draw"
    )
    completed = run(
        binary,
        command(precedence["fen"]).replace("antichess-info\n", "go depth 2\n"),
    )
    require(completed.returncode == 0, "terminal precedence search failed")
    require("score mate 0" in completed.stdout, "variant end did not precede automatic draw")
    require("bestmove (none)" in completed.stdout, "terminal position returned a move")
    check_count += 2

    for fixture in search_boundaries["tt_isolation_cases"]:
        claim = run(
            binary,
            command(fixture["initial_fen"], fixture["claim_moves"]).replace(
                "antichess-info\n", f"go depth {fixture['depth']}\n"
            ),
        )
        raw = run(
            binary,
            command(fixture["initial_fen"]).replace(
                "antichess-info\n", f"go depth {fixture['depth']}\n"
            ),
        )
        claim_search = parse_searches(claim.stdout)[0]
        raw_search = parse_searches(raw.stdout)[0]
        require(claim_search[0] == "cp", f"{fixture['id']}: claim score type")
        require(
            claim_search[1] >= fixture["expected"]["claim_minimum_score_cp"],
            f"{fixture['id']}: claim floor",
        )
        require(raw_search[1] == claim_search[1], f"{fixture['id']}: raw score drift")
        check_count += 3

    print(
        "candidate UCI fixture verification passed: "
        f"{len(cases)} state cases, {len(search_boundaries['cases'])} search cases, "
        f"{check_count} checks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
