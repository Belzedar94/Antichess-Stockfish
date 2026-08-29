#!/usr/bin/env python3
"""Verify AC_REFEREE_V1 against the frozen Lichess Antichess contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PREFIX = "referee-info "
EXPECTED_CUTECHESS_COMMIT = "5e84232be4546aaedc9d87a96c91867a1da06ada"
EXPECTED_CUTECHESS_TREE = "d0912f7c5355837bec16a9c57dc5da29ce42765d"
EXPECTED_PATCH_SHA256 = "b8d20a4aa6c4a4a287772cec08b7e952feca88be9120ce11c45a7a3ccfa2a972"
EXPECTED_PATCHED_TREE = "639664d19717604326fa5fef21356556db86e27b"
EXPECTED_PATCHED_BLOBS = {
    "CMakeLists.txt": "e45a44698795022c38949ebe3d53ff73f81d8532",
    "projects/cli/src/main.cpp": "51cc766401e426c96dca6823300af6f878ced01e",
    "projects/lib/src/board/antiboard.cpp": "25082a3c71f362492027b462489edc3e8cde4f44",
    "projects/lib/src/board/antiboard.h": "fbd75bbbcd27bcbd043b69a249e30e56ea71f9e3",
    "projects/lib/src/chessgame.cpp": "f3ffa16fd746ce8be079654389bd5456d1e8d8bf",
    "projects/lib/src/pgngame.cpp": "f43f1160a4a3336475fa79ea18ce22405d10540a",
    "projects/lib/tests/antichessprofile/antichess_profile_probe.cpp": (
        "095d1177953da93f629a135b2a512e0bc06305b5"
    ),
}
MUST_CAPTURE_CASES = {
    "mandatory_capture_single",
    "mandatory_capture_free_choice",
    "adjacent_king_capture",
    "en_passant_only_capture",
    "en_passant_among_captures",
    "capture_promotion_all_roles",
    "effective_ep_breaks_blocked_bishops_pawns_draw",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), *arguments],
        text=True,
        encoding="utf-8",
        errors="strict",
    ).strip()


def derive_patched_tree(root: Path, patch: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="ac-referee-index-") as temporary:
        environment = os.environ.copy()
        environment["GIT_INDEX_FILE"] = str(Path(temporary) / "index")
        subprocess.run(
            ["git", "-C", str(root), "read-tree", "HEAD"],
            env=environment,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        subprocess.run(
            ["git", "-C", str(root), "apply", "--cached", "--whitespace=error-all", str(patch)],
            env=environment,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return subprocess.check_output(
            ["git", "-C", str(root), "write-tree"],
            env=environment,
            text=True,
            encoding="ascii",
        ).strip()


def run(
    probe: Path,
    fen: str,
    moves: list[str] | None,
    environment: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(probe), fen, *(moves or [])],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=30,
        check=False,
    )


def parse(output: str) -> dict[str, str]:
    lines = [line for line in output.splitlines() if line.startswith(PREFIX)]
    require(len(lines) == 1, f"expected one referee diagnostic, got {len(lines)}:\n{output}")
    fields: dict[str, str] = {}
    for item in lines[0][len(PREFIX) :].split("|"):
        key, separator, value = item.partition("=")
        require(bool(separator), f"malformed referee field: {item!r}")
        fields[key] = value
    return fields


def bool_text(value: bool) -> str:
    return "1" if value else "0"


def none_text(value: Any) -> str:
    return "none" if value is None else str(value)


def verify_state(fixture_id: str, actual: dict[str, str], expected: dict[str, Any]) -> int:
    checks = {
        "profile": "LICHESS_ANTICHESS_V1",
        "fen": expected["canonical_fen"],
        "legal": ",".join(expected["legal_moves"]),
        "end": bool_text(expected["end"]),
        "variant_end": bool_text(expected["variant_end"]),
        "automatic_draw": bool_text(expected["automatic_draw"]),
        "threefold": bool_text(expected["threefold"]),
        "fivefold": bool_text(expected["fivefold"]),
        "status": none_text(expected["status"]),
        "winner": none_text(expected["winner"]),
        "check": bool_text(expected["check"]),
        "must_capture": bool_text(fixture_id in MUST_CAPTURE_CASES),
        "player_insufficient": bool_text(expected["player_insufficient"]),
        "opponent_insufficient": bool_text(expected["opponent_insufficient"]),
        "halfmove_clock": str(expected["halfmove_clock"]),
        "effective_ep": none_text(expected["effective_ep"]),
    }
    for key, value in checks.items():
        require(actual.get(key) == value, f"{fixture_id}: {key}: {actual.get(key)!r} != {value!r}")

    expected_board_result = (
        "win" if expected["variant_end"] else "draw" if expected["automatic_draw"] else "none"
    )
    require(
        actual["board_result"] == expected_board_result,
        f"{fixture_id}: board result {actual['board_result']!r} != {expected_board_result!r}",
    )
    expected_winner = expected["winner"] if expected["variant_end"] else None
    require(
        actual["board_result_winner"] == none_text(expected_winner),
        f"{fixture_id}: board winner drift",
    )

    if not expected["automatic_draw"]:
        turn = actual["side_to_move"]
        other = "black" if turn == "white" else "white"
        require(
            actual[f"{turn}_win_possible"]
            == bool_text(not expected["player_insufficient"]),
            f"{fixture_id}: side-to-move winPossible drift",
        )
        require(
            actual[f"{other}_win_possible"]
            == bool_text(not expected["opponent_insufficient"]),
            f"{fixture_id}: opponent winPossible drift",
        )
        return len(checks) + 4
    return len(checks) + 2


def verify_service_cases(
    document: dict[str, Any],
    position_diagnostics: dict[str, dict[str, str]],
) -> int:
    checks = 0
    for fixture in document["service_result_fixtures"]:
        actual = position_diagnostics[fixture["position_fixture"]]
        actor = fixture["actor"]
        turn = actual["side_to_move"]
        other = "black" if actor == "white" else "white"
        event = fixture["event"]

        if event in {"timeout", "resign"}:
            require(actor == turn or event == "resign", f"{fixture['id']}: timeout actor drift")
            can_win = actual[f"{other}_win_possible"] == "1"
            result = "win" if can_win else "draw"
            winner = other if can_win else None
        elif event == "disconnect_claim":
            require(actor != turn, f"{fixture['id']}: claimant is side to move")
            can_win = actual[f"{actor}_win_possible"] == "1"
            result = "win" if can_win else "draw"
            winner = actor if can_win else None
        elif event == "cannot_lose_claim":
            insufficient_field = (
                "opponent_insufficient" if actor == turn else "player_insufficient"
            )
            require(actual[insufficient_field] == "1", f"{fixture['id']}: invalid cannot-lose claim")
            result, winner = "draw", None
        else:
            raise AssertionError(f"{fixture['id']}: unsupported service event {event}")

        require(result == fixture["expected_result"], f"{fixture['id']}: service result drift")
        require(winner == fixture["winner"], f"{fixture['id']}: service winner drift")
        checks += 3
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", required=True, type=Path)
    parser.add_argument("--cutechess-root", required=True, type=Path)
    parser.add_argument("--qt-bin", required=True, type=Path)
    args = parser.parse_args()

    probe = args.probe.resolve()
    cutechess_root = args.cutechess_root.resolve()
    qt_bin = args.qt_bin.resolve()
    patch = ROOT / "tools" / "referee" / "patches" / "cutechess-5e84232-lichess-antichess-v1.patch"
    require(probe.is_file(), f"referee probe not found: {probe}")
    require(patch.is_file(), f"referee patch not found: {patch}")
    require((qt_bin / "Qt6Core.dll").is_file(), f"Qt6 runtime not found: {qt_bin}")
    require(git(cutechess_root, "rev-parse", "HEAD") == EXPECTED_CUTECHESS_COMMIT, "wrong CuteChess base commit")
    require(
        git(cutechess_root, "rev-parse", "HEAD^{tree}") == EXPECTED_CUTECHESS_TREE,
        "wrong CuteChess base tree",
    )
    require(hashlib.sha256(patch.read_bytes()).hexdigest() == EXPECTED_PATCH_SHA256, "referee patch hash drift")
    require(
        derive_patched_tree(cutechess_root, patch) == EXPECTED_PATCHED_TREE,
        "referee patch tree drift",
    )
    for relative_path, expected_blob in EXPECTED_PATCHED_BLOBS.items():
        require((cutechess_root / relative_path).is_file(), f"patched source missing: {relative_path}")
        require(
            git(cutechess_root, "hash-object", f"--path={relative_path}", "--", relative_path)
            == expected_blob,
            f"patched source drift: {relative_path}",
        )

    environment = os.environ.copy()
    environment["PATH"] = str(qt_bin) + os.pathsep + environment.get("PATH", "")

    core = load("tests/antichess/fixtures/core-v1.json")
    material = load("tests/antichess/fixtures/material-boundaries-v1.json")
    repetition = load("tests/antichess/fixtures/repetition-boundaries-v1.json")
    parser_boundaries = load("tests/antichess/fixtures/parser-boundaries-v1.json")
    notation = load("tests/antichess/fixtures/notation-v1.json")

    cases: list[tuple[str, str, list[str] | None, dict[str, Any]]] = []
    for fixture in core["position_fixtures"]:
        cases.append((fixture["id"], fixture["fen"], None, fixture["expected"]))
    for fixture in core["history_fixtures"]:
        cases.append((fixture["id"], fixture["initial_fen"], fixture["moves"], fixture["expected"]))
    for fixture in material["history_cases"]:
        cases.append((fixture["id"], fixture["initial_fen"], fixture["moves"], fixture["expected"]))

    check_count = 0
    position_diagnostics: dict[str, dict[str, str]] = {}
    for fixture_id, fen, moves, expected in cases:
        completed = run(probe, fen, moves, environment)
        require(completed.returncode == 0, f"{fixture_id}: referee exited {completed.returncode}:\n{completed.stdout}")
        actual = parse(completed.stdout)
        check_count += verify_state(fixture_id, actual, expected)
        if moves is None:
            position_diagnostics[fixture_id] = actual

    for fixture in repetition["position_cases"]:
        completed = run(probe, fixture["fen"], None, environment)
        require(completed.returncode == 0, f"{fixture['id']}: referee rejected repetition FEN")
        actual = parse(completed.stdout)
        require(actual["threefold"] == "0", f"{fixture['id']}: FEN invented a claim")
        require(actual["fivefold"] == "0", f"{fixture['id']}: FEN invented fivefold")
        require(
            actual["automatic_draw"] == bool_text(fixture["expected"]["automatic"]),
            f"{fixture['id']}: repetition automatic drift",
        )
        check_count += 3
    for fixture in repetition["history_cases"]:
        completed = run(probe, fixture["initial_fen"], fixture["moves"], environment)
        require(completed.returncode == 0, f"{fixture['id']}: referee rejected repetition history")
        actual = parse(completed.stdout)
        require(
            actual["threefold"] == bool_text(fixture["expected"]["claimable"]),
            f"{fixture['id']}: claimability drift",
        )
        require(actual["fivefold"] == "0", f"{fixture['id']}: fourfold became fivefold")
        require(actual["board_result"] == "none", f"{fixture['id']}: claim became automatic")
        check_count += 3

    accepted = [
        fixture
        for fixture in [*core["parser_fixtures"], *parser_boundaries["cases"]]
        if fixture["project_policy"] == "accept"
    ]
    rejected = [
        fixture
        for fixture in [*core["parser_fixtures"], *parser_boundaries["cases"]]
        if fixture["project_policy"] == "reject"
    ]
    for fixture in accepted:
        completed = run(probe, fixture["fen"], None, environment)
        require(completed.returncode == 0, f"{fixture['id']}: accepted FEN was rejected")
        check_count += 1
    for fixture in rejected:
        completed = run(probe, fixture["fen"], None, environment)
        require(completed.returncode == 4, f"{fixture['id']}: malformed FEN was accepted")
        require("referee-error invalid-fen" in completed.stdout, f"{fixture['id']}: wrong rejection")
        check_count += 2

    for fixture in core["move_rejection_fixtures"]:
        completed = run(probe, fixture["fen"], [fixture["move"]], environment)
        require(completed.returncode == 5, f"{fixture['id']}: illegal move was accepted")
        require(
            f"referee-error illegal-move {fixture['move']}" in completed.stdout,
            f"{fixture['id']}: wrong illegal-move rejection",
        )
        check_count += 2

    for fixture in notation["cases"]:
        completed = run(probe, fixture["fen"], None, environment)
        require(completed.returncode == 0, f"{fixture['id']}: notation FEN was rejected")
        actual = parse(completed.stdout)
        require(actual["fen"] == fixture["canonical_fen"], f"{fixture['id']}: canonical FEN drift")
        require(actual["notation"] == ",".join(fixture["notation"]), f"{fixture['id']}: SAN drift")
        require(
            actual["must_capture"] == bool_text(fixture["must_capture"]),
            f"{fixture['id']}: mandatory-capture notation context drift",
        )
        check_count += 3

    check_count += verify_service_cases(core, position_diagnostics)

    probe_sha256 = hashlib.sha256(probe.read_bytes()).hexdigest()
    print(
        "AC_REFEREE_V1 verification passed: "
        f"{len(cases)} state/history cases, {len(accepted)} accepted and {len(rejected)} rejected FENs, "
        f"{len(core['move_rejection_fixtures'])} rejected moves, "
        f"{len(notation['cases'])} notation positions, "
        f"{len(core['service_result_fixtures'])} service outcomes, {check_count} checks; "
        f"probe sha256 {probe_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
