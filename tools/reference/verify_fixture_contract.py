#!/usr/bin/env python3
"""Validate the frozen Antichess fixture contract without external packages."""

from __future__ import annotations

import argparse
import hashlib
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


def validate_material_boundaries(document: dict[str, Any]) -> int:
    require(document["fixture_version"] == 1, "unsupported material fixture version")
    require(document["profile"] == "LICHESS_ANTICHESS_V1", "wrong material rules profile")
    require(document["scope"] == "MATERIAL_BOUNDARIES", "wrong material fixture scope")
    authority = document.get("authority", {})
    require(
        authority.get("repository") == "https://github.com/lichess-org/scalachess",
        "wrong material authority repository",
    )
    require(
        authority.get("commit") == "cbffc9d7e2c6f8ba33381c5403e1b4f992199626",
        "wrong material authority commit",
    )
    histories = document.get("history_cases")
    require(isinstance(histories, list) and histories, "empty material history cases")
    ids = [case["id"] for case in histories]
    require(len(ids) == len(set(ids)), "duplicate material boundary fixture ID")
    automatic_results: set[bool] = set()
    for case in histories:
        require(case["family"] == "insufficient_material", f"{case['id']}: wrong material family")
        require(case["moves"], f"{case['id']}: empty material transition")
        validate_expected(case["id"], case["expected"])
        automatic_results.add(case["expected"]["automatic_draw"])
    require(automatic_results == {False, True}, "material boundaries need positive and negative cases")
    require(
        "blocked_pawns_opposite_bishops_draw" in ids,
        "blocked-pawn positive material case is missing",
    )
    require(
        "pawn_blocked_by_bishop_not_draw" in ids,
        "non-pawn blocker negative material case is missing",
    )
    return len(histories)


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


def validate_claim_protocol_boundaries(document: dict[str, Any]) -> int:
    require(document["fixture_version"] == 1, "unsupported claim protocol fixture version")
    require(document["profile"] == "LICHESS_ANTICHESS_V1", "wrong claim protocol profile")
    require(document["scope"] == "CLAIM_PROTOCOL_POLICY", "wrong claim protocol scope")
    cases = document.get("cases")
    require(isinstance(cases, list) and cases, "empty claim protocol cases")
    ids = [case["id"] for case in cases]
    require(len(ids) == len(set(ids)), "duplicate claim protocol fixture ID")
    actions = {case["expected"]["action"] for case in cases}
    require(actions == {"claim", "move"}, "claim protocol fixtures need claim and move actions")
    for case in cases:
        require(case["moves"], f"{case['id']}: no repetition history")
        require(case["depth"] > 0, f"{case['id']}: non-positive protocol depth")
        require(case["expected"]["line"], f"{case['id']}: empty protocol line")
    return len(cases)


def validate_legacy_evaluator(document: dict[str, Any]) -> int:
    require(document["fixture_version"] == 1, "unsupported legacy evaluator fixture version")
    require(document["profile"] == "LICHESS_ANTICHESS_V1", "wrong legacy evaluator profile")
    network = document.get("network", {})
    require(
        network.get("sha256")
        == "dd3cbe53cd4e1ca5b7f41cf090873ebe732d84d27f9ed7b14c62ff7a633712cc",
        "wrong legacy evaluator network identity",
    )
    require(network.get("bytes") == 953248, "wrong legacy evaluator network size")
    require(
        network.get("redistribution_license") == "UNRESOLVED",
        "legacy evaluator license boundary changed without a contract update",
    )
    executable = document.get("executable_reference", {})
    require(
        executable.get("commit") == "c19b5f6c66894fdb0e88d0dd100e3885f744760a",
        "wrong legacy executable reference commit",
    )
    cases = document.get("cases")
    require(isinstance(cases, list) and cases, "empty legacy evaluator cases")
    ids = [case["id"] for case in cases]
    require(len(ids) == len(set(ids)), "duplicate legacy evaluator fixture ID")
    buckets: set[int] = set()
    turns: set[str] = set()
    for case in cases:
        require(len(case["fen"].split()) == 6, f"{case['id']}: evaluator FEN must have six fields")
        require(case["piece_count"] > 0, f"{case['id']}: empty-board evaluator fixture")
        expected_bucket = min((case["piece_count"] - 1) * 8 // 32, 7)
        require(case["bucket"] == expected_bucket, f"{case['id']}: legacy bucket mismatch")
        require(isinstance(case["expected_raw"], int), f"{case['id']}: non-integer legacy value")
        buckets.add(case["bucket"])
        turns.add(case["fen"].split()[1])
    require(buckets == set(range(8)), f"legacy evaluator buckets incomplete: {sorted(buckets)}")
    require(turns == {"w", "b"}, "legacy evaluator lacks both side-to-move perspectives")
    return len(cases)


def validate_notation(document: dict[str, Any]) -> int:
    require(document["schema"] == "antichess-notation-fixtures-v1", "wrong notation schema")
    require(document["profile"] == "LICHESS_ANTICHESS_V1", "wrong notation profile")
    require(
        document["authority"]["commit"] == "cbffc9d7e2c6f8ba33381c5403e1b4f992199626",
        "wrong notation authority commit",
    )
    cases = document.get("cases")
    require(isinstance(cases, list) and cases, "empty notation cases")
    ids = [case["id"] for case in cases]
    require(len(ids) == len(set(ids)), "duplicate notation fixture ID")
    required_ids = {
        "terminal_mandatory_pawn_capture_san",
        "terminal_nonroyal_king_capture_san",
        "terminal_en_passant_san",
        "quiet_promotion_all_antichess_roles_san",
        "capture_promotion_all_antichess_roles_san",
        "attacked_nonroyal_king_has_no_check_suffix",
        "orthodox_checkmate_shape_has_no_check_suffix",
    }
    require(set(ids) == required_ids, "notation fixture coverage drift")
    for case in cases:
        fen_parts = case["canonical_fen"].split()
        require(len(fen_parts) == 6, f"{case['id']}: canonical FEN must have six fields")
        require(fen_parts[2] == "-", f"{case['id']}: canonical FEN retained castling rights")
        notation = case["notation"]
        require(notation == sorted(notation), f"{case['id']}: notation is not UCI-sorted")
        require(len(notation) == len(set(notation)), f"{case['id']}: duplicate notation entry")
        for entry in notation:
            uci, separator, san = entry.partition("=")
            require(bool(separator) and len(uci) in {4, 5}, f"{case['id']}: malformed UCI/SAN pair")
            require(san and "+" not in san, f"{case['id']}: check suffix leaked into Antichess SAN")
    require(
        any("a7a8k=a8=K" in entry for case in cases for entry in case["notation"]),
        "notation fixtures lack promotion to king",
    )
    require(
        sum(entry.endswith("#") for case in cases for entry in case["notation"]) == 3,
        "terminal SAN marker coverage drift",
    )
    return len(cases)


def validate_bench(document: dict[str, Any]) -> int:
    require(document["schema"] == "ANTICHESS_BENCH_V1", "wrong bench schema")
    require(document["profile"] == "LICHESS_ANTICHESS_V1", "wrong bench profile")
    require(document["command"] == "bench 1 1 2 default depth", "wrong bench command")
    records = document.get("records")
    require(isinstance(records, list) and records, "empty bench records")
    require(len(records) == document["position_count"] == 13, "bench position count drift")
    require([record["index"] for record in records] == list(range(1, 14)), "bench index drift")
    require(
        sum(record["nodes"] for record in records) == document["total_nodes"] == 737,
        "bench node total drift",
    )
    require(
        all(record["score_type"] in {"cp", "mate"} for record in records),
        "invalid bench score type",
    )
    require(
        all(record["pv"] and record["bestmove"] for record in records),
        "empty bench move record",
    )
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")) + "\n"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    require(digest == document["canonical_sha256"], "bench canonical digest drift")
    return len(records)


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
    parser.add_argument(
        "--material-fixtures",
        default="tests/antichess/fixtures/material-boundaries-v1.json",
        type=Path,
    )
    parser.add_argument(
        "--claim-protocol-fixtures",
        default="tests/antichess/fixtures/protocol-claim-boundaries-v1.json",
        type=Path,
    )
    parser.add_argument(
        "--legacy-evaluator-fixtures",
        default="tests/antichess/fixtures/legacy-evaluator-v1.json",
        type=Path,
    )
    parser.add_argument(
        "--notation-fixtures",
        default="tests/antichess/fixtures/notation-v1.json",
        type=Path,
    )
    parser.add_argument(
        "--bench-fixtures",
        default="tests/antichess/fixtures/bench-v1.json",
        type=Path,
    )
    args = parser.parse_args()
    document = json.loads(args.fixture_file.read_text(encoding="utf-8"))
    counts = validate(document)
    parser_document = json.loads(args.parser_fixtures.read_text(encoding="utf-8"))
    parser_count = validate_parser_boundaries(parser_document)
    repetition_document = json.loads(args.repetition_fixtures.read_text(encoding="utf-8"))
    repetition_counts = validate_repetition_boundaries(repetition_document)
    material_document = json.loads(args.material_fixtures.read_text(encoding="utf-8"))
    material_count = validate_material_boundaries(material_document)
    search_document = json.loads(args.search_fixtures.read_text(encoding="utf-8"))
    search_counts = validate_search_boundaries(search_document)
    claim_protocol_document = json.loads(
        args.claim_protocol_fixtures.read_text(encoding="utf-8")
    )
    claim_protocol_count = validate_claim_protocol_boundaries(claim_protocol_document)
    legacy_evaluator_document = json.loads(
        args.legacy_evaluator_fixtures.read_text(encoding="utf-8")
    )
    legacy_evaluator_count = validate_legacy_evaluator(legacy_evaluator_document)
    notation_document = json.loads(args.notation_fixtures.read_text(encoding="utf-8"))
    notation_count = validate_notation(notation_document)
    bench_document = json.loads(args.bench_fixtures.read_text(encoding="utf-8"))
    bench_count = validate_bench(bench_document)
    print(
        "fixture contract verified: "
        f"{counts[0]} positions, {counts[1]} histories, {counts[2]} rejected moves, "
        f"{counts[3]} core parser cases, {parser_count} boundary parser cases, "
        f"{counts[4]} service results, {repetition_counts[0]} repetition position cases, "
        f"{repetition_counts[1]} repetition history cases, {material_count} material cases, "
        f"{search_counts[0]} search cases, "
        f"{search_counts[1]} TT isolation cases, {claim_protocol_count} claim protocol cases, "
        f"{legacy_evaluator_count} legacy evaluator cases, {notation_count} notation cases, "
        f"{bench_count} bench records"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
