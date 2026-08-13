#!/usr/bin/env python3
"""Validate the frozen Antichess fixture contract without external packages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_POSITION_FAMILIES = {
    "identity",
    "mandatory_capture",
    "nonroyal_king",
    "castling",
    "en_passant",
    "promotion",
    "terminal",
    "terminal_precedence",
    "insufficient_material",
    "one_sided_cannot_win",
    "fifty_move",
    "orthodox_negative",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def opposite(color: str) -> str:
    return "black" if color == "white" else "white"


def fen_turn(fen: str) -> str:
    token = fen.split()[1]
    require(token in {"w", "b"}, f"invalid side-to-move token in {fen!r}")
    return "white" if token == "w" else "black"


def validate_expected(fixture_id: str, expected: dict[str, Any]) -> None:
    moves = expected["legal_moves"]
    require(moves == sorted(moves), f"{fixture_id}: legal moves are not sorted")
    require(len(moves) == len(set(moves)), f"{fixture_id}: duplicate legal move")

    fen_parts = expected["canonical_fen"].split()
    require(len(fen_parts) == 6, f"{fixture_id}: canonical FEN must have six fields")
    require(fen_parts[2] == "-", f"{fixture_id}: canonical Antichess FEN advertises castling rights")
    require(int(fen_parts[4]) == expected["halfmove_clock"], f"{fixture_id}: halfmove mismatch")
    canonical_ep = None if fen_parts[3] == "-" else fen_parts[3]
    require(canonical_ep == expected["effective_ep"], f"{fixture_id}: effective EP mismatch")

    if not expected["end"]:
        require(expected["status"] is None, f"{fixture_id}: ongoing position has a status")
        require(expected["winner"] is None, f"{fixture_id}: ongoing position has a winner")
    if expected["status"] == "draw":
        require(expected["end"], f"{fixture_id}: draw is not terminal")
        require(expected["winner"] is None, f"{fixture_id}: draw has a winner")
    if expected["variant_end"]:
        require(expected["end"], f"{fixture_id}: variant end is not terminal")
        require(expected["status"] == "variant_end", f"{fixture_id}: variant end lost precedence")
        require(expected["winner"] in {"white", "black"}, f"{fixture_id}: variant end has no winner")
    if expected["fivefold"]:
        require(expected["threefold"], f"{fixture_id}: fivefold without threefold")
        require(expected["automatic_draw"], f"{fixture_id}: fivefold is not automatic")
    if expected["automatic_draw"] and not expected["variant_end"]:
        require(expected["status"] == "draw", f"{fixture_id}: automatic draw has wrong status")

    castle_moves = {"e1g1", "e1c1", "e8g8", "e8c8"}
    require(not castle_moves.intersection(moves), f"{fixture_id}: castling move leaked into Antichess")


def validate_service_result(fixture: dict[str, Any], positions: dict[str, dict[str, Any]]) -> None:
    fixture_id = fixture["id"]
    position = positions[fixture["position_fixture"]]
    expected = position["expected"]
    turn = fen_turn(position["fen"])
    actor = fixture["actor"]
    event = fixture["event"]

    cannot_lose = (
        expected["opponent_insufficient"]
        if actor == turn
        else expected["player_insufficient"]
    )

    if event == "timeout":
        require(actor == turn, f"{fixture_id}: timeout actor is not side to move")
        result = "draw" if expected["opponent_insufficient"] else "win"
        winner = None if result == "draw" else opposite(actor)
        status = "outoftime"
    elif event == "resign":
        result = "draw" if cannot_lose else "win"
        winner = None if result == "draw" else opposite(actor)
        status = "insufficient_material_claim" if result == "draw" else "resign"
    elif event == "disconnect_claim":
        require(actor != turn, f"{fixture_id}: disconnect claimant must be the non-moving side")
        result = "draw" if expected["opponent_insufficient"] else "win"
        winner = None if result == "draw" else actor
        status = "timeout"
    elif event == "cannot_lose_claim":
        require(cannot_lose, f"{fixture_id}: actor does not satisfy cannotLose")
        result, winner, status = "draw", None, "insufficient_material_claim"
    else:
        raise ValueError(f"{fixture_id}: unsupported service event {event}")

    require(fixture["expected_result"] == result, f"{fixture_id}: service result mismatch")
    require(fixture["winner"] == winner, f"{fixture_id}: service winner mismatch")
    require(fixture["status"] == status, f"{fixture_id}: service status mismatch")


def validate(document: dict[str, Any]) -> tuple[int, int, int, int, int]:
    require(document["fixture_version"] == 1, "unsupported fixture version")
    require(document["profile"] == "LICHESS_ANTICHESS_V1", "wrong rules profile")
    require(document["authority_lock"] == "RULES/AUTHORITY.lock.json", "wrong authority lock")

    categories = (
        "position_fixtures",
        "history_fixtures",
        "move_rejection_fixtures",
        "parser_fixtures",
        "service_result_fixtures",
    )
    all_ids: list[str] = []
    for category in categories:
        require(isinstance(document.get(category), list) and document[category], f"empty {category}")
        all_ids.extend(item["id"] for item in document[category])
    require(len(all_ids) == len(set(all_ids)), "fixture IDs are not globally unique")

    positions = {fixture["id"]: fixture for fixture in document["position_fixtures"]}
    families = {fixture["family"] for fixture in positions.values()}
    missing = REQUIRED_POSITION_FAMILIES - families
    require(not missing, f"missing position fixture families: {sorted(missing)}")

    for fixture in document["position_fixtures"]:
        require(fixture["input_policy"] == "accept", f"{fixture['id']}: position fixture is not accepted")
        validate_expected(fixture["id"], fixture["expected"])
    for fixture in document["history_fixtures"]:
        require(fixture["moves"], f"{fixture['id']}: empty move sequence")
        validate_expected(fixture["id"], fixture["expected"])

    parser_rejections = [
        fixture for fixture in document["parser_fixtures"] if fixture["project_policy"] == "reject"
    ]
    require(parser_rejections, "no fail-closed parser fixture")
    require(
        any("z9" in fixture["fen"] for fixture in parser_rejections),
        "malformed en-passant fixture is missing",
    )

    for fixture in document["service_result_fixtures"]:
        require(fixture["position_fixture"] in positions, f"{fixture['id']}: missing position reference")
        validate_service_result(fixture, positions)

    return tuple(len(document[category]) for category in categories)  # type: ignore[return-value]


def validate_parser_boundaries(document: dict[str, Any]) -> int:
    require(document["fixture_version"] == 1, "unsupported parser fixture version")
    require(document["profile"] == "LICHESS_ANTICHESS_V1", "wrong parser rules profile")
    require(document["scope"] == "PROJECT_FEN_BOUNDARY", "wrong parser fixture scope")
    cases = document.get("cases")
    require(isinstance(cases, list) and cases, "empty parser boundary cases")
    ids = [case["id"] for case in cases]
    require(len(ids) == len(set(ids)), "duplicate parser boundary fixture ID")
    policies = {case["project_policy"] for case in cases}
    require(policies == {"accept", "reject"}, "parser boundaries need accept and reject cases")
    for case in cases:
        require(len(case["fen"].split()) == 6, f"{case['id']}: parser FEN must have six fields")
    return len(cases)


def validate_repetition_boundaries(document: dict[str, Any]) -> tuple[int, int]:
    require(document["fixture_version"] == 1, "unsupported repetition fixture version")
    require(document["profile"] == "LICHESS_ANTICHESS_V1", "wrong repetition rules profile")
    require(document["scope"] == "REPETITION_CLASSIFICATION", "wrong repetition fixture scope")
    positions = document.get("position_cases")
    histories = document.get("history_cases")
    require(isinstance(positions, list) and positions, "empty repetition position cases")
    require(isinstance(histories, list) and histories, "empty repetition history cases")
    ids = [case["id"] for case in [*positions, *histories]]
    require(len(ids) == len(set(ids)), "duplicate repetition boundary fixture ID")
    for case in positions:
        require(not case["expected"]["claimable"], f"{case['id']}: FEN invented a repetition claim")
        require(not case["expected"]["automatic"], f"{case['id']}: FEN invented an automatic repetition")
    for case in histories:
        require(case["moves"], f"{case['id']}: empty repetition history")
        require(case["expected"]["claimable"], f"{case['id']}: history is not claimable")
        require(not case["expected"]["automatic"], f"{case['id']}: fourfold became automatic")
    return len(positions), len(histories)


def validate_search_boundaries(document: dict[str, Any]) -> tuple[int, int]:
    require(document["fixture_version"] == 1, "unsupported search fixture version")
    require(document["profile"] == "LICHESS_ANTICHESS_V1", "wrong search rules profile")
    require(
        document["scope"] == "SEARCH_TERMINAL_AND_CLAIM_POLICY",
        "wrong search fixture scope",
    )
    cases = document.get("cases")
    isolation_cases = document.get("tt_isolation_cases")
    require(isinstance(cases, list) and cases, "empty search boundary cases")
    require(isinstance(isolation_cases, list) and isolation_cases, "empty TT isolation cases")
    ids = [case["id"] for case in [*cases, *isolation_cases]]
    require(len(ids) == len(set(ids)), "duplicate search boundary fixture ID")
    for case in cases:
        require(case["depth"] > 0, f"{case['id']}: non-positive search depth")
        require(case["expected"]["bestmoves"], f"{case['id']}: no legal bestmove contract")
    for case in isolation_cases:
        require(case["claim_moves"], f"{case['id']}: no claim history")
        require(case["depth"] > 0, f"{case['id']}: non-positive isolation depth")
        require(
            case["expected"]["warmed_raw_score_equals_fresh_raw_score"],
            f"{case['id']}: TT isolation equality is not required",
        )
    return len(cases), len(isolation_cases)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "fixture_file",
        nargs="?",
        default="tests/antichess/fixtures/core-v1.json",
        type=Path,
    )
    parser.add_argument(
        "--parser-fixtures",
        default="tests/antichess/fixtures/parser-boundaries-v1.json",
        type=Path,
    )
    parser.add_argument(
        "--repetition-fixtures",
        default="tests/antichess/fixtures/repetition-boundaries-v1.json",
        type=Path,
    )
    parser.add_argument(
        "--search-fixtures",
        default="tests/antichess/fixtures/search-boundaries-v1.json",
        type=Path,
    )
    args = parser.parse_args()
    document = json.loads(args.fixture_file.read_text(encoding="utf-8"))
    counts = validate(document)
    parser_document = json.loads(args.parser_fixtures.read_text(encoding="utf-8"))
    parser_count = validate_parser_boundaries(parser_document)
    repetition_document = json.loads(args.repetition_fixtures.read_text(encoding="utf-8"))
    repetition_counts = validate_repetition_boundaries(repetition_document)
    search_document = json.loads(args.search_fixtures.read_text(encoding="utf-8"))
    search_counts = validate_search_boundaries(search_document)
    print(
        "fixture contract verified: "
        f"{counts[0]} positions, {counts[1]} histories, {counts[2]} rejected moves, "
        f"{counts[3]} core parser cases, {parser_count} boundary parser cases, "
        f"{counts[4]} service results, {repetition_counts[0]} repetition position cases, "
        f"{repetition_counts[1]} repetition history cases, {search_counts[0]} search cases, "
        f"{search_counts[1]} TT isolation cases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
