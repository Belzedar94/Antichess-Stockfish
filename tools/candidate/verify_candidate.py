#!/usr/bin/env python3
"""Verify an exact Fairy-Stockfish candidate against LICHESS_ANTICHESS_V1."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


PERFT_MOVE = re.compile(r"^([a-h][1-8][a-h][1-8][qrbnk]?):\s+[0-9]+$")
VALUE_MATE = 32000


def load_pyffish(directory: Path) -> ModuleType:
    candidates = list(directory.glob("pyffish*.pyd")) + list(directory.glob("pyffish*.so"))
    if len(candidates) != 1:
        raise RuntimeError(f"expected exactly one pyffish module in {directory}, found {len(candidates)}")
    sys.path.insert(0, str(directory))
    module = importlib.import_module("pyffish")
    loaded = Path(module.__file__).resolve()
    if loaded != candidates[0].resolve():
        raise RuntimeError(f"loaded unexpected pyffish module: {loaded}")
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fen_turn(fen: str) -> str:
    return "white" if fen.split()[1] == "w" else "black"


def run_uci(engine: Path, commands: list[str], timeout: float) -> str:
    completed = subprocess.run(
        [str(engine)],
        input="\n".join(commands + ["quit", ""]),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"engine exited {completed.returncode}:\n{completed.stdout[-4000:]}")
    return completed.stdout


def uci_moves(engine: Path, fen: str, moves: list[str], timeout: float) -> list[str]:
    position = f"position fen {fen}"
    if moves:
        position += " moves " + " ".join(moves)
    output = run_uci(
        engine,
        [
            "uci",
            "setoption name UCI_Variant value antichess",
            "isready",
            position,
            "go perft 1",
        ],
        timeout,
    )
    if "uciok" not in output or "readyok" not in output:
        raise RuntimeError(f"incomplete UCI handshake:\n{output[-4000:]}")
    return sorted(
        match.group(1)
        for line in output.splitlines()
        if (match := PERFT_MOVE.match(line.strip()))
    )


class Verification:
    def __init__(self) -> None:
        self.checks = 0
        self.failures: list[str] = []

    def equal(self, actual: Any, expected: Any, label: str) -> None:
        self.checks += 1
        if actual != expected:
            self.failures.append(f"{label}: expected {expected!r}, got {actual!r}")

    def true(self, condition: bool, label: str) -> None:
        self.equal(bool(condition), True, label)


def verify_core_state(
    check: Verification,
    sf: ModuleType,
    fixture: dict[str, Any],
    initial_fen: str,
    moves: list[str],
) -> None:
    fixture_id = fixture["id"]
    expected = fixture["expected"]
    legal = sorted(sf.legal_moves("antichess", initial_fen, moves))
    check.equal(legal, expected["legal_moves"], f"{fixture_id} core legal moves")
    check.equal(
        sf.get_fen("antichess", initial_fen, moves),
        expected["canonical_fen"],
        f"{fixture_id} canonical FEN",
    )

    final_fen = expected["canonical_fen"]
    immediate, immediate_value = sf.is_immediate_game_end("antichess", initial_fen, moves)
    optional, optional_value = sf.is_optional_game_end("antichess", initial_fen, moves)
    white_insufficient, black_insufficient = sf.has_insufficient_material(
        "antichess", initial_fen, moves
    )

    if expected["variant_end"]:
        check.equal(legal, [], f"{fixture_id} variant terminal move set")
        result = sf.game_result("antichess", initial_fen, moves)
        check.equal(result, VALUE_MATE, f"{fixture_id} side-to-move variant win")
        check.equal(expected["winner"], fen_turn(final_fen), f"{fixture_id} winner perspective")
    elif expected["status"] == "draw":
        if fixture["family"] == "insufficient_material":
            check.equal(
                (white_insufficient, black_insufficient),
                (True, True),
                f"{fixture_id} automatic insufficient-material draw",
            )
        else:
            check.equal(immediate, True, f"{fixture_id} automatic draw classification")
            if immediate:
                check.equal(immediate_value, 0, f"{fixture_id} automatic draw value")
    else:
        check.equal(immediate, False, f"{fixture_id} unexpected immediate end")
        if expected["threefold"] and not expected["fivefold"]:
            check.equal(optional, True, f"{fixture_id} threefold claim availability")
            if optional:
                check.equal(optional_value, 0, f"{fixture_id} threefold claim value")
        elif not expected["end"]:
            check.equal(optional, False, f"{fixture_id} unexpected optional end")

    if fixture["family"] == "one_sided_cannot_win":
        turn = fen_turn(final_fen)
        by_color = {"white": white_insufficient, "black": black_insufficient}
        other = "black" if turn == "white" else "white"
        check.equal(
            by_color[turn],
            expected["player_insufficient"],
            f"{fixture_id} player cannot-win predicate",
        )
        check.equal(
            by_color[other],
            expected["opponent_insufficient"],
            f"{fixture_id} opponent cannot-win predicate",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--pyffish-dir", required=True, type=Path)
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=Path("tests/antichess/fixtures/core-v1.json"),
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    engine = args.engine.resolve()
    pyffish_dir = args.pyffish_dir.resolve()
    fixture_path = args.fixtures.resolve()
    for path in (engine, pyffish_dir, fixture_path):
        if not path.exists():
            raise RuntimeError(f"required path does not exist: {path}")

    sf = load_pyffish(pyffish_dir)
    document = json.loads(fixture_path.read_text(encoding="utf-8"))
    check = Verification()

    uci = run_uci(engine, ["uci"], args.timeout)
    check.true("uciok" in uci, "UCI handshake")
    check.true(
        any(line.startswith("option name UCI_Variant ") and " var antichess" in line for line in uci.splitlines()),
        "UCI antichess option mapping",
    )
    check.true(
        "id name Fairy-Stockfish" in uci and "Fairy-Stockfish" in sf.info(),
        "binary and binding identity surface",
    )

    classical = run_uci(
        engine,
        [
            "uci",
            "setoption name UCI_Variant value antichess",
            "isready",
            "position startpos",
            "go depth 2",
        ],
        args.timeout,
    )
    check.true("info string classical evaluation enabled" in classical, "network-independent classical search")
    check.true(any(line.startswith("bestmove ") for line in classical.splitlines()), "classical bestmove")

    for fixture in document["position_fixtures"]:
        fixture_id = fixture["id"]
        fen = fixture["fen"]
        check.equal(sf.validate_fen(fen, "antichess"), sf.FEN_OK, f"{fixture_id} FEN acceptance")
        check.equal(
            uci_moves(engine, fen, [], args.timeout),
            fixture["expected"]["legal_moves"],
            f"{fixture_id} UCI legal moves",
        )
        verify_core_state(check, sf, fixture, fen, [])

    for fixture in document["history_fixtures"]:
        check.equal(
            uci_moves(engine, fixture["initial_fen"], fixture["moves"], args.timeout),
            fixture["expected"]["legal_moves"],
            f"{fixture['id']} UCI history legal moves",
        )
        verify_core_state(check, sf, fixture, fixture["initial_fen"], fixture["moves"])

    positions_by_fen = {
        fixture["fen"]: fixture for fixture in document["position_fixtures"]
    }
    for fixture in document["move_rejection_fixtures"]:
        source = positions_by_fen[fixture["fen"]]
        check.true(
            fixture["move"] not in source["expected"]["legal_moves"],
            f"{fixture['id']} frozen rejection",
        )
        check.true(
            fixture["move"] not in sf.legal_moves("antichess", fixture["fen"], []),
            f"{fixture['id']} core rejection",
        )

    for fixture in document["parser_fixtures"]:
        accepted = sf.validate_fen(fixture["fen"], "antichess") == sf.FEN_OK
        check.equal(
            accepted,
            fixture["project_policy"] == "accept",
            f"{fixture['id']} fail-closed parser policy",
        )

    module_path = Path(sf.__file__).resolve()
    print(f"engine_sha256={sha256(engine)}")
    print(f"pyffish_sha256={sha256(module_path)}")
    print(f"engine={engine}")
    print(f"pyffish={module_path}")
    print(f"checks={check.checks}")
    print(f"failures={len(check.failures)}")
    for failure in check.failures:
        print(f"FAIL: {failure}")
    return 1 if check.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
