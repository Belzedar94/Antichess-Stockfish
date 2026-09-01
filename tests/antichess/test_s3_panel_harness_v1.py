#!/usr/bin/env python3
"""Self-tests for the fail-closed Antichess S3 panel contract."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.strength.panel_contract_v1 import (  # noqa: E402
    ContractError,
    EXPECTED_BOOK_SHA256,
    EXPECTED_CANDIDATE_COMMIT,
    EXPECTED_CANDIDATE_TREE,
    EXPECTED_FSF_BINARY_SHA256,
    EXPECTED_NETWORK_SHA256,
    PROFILE,
    REFEREE,
    STRENGTH_AUTH_SCHEMA,
    TIME_CONTROLS_MS,
    audit_mandatory_capture,
    complete_legal_set_equal,
    normalize_epd_book,
    parse_candidate_diagnostics,
    parse_fsf_perft_sections,
    scan_forbidden_log,
    validate_completed_pair,
    validate_strength_authorization,
    wld_statistics,
)
from tools.strength.run_fsf_pair_smoke_v1 import (  # noqa: E402
    AUTHORIZATION_SCHEMA as SMOKE_AUTHORIZATION_SCHEMA,
    EVIDENCE_CLASS as SMOKE_EVIDENCE_CLASS,
    validate_authorization as validate_smoke_authorization,
)


def valid_authorization() -> dict[str, object]:
    return {
        "schema": STRENGTH_AUTH_SCHEMA,
        "authorized": True,
        "profile": PROFILE,
        "referee": REFEREE,
        "candidate_commit": EXPECTED_CANDIDATE_COMMIT,
        "candidate_tree": EXPECTED_CANDIDATE_TREE,
        "candidate_binary_sha256": "1" * 64,
        "comparator_binary_sha256": EXPECTED_FSF_BINARY_SHA256,
        "network_sha256": EXPECTED_NETWORK_SHA256,
        "book_sha256": EXPECTED_BOOK_SHA256,
        "certification_status": "PASS",
        "certification_receipt_sha256": "2" * 64,
        "runner_sha256": "3" * 64,
        "schedule_sha256": "4" * 64,
        "time_controls_ms": {name: list(value) for name, value in TIME_CONTROLS_MS.items()},
        "threads_per_engine": 1,
        "hash_mib_per_engine": 512,
        "games_per_pair": 2,
        "minimum_games_exclusive": 100,
        "maximum_games": 64000,
        "target_displayed_los": "100.0",
        "loss_displayed_los": "0.0",
    }


class BookContractTests(unittest.TestCase):
    def test_normalization_and_schedule_are_deterministic(self) -> None:
        data = (
            b"8/8/8/8/8/8/P7/7k w - -\n"
            b"7k/p7/8/8/8/8/8/8 b - -\n"
        )
        first, first_hash = normalize_epd_book(data, expected_lines=2, seed="test-seed")
        second, second_hash = normalize_epd_book(data, expected_lines=2, seed="test-seed")
        self.assertEqual(first, second)
        self.assertEqual(first_hash, second_hash)
        self.assertEqual({opening.source_index for opening in first}, {1, 2})
        self.assertTrue(all(opening.fen.endswith(" 0 1") for opening in first))

    def test_duplicate_after_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(ContractError, "duplicate source"):
            normalize_epd_book(b"8/8/8/8/8/8/P7/7k w - -\n" * 2, expected_lines=2)

    def test_noncanonical_spacing_is_rejected(self) -> None:
        with self.assertRaisesRegex(ContractError, "spacing"):
            normalize_epd_book(b"8/8/8/8/8/8/P7/7k  w - -\n", expected_lines=1)


class ProtocolParserTests(unittest.TestCase):
    def test_candidate_diagnostic_parser(self) -> None:
        output = "antichess-info profile=LICHESS_ANTICHESS_V1|fen=8/8/8/8/8/8/P7/7k w - - 0 1|legal=a2a3,a2a4\n"
        fields = parse_candidate_diagnostics(output, 1)[0]
        self.assertEqual(fields["profile"], PROFILE)
        self.assertEqual(fields["legal"], "a2a3,a2a4")

    def test_fsf_perft_parser(self) -> None:
        output = "a2a4: 1\na2a3: 1\n\nNodes searched: 2\n\nh8g7: 1\nNodes searched: 1\n"
        self.assertEqual(parse_fsf_perft_sections(output, 2), [["a2a3", "a2a4"], ["h8g7"]])

    def test_fsf_perft_total_mismatch_is_rejected(self) -> None:
        with self.assertRaisesRegex(ContractError, "perft total"):
            parse_fsf_perft_sections("a2a3: 1\nNodes searched: 2\n", 1)


class MandatoryCaptureTests(unittest.TestCase):
    def test_ordinary_capture_suppresses_quiet_moves(self) -> None:
        fen = "8/8/8/3p4/4P3/8/8/8 w - - 0 1"
        self.assertTrue(audit_mandatory_capture(fen, ["e4d5"], referee_must_capture=True))
        with self.assertRaisesRegex(ContractError, "quiet move survived"):
            audit_mandatory_capture(fen, ["e4d5", "e4e5"])

    def test_en_passant_is_a_capture(self) -> None:
        fen = "8/8/8/3pP3/8/8/8/8 w - d6 0 1"
        self.assertTrue(audit_mandatory_capture(fen, ["e5d6"], referee_must_capture=True))

    def test_king_is_a_capturable_common_piece(self) -> None:
        fen = "8/8/8/3k4/4K3/8/8/8 w - - 0 1"
        self.assertTrue(audit_mandatory_capture(fen, ["e4d5"], referee_must_capture=True))


class StatisticalContractTests(unittest.TestCase):
    def test_atomic_formula_extreme_display(self) -> None:
        passing = wld_statistics(98, 0, 4)
        not_passing = wld_statistics(66, 35, 1)
        self.assertEqual(passing.total, 102)
        self.assertEqual(passing.displayed_los, "100.0")
        self.assertEqual(not_passing.displayed_los, "99.9")

    def test_zero_variance_has_no_displayed_los(self) -> None:
        self.assertIsNone(wld_statistics(0, 0, 102).displayed_los)
        self.assertIsNone(wld_statistics(102, 0, 0).displayed_los)


class PairAndAuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.opening = "8/8/8/8/8/8/P7/7k w - - 0 1"
        self.games = [
            {
                "white": "Antichess-Stockfish",
                "black": "Fairy-Stockfish",
                "variant": "Antichess",
                "fen": self.opening,
                "time_control": "2+0.02",
                "result": "1-0",
                "terminal_marker": True,
                "defects": [],
            },
            {
                "white": "Fairy-Stockfish",
                "black": "Antichess-Stockfish",
                "variant": "Antichess",
                "fen": self.opening,
                "time_control": "2+0.02",
                "result": "0-1",
                "terminal_marker": True,
                "defects": [],
            },
        ]

    def test_exact_color_pair_passes(self) -> None:
        validate_completed_pair(
            self.games,
            candidate="Antichess-Stockfish",
            comparator="Fairy-Stockfish",
            opening_fen=self.opening,
            time_control="2+0.02",
        )

    def test_pair_with_defect_fails(self) -> None:
        invalid = copy.deepcopy(self.games)
        invalid[1]["defects"] = ["time_loss"]
        with self.assertRaisesRegex(ContractError, "defects"):
            validate_completed_pair(
                invalid,
                candidate="Antichess-Stockfish",
                comparator="Fairy-Stockfish",
                opening_fen=self.opening,
                time_control="2+0.02",
            )

    def test_preregistration_cannot_authorize_strength(self) -> None:
        prereg = {
            "schema": "ANTICHESS_S3_FSF_PANEL_CERT_V1_PREREG",
            "authorized": False,
        }
        with self.assertRaisesRegex(ContractError, "schema"):
            validate_strength_authorization(prereg)

    def test_complete_authorization_passes(self) -> None:
        validate_strength_authorization(valid_authorization())

    def test_any_missing_hash_fails_authorization(self) -> None:
        authorization = valid_authorization()
        authorization["runner_sha256"] = None
        with self.assertRaisesRegex(ContractError, "runner_sha256"):
            validate_strength_authorization(authorization)

    def test_smoke_authorization_is_exactly_two_non_strength_games(self) -> None:
        output_dir = (ROOT / ".local" / "synthetic-smoke-output").resolve()
        authorization = {
            "authorized": True,
            "candidate_binary_sha256": "1" * 64,
            "evidence_class": SMOKE_EVIDENCE_CLASS,
            "games": 2,
            "output_dir": str(output_dir),
            "profile": PROFILE,
            "referee": REFEREE,
            "schema": SMOKE_AUTHORIZATION_SCHEMA,
            "strength_games": 0,
        }
        self.assertEqual(validate_smoke_authorization(authorization, output_dir), "1" * 64)

    def test_smoke_authorization_rejects_strength_label(self) -> None:
        output_dir = (ROOT / ".local" / "synthetic-smoke-output").resolve()
        authorization = {
            "authorized": True,
            "candidate_binary_sha256": "1" * 64,
            "evidence_class": SMOKE_EVIDENCE_CLASS,
            "games": 2,
            "output_dir": str(output_dir),
            "profile": PROFILE,
            "referee": REFEREE,
            "schema": SMOKE_AUTHORIZATION_SCHEMA,
            "strength_games": 2,
        }
        with self.assertRaisesRegex(ContractError, "mislabeled"):
            validate_smoke_authorization(authorization, output_dir)


class FailureMarkerTests(unittest.TestCase):
    def test_forbidden_markers_are_counted(self) -> None:
        counts = scan_forbidden_log("engine crashed\nplayer lost on time\nillegal move\n")
        self.assertEqual(counts["crash"], 1)
        self.assertEqual(counts["time_loss"], 1)
        self.assertEqual(counts["illegal_move"], 1)

    def test_legal_sets_compare_as_sets(self) -> None:
        self.assertTrue(complete_legal_set_equal(["a2a4", "a2a3"], ["a2a3", "a2a4"]))
        self.assertFalse(complete_legal_set_equal(["a2a3"], ["a2a4"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
