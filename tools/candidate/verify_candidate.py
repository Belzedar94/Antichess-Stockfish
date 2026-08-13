#!/usr/bin/env python3
"""Verify an exact Fairy-Stockfish candidate against LICHESS_ANTICHESS_V1."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import ModuleType
from typing import Any


PERFT_MOVE = re.compile(r"^([a-h][1-8][a-h][1-8][qrbnk]?):\s+[0-9]+$")
UCI_SCORE = re.compile(r"\bscore (cp|mate) (-?[0-9]+)\b")
UCI_DEPTH = re.compile(r"^info depth ([0-9]+)\b")
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


class UciSession:
    def __init__(self, engine: Path, timeout: float) -> None:
        self.timeout = timeout
        self.process = subprocess.Popen(
            [str(engine)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.reader = threading.Thread(target=self._read_output, daemon=True)
        self.reader.start()
        self.command("uci")
        self.wait_for(lambda line: line == "uciok", "uciok")
        self.command("setoption name UCI_Variant value antichess")
        self.command("setoption name Use NNUE value false")
        self.command("setoption name Threads value 1")
        self.command("setoption name Hash value 16")
        self.ready()

    def _read_output(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self.lines.put(line.rstrip("\r\n"))
        self.lines.put(None)

    def command(self, command: str) -> None:
        if self.process.poll() is not None:
            raise RuntimeError(f"engine exited before command {command!r}")
        assert self.process.stdin is not None
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()

    def wait_for(self, predicate: Any, label: str) -> list[str]:
        output: list[str] = []
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(f"timeout waiting for {label}:\n" + "\n".join(output[-100:]))
            try:
                line = self.lines.get(timeout=remaining)
            except queue.Empty as exc:
                raise RuntimeError(f"timeout waiting for {label}") from exc
            if line is None:
                raise RuntimeError(
                    f"engine exited {self.process.poll()} while waiting for {label}:\n"
                    + "\n".join(output[-100:])
                )
            output.append(line)
            if predicate(line):
                return output

    def ready(self) -> None:
        self.command("isready")
        self.wait_for(lambda line: line == "readyok", "readyok")

    def clear(self) -> None:
        self.command("setoption name Clear Hash")
        self.ready()

    def search(self, fen: str, moves: list[str], depth: int) -> dict[str, Any]:
        position = f"position fen {fen}"
        if moves:
            position += " moves " + " ".join(moves)
        self.command(position)
        self.command(f"go depth {depth}")
        output = self.wait_for(lambda line: line.startswith("bestmove "), "bestmove")
        info_lines = [line for line in output if UCI_DEPTH.match(line) and UCI_SCORE.search(line)]
        if not info_lines:
            raise RuntimeError("search returned no scored depth info:\n" + "\n".join(output[-100:]))
        info = info_lines[-1]
        depth_match = UCI_DEPTH.match(info)
        score_match = UCI_SCORE.search(info)
        assert depth_match is not None and score_match is not None
        bestmove = output[-1].split()[1]
        return {
            "depth": int(depth_match.group(1)),
            "score_type": score_match.group(1),
            "score": int(score_match.group(2)),
            "bestmove": bestmove,
            "output": output,
        }

    def close(self) -> None:
        if self.process.poll() is None:
            self.command("quit")
            try:
                self.process.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=5)

    def __enter__(self) -> "UciSession":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def score_rank(result: dict[str, Any]) -> int:
    if result["score_type"] == "mate":
        return VALUE_MATE if result["score"] > 0 else -VALUE_MATE
    return int(result["score"])


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
    automatic, automatic_value = sf.is_automatic_game_end("antichess", initial_fen, moves)
    optional, optional_value = sf.is_optional_game_end("antichess", initial_fen, moves)
    white_insufficient, black_insufficient = sf.has_insufficient_material(
        "antichess", initial_fen, moves
    )

    if expected["variant_end"]:
        check.equal(legal, [], f"{fixture_id} variant terminal move set")
        check.equal(automatic, False, f"{fixture_id} decisive result precedes automatic draw")
        result = sf.game_result("antichess", initial_fen, moves)
        check.equal(result, VALUE_MATE, f"{fixture_id} side-to-move variant win")
        check.equal(expected["winner"], fen_turn(final_fen), f"{fixture_id} winner perspective")
    elif expected["status"] == "draw":
        check.equal(immediate, False, f"{fixture_id} automatic draw leaked into move generation")
        check.equal(automatic, True, f"{fixture_id} automatic draw classification")
        if automatic:
            check.equal(automatic_value, 0, f"{fixture_id} automatic draw value")
        if fixture["family"] == "fifty_move":
            check.equal(optional, False, f"{fixture_id} 100-halfmove draw is not claimable")
    else:
        check.equal(immediate, False, f"{fixture_id} unexpected immediate end")
        check.equal(automatic, False, f"{fixture_id} unexpected automatic end")
        if expected["threefold"] and not expected["fivefold"]:
            check.equal(optional, True, f"{fixture_id} threefold claim availability")
            if optional:
                check.equal(optional_value, 0, f"{fixture_id} threefold claim value")
        elif not expected["end"]:
            check.equal(optional, False, f"{fixture_id} unexpected optional end")

    if fixture["family"] in {"insufficient_material", "one_sided_cannot_win"}:
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
    parser.add_argument(
        "--parser-fixtures",
        type=Path,
        default=Path("tests/antichess/fixtures/parser-boundaries-v1.json"),
    )
    parser.add_argument(
        "--repetition-fixtures",
        type=Path,
        default=Path("tests/antichess/fixtures/repetition-boundaries-v1.json"),
    )
    parser.add_argument(
        "--search-fixtures",
        type=Path,
        default=Path("tests/antichess/fixtures/search-boundaries-v1.json"),
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    engine = args.engine.resolve()
    pyffish_dir = args.pyffish_dir.resolve()
    fixture_path = args.fixtures.resolve()
    parser_fixture_path = args.parser_fixtures.resolve()
    repetition_fixture_path = args.repetition_fixtures.resolve()
    search_fixture_path = args.search_fixtures.resolve()
    for path in (
        engine,
        pyffish_dir,
        fixture_path,
        parser_fixture_path,
        repetition_fixture_path,
        search_fixture_path,
    ):
        if not path.exists():
            raise RuntimeError(f"required path does not exist: {path}")

    sf = load_pyffish(pyffish_dir)
    document = json.loads(fixture_path.read_text(encoding="utf-8"))
    parser_document = json.loads(parser_fixture_path.read_text(encoding="utf-8"))
    repetition_document = json.loads(repetition_fixture_path.read_text(encoding="utf-8"))
    search_document = json.loads(search_fixture_path.read_text(encoding="utf-8"))
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
    check.equal(sf.rules_profile("antichess"), "LICHESS_ANTICHESS_V1", "binding exact rules profile")
    for negative_profile in ("giveaway", "suicide", "losers"):
        check.equal(sf.rules_profile(negative_profile), "NONE", f"{negative_profile} negative rules profile")

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
    check.true(
        "info string rules profile LICHESS_ANTICHESS_V1" in classical,
        "UCI exact rules profile handshake",
    )
    for negative_profile in ("giveaway", "suicide", "losers"):
        negative_uci = run_uci(
            engine,
            ["uci", f"setoption name UCI_Variant value {negative_profile}"],
            args.timeout,
        )
        check.true(
            "info string rules profile NONE" in negative_uci,
            f"{negative_profile} negative UCI rules profile",
        )
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

    positions_by_id = {
        fixture["id"]: fixture for fixture in document["position_fixtures"]
    }
    fifty = positions_by_id["fifty_move_at_threshold"]
    fifty_search = run_uci(
        engine,
        [
            "uci",
            "setoption name UCI_Variant value antichess",
            "isready",
            f"position fen {fifty['fen']}",
            "go depth 2",
        ],
        args.timeout,
    )
    check.true("info depth 0 score cp 0" in fifty_search, "UCI 100-halfmove automatic draw score")
    fifty_bestmoves = [line.split()[1] for line in fifty_search.splitlines() if line.startswith("bestmove ")]
    check.true(
        len(fifty_bestmoves) == 1 and fifty_bestmoves[0] in fifty["expected"]["legal_moves"],
        "UCI automatic draw legal fallback move",
    )

    precedence = positions_by_id["variant_end_precedes_fifty_move_draw"]
    precedence_search = run_uci(
        engine,
        [
            "uci",
            "setoption name UCI_Variant value antichess",
            "isready",
            f"position fen {precedence['fen']}",
            "go depth 2",
        ],
        args.timeout,
    )
    check.true("info depth 0 score mate 0" in precedence_search, "UCI variant win precedes 100-halfmove draw")
    check.true(
        any(line in {"bestmove (none)", "bestmove 0000"} for line in precedence_search.splitlines()),
        "UCI decisive terminal has no move",
    )

    for fixture in document["history_fixtures"]:
        check.equal(
            uci_moves(engine, fixture["initial_fen"], fixture["moves"], args.timeout),
            fixture["expected"]["legal_moves"],
            f"{fixture['id']} UCI history legal moves",
        )
        verify_core_state(check, sf, fixture, fixture["initial_fen"], fixture["moves"])

    histories_by_id = {
        fixture["id"]: fixture for fixture in document["history_fixtures"]
    }
    fivefold = histories_by_id["fivefold_automatic_draw"]
    fivefold_position = f"position fen {fivefold['initial_fen']} moves " + " ".join(fivefold["moves"])
    fivefold_search = run_uci(
        engine,
        [
            "uci",
            "setoption name UCI_Variant value antichess",
            "isready",
            fivefold_position,
            "go depth 2",
        ],
        args.timeout,
    )
    check.true("info depth 0 score cp 0" in fivefold_search, "UCI fivefold automatic draw score")
    fivefold_bestmoves = [
        line.split()[1] for line in fivefold_search.splitlines() if line.startswith("bestmove ")
    ]
    check.true(
        len(fivefold_bestmoves) == 1
        and fivefold_bestmoves[0] in fivefold["expected"]["legal_moves"],
        "UCI fivefold automatic draw legal fallback move",
    )

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

    for fixture in parser_document["cases"]:
        accepted = sf.validate_fen(fixture["fen"], "antichess") == sf.FEN_OK
        check.equal(
            accepted,
            fixture["project_policy"] == "accept",
            f"{fixture['id']} parser geometry policy",
        )

    for fixture in repetition_document["position_cases"]:
        automatic, automatic_value = sf.is_automatic_game_end("antichess", fixture["fen"], [])
        claimable, claimable_value = sf.is_optional_game_end("antichess", fixture["fen"], [])
        check.equal(automatic, fixture["expected"]["automatic"], f"{fixture['id']} automatic classification")
        check.equal(claimable, fixture["expected"]["claimable"], f"{fixture['id']} claimable classification")

    for fixture in repetition_document["history_cases"]:
        automatic, automatic_value = sf.is_automatic_game_end(
            "antichess", fixture["initial_fen"], fixture["moves"]
        )
        claimable, claimable_value = sf.is_optional_game_end(
            "antichess", fixture["initial_fen"], fixture["moves"]
        )
        check.equal(automatic, fixture["expected"]["automatic"], f"{fixture['id']} automatic classification")
        check.equal(claimable, fixture["expected"]["claimable"], f"{fixture['id']} claimable classification")

    with UciSession(engine, args.timeout) as session:
        for fixture in search_document["cases"]:
            session.clear()
            result = session.search(fixture["initial_fen"], fixture["moves"], fixture["depth"])
            expected = fixture["expected"]
            check.true(result["depth"] >= fixture["depth"], f"{fixture['id']} completed search depth")
            check.true(result["bestmove"] in expected["bestmoves"], f"{fixture['id']} legal policy move")
            if "score_type" in expected:
                check.equal(result["score_type"], expected["score_type"], f"{fixture['id']} score type")
                check.equal(result["score"], expected["score"], f"{fixture['id']} score value")
            if "minimum_score_cp" in expected:
                check.true(
                    score_rank(result) >= expected["minimum_score_cp"],
                    f"{fixture['id']} virtual claim floor",
                )

        for fixture in search_document["tt_isolation_cases"]:
            session.clear()
            claim = session.search(
                fixture["initial_fen"],
                fixture["claim_moves"],
                fixture["depth"],
            )
            warmed_raw = session.search(fixture["initial_fen"], [], fixture["depth"])
            session.clear()
            fresh_raw = session.search(fixture["initial_fen"], [], fixture["depth"])
            check.true(
                score_rank(claim) >= fixture["expected"]["claim_minimum_score_cp"],
                f"{fixture['id']} claim score floor",
            )
            check.equal(
                (warmed_raw["score_type"], warmed_raw["score"]),
                (fresh_raw["score_type"], fresh_raw["score"]),
                f"{fixture['id']} no claim-history TT score leak",
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
