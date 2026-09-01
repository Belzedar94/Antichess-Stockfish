#!/usr/bin/env python3
"""Fast, game-free tests for the frozen S3 strength runner."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(ROOT))

from tools.strength.panel_contract_v1 import (  # noqa: E402
    EXPECTED_BOOK_SHA256,
    EXPECTED_CANDIDATE_COMMIT,
    EXPECTED_CANDIDATE_TREE,
    EXPECTED_FSF_BINARY_SHA256,
    EXPECTED_NETWORK_SHA256,
    PROFILE,
    REFEREE,
    STRENGTH_AUTH_SCHEMA,
    TIME_CONTROLS_MS,
    ContractError,
    Opening,
    sha256_file,
)
from tools.strength.run_fsf_same_net_3tc_v1 import (  # noqa: E402
    CANDIDATE_NAME,
    COMPARATOR_NAME,
    EVIDENCE_CLASS,
    EXPECTED_CANDIDATE_BINARY_SHA256,
    EXPECTED_CERTIFICATION_RECEIPT_SHA256,
    EXPECTED_LEASE_RESOURCE,
    EXPECTED_LEASE_SCHEMA,
    EXPECTED_RESOURCE_SNAPSHOT_SCHEMA,
    EXPECTED_PREREGISTRATION_SHA256,
    EXPECTED_PYTHON_DLL_SHA256,
    EXPECTED_PYTHON_SHA256,
    EXPECTED_SCHEDULE_SHA256,
    EXPERIMENT_ID,
    LOSS_DISPLAYED_LOS,
    MAXIMUM_GAMES,
    NO_COMPLETED_PAIR_TIMEOUT_SECONDS,
    PanelPaths,
    TARGET_DISPLAYED_LOS,
    TEST_PATH,
    TIME_MARGIN_MS,
    audit_pair,
    build_cutechess_command,
    candidate_outcome,
    gate_decision,
    pair_score_bucket,
    run_campaign,
    run_time_control,
    time_control_text,
    validate_compiler_output,
    validate_final_authorization,
    verify_raw_pair_log,
)


class GateTests(unittest.TestCase):
    def test_exact_time_control_text(self) -> None:
        self.assertEqual(time_control_text(2000, 20), "2+0.02")
        self.assertEqual(time_control_text(10000, 100), "10+0.1")
        self.assertEqual(time_control_text(30000, 300), "30+0.3")

    def test_gate_waits_for_exclusive_minimum(self) -> None:
        self.assertEqual(gate_decision(98, 0, 2).state, "CONTINUE")

    def test_gate_passes_exact_display_after_pair(self) -> None:
        decision = gate_decision(98, 0, 4)
        self.assertEqual(decision.total, 102)
        self.assertEqual(decision.displayed_los, TARGET_DISPLAYED_LOS)
        self.assertEqual(decision.state, "PASS")

    def test_gate_rejects_symmetric_loss(self) -> None:
        decision = gate_decision(0, 98, 4)
        self.assertEqual(decision.displayed_los, LOSS_DISPLAYED_LOS)
        self.assertEqual(decision.state, "REJECTED_LOSS_GATE")

    def test_gate_rejects_maximum_miss(self) -> None:
        decision = gate_decision(MAXIMUM_GAMES // 2, MAXIMUM_GAMES // 2, 0)
        self.assertEqual(decision.state, "REJECTED_MAXIMUM_MISS")

    def test_gate_rejects_odd_total(self) -> None:
        self.assertEqual(gate_decision(51, 50, 0).state, "INVALID_ODD_TOTAL")

    def test_pair_score_buckets(self) -> None:
        self.assertEqual(pair_score_bucket(("loss", "loss")), "0.0")
        self.assertEqual(pair_score_bucket(("loss", "draw")), "0.5")
        self.assertEqual(pair_score_bucket(("win", "loss")), "1.0")
        self.assertEqual(pair_score_bucket(("win", "draw")), "1.5")
        self.assertEqual(pair_score_bucket(("win", "win")), "2.0")


class CommandTests(unittest.TestCase):
    def paths(self, root: Path) -> PanelPaths:
        return PanelPaths(
            authorization=root / "authorization.json",
            candidate=root / "candidate.exe",
            comparator=root / "comparator.exe",
            network=root / "network.nnue",
            book=root / "book.epd",
            cli=root / "cutechess-cli.exe",
            probe=root / "probe.exe",
            qt_bin=root / "qt",
            output_dir=root / "output",
            lease=root / "lease.json",
        )

    def test_command_is_exact_pair_without_adjudication_or_depth(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            command, tc, event = build_cutechess_command(
                self.paths(root),
                tc_name="VSTC",
                pair_index=7,
                opening_path=root / "opening.epd",
                pgn_path=root / "games.pgn",
            )
        joined = " ".join(command)
        self.assertEqual(tc, "2+0.02")
        self.assertEqual(event, "Antichess S3 same-net VSTC pair 00007")
        self.assertIn("option.Antichess_Search=alpha-beta-v1", command)
        self.assertIn("option.Use NNUE=true", command)
        self.assertEqual(command.count("option.Hash=512"), 2)
        self.assertEqual(command.count("option.Threads=1"), 2)
        self.assertIn("-concurrency 1", joined)
        self.assertIn("-games 2", joined)
        for forbidden in ("-depth", "-maxmoves", "-draw", "-resign", "-tb", "-sprt", "-recover", "-noswap", "-reverse"):
            self.assertNotIn(forbidden, command)

    def test_candidate_outcomes_follow_engine_color(self) -> None:
        self.assertEqual(candidate_outcome({"White": CANDIDATE_NAME, "Black": COMPARATOR_NAME, "Result": "1-0"}), "win")
        self.assertEqual(candidate_outcome({"White": COMPARATOR_NAME, "Black": CANDIDATE_NAME, "Result": "1-0"}), "loss")
        self.assertEqual(candidate_outcome({"White": COMPARATOR_NAME, "Black": CANDIDATE_NAME, "Result": "1/2-1/2"}), "draw")

    def test_compiler_preflight_accepts_only_frozen_common_target(self) -> None:
        candidate = "Compiled by                : g++ (GNUC) 16.1.0 on MinGW64\nCompilation settings       : 64bit SSE2\n"
        comparator = "Compiled by g++ (GNUC) 16.1.0 on MinGW64\nCompilation settings include:  64bit SSE2\n"
        self.assertEqual(validate_compiler_output(candidate, label="candidate"), validate_compiler_output(comparator, label="comparator"))
        with self.assertRaisesRegex(ContractError, "64bit SSE2"):
            validate_compiler_output(candidate.replace("64bit SSE2", "64bit AVX2"), label="candidate")

    def test_raw_log_requires_load_and_option_evidence(self) -> None:
        network = Path("C:/frozen/antichess.nnue")
        text = "\n".join(
            (
                "setoption name UCI_Variant value antichess",
                "setoption name Antichess_Evaluator value legacy-v1",
                "setoption name Antichess_Search value alpha-beta-v1",
                "setoption name Use NNUE value true",
                "setoption name Hash value 512",
                "setoption name Threads value 1",
                f"setoption name EvalFile value {network}",
                "Loaded Antichess legacy-v1 network",
                "NNUE evaluation using antichess.nnue enabled",
                "bestmove a2a3",
            )
        )
        evidence = verify_raw_pair_log(text, network)
        self.assertTrue(all(value > 0 for value in evidence["required_pattern_counts"].values()))

    def test_raw_log_rejects_time_loss(self) -> None:
        for marker in ("time loss", "White loses on time", "engine forfeited on time"):
            with self.subTest(marker=marker), self.assertRaisesRegex(ContractError, "forbidden"):
                verify_raw_pair_log(marker, Path("network.nnue"))


class PairAuditTests(unittest.TestCase):
    def test_forced_terminal_pair_replays_and_scores(self) -> None:
        fen = "8/8/8/3p4/4B3/8/8/8 w - - 0 1"
        event = "Antichess S3 same-net VSTC pair 00001"
        games = []
        for white, black in ((CANDIDATE_NAME, COMPARATOR_NAME), (COMPARATOR_NAME, CANDIDATE_NAME)):
            games.append(
                "\n".join(
                    (
                        f'[Event "{event}"]',
                        '[Site "?"]',
                        '[Date "2026.09.01"]',
                        '[Round "1"]',
                        f'[White "{white}"]',
                        f'[Black "{black}"]',
                        '[Result "1-0"]',
                        '[SetUp "1"]',
                        f'[FEN "{fen}"]',
                        '[Variant "Antichess"]',
                        '[TimeControl "2+0.02"]',
                        '[PlyCount "1"]',
                        "",
                        "1. Bxd5# {0.01s} 1-0",
                        "",
                    )
                )
            )

        def fake_probe(_probe: Path, _fen: str, moves: list[str], _environment: dict[str, str]) -> dict[str, str]:
            if not moves:
                return {
                    "end": "0",
                    "must_capture": "1",
                    "notation": "e4d5=Bxd5#",
                }
            self.assertEqual(moves, ["e4d5"])
            return {
                "board_result": "win",
                "board_result_winner": "white",
                "end": "1",
                "must_capture": "0",
                "notation": "",
            }

        with tempfile.TemporaryDirectory() as temporary:
            pgn = Path(temporary) / "games.pgn"
            pgn.write_text("\n".join(games), encoding="utf-8")
            audit = audit_pair(
                pgn,
                {"event": event, "opening_fen": fen, "time_control": "2+0.02"},
                Path("probe.exe"),
                Path("qt"),
                probe_runner=fake_probe,
            )
        self.assertEqual(audit["candidate_outcomes"], ["win", "loss"])
        self.assertEqual(audit["pentanomial_bucket"], "1.0")
        self.assertEqual(audit["mandatory_positions"], 2)


class RunnerFlowTests(unittest.TestCase):
    def paths(self, root: Path) -> PanelPaths:
        return PanelPaths(
            authorization=root / "authorization.json",
            candidate=root / "candidate.exe",
            comparator=root / "comparator.exe",
            network=root / "network.nnue",
            book=root / "book.epd",
            cli=root / "cutechess-cli.exe",
            probe=root / "probe.exe",
            qt_bin=root / "qt",
            output_dir=root / "output",
            lease=root / "lease.json",
        )

    def test_time_control_stops_at_first_eligible_passing_pair(self) -> None:
        opening = Opening(1, "8/8/8/8/8/8/8/8 w - -", "8/8/8/8/8/8/8/8 w - - 0 1", "a" * 64)

        def fake_pair(_paths: PanelPaths, **kwargs: object) -> dict[str, object]:
            pair_index = int(kwargs["pair_index"])
            outcomes = ["win", "win"] if pair_index <= 49 else ["draw", "draw"]
            return {
                "artifacts": {},
                "candidate_outcomes": outcomes,
                "mandatory_positions": 2,
                "opening_schedule_key": "a" * 64,
                "opening_source_index": 1,
                "pair_index": pair_index,
                "pentanomial_bucket": pair_score_bucket(outcomes),
                "tc_name": "VSTC",
                "time_control": "2+0.02",
                "total_plies": 2,
            }

        with tempfile.TemporaryDirectory() as temporary:
            paths = self.paths(Path(temporary))
            paths.output_dir.mkdir()
            with patch("tools.strength.run_fsf_same_net_3tc_v1.run_pair", side_effect=fake_pair), patch("builtins.print"):
                result = run_time_control(paths, authorization_sha256="f" * 64, tc_name="VSTC", openings=[opening])
            ledger_lines = (paths.output_dir / "VSTC" / "pair-ledger.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["completed_pairs"], 51)
        self.assertEqual(len(ledger_lines), 51)

    def test_campaign_does_not_run_later_tc_after_rejection(self) -> None:
        paths = self.paths(Path("C:/synthetic"))
        calls: list[str] = []

        def fake_tc(_paths: PanelPaths, **kwargs: object) -> dict[str, object]:
            tc_name = str(kwargs["tc_name"])
            calls.append(tc_name)
            return {"status": "REJECTED_LOSS_GATE", "tc_name": tc_name}

        with patch("tools.strength.run_fsf_same_net_3tc_v1.run_time_control", side_effect=fake_tc):
            code, aggregate = run_campaign(paths, authorization_sha256="f" * 64, openings=[])
        self.assertEqual(code, 1)
        self.assertEqual(aggregate["status"], "REJECTED_STRENGTH")
        self.assertEqual(calls, ["VSTC"])


class AuthorizationTests(unittest.TestCase):
    def test_final_authorization_binds_runner_merge_ci_lease_and_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = PanelPaths(
                authorization=root / "authorization.json",
                candidate=root / "candidate.exe",
                comparator=root / "comparator.exe",
                network=root / "network.nnue",
                book=root / "book.epd",
                cli=root / "cutechess-cli.exe",
                probe=root / "probe.exe",
                qt_bin=root / "qt",
                output_dir=root / "output",
                lease=root / "lease.json",
            )
            lease = {
                "schema": EXPECTED_LEASE_SCHEMA,
                "status": "ACTIVE",
                "project": "Antichess-Stockfish",
                "experiment_id": EXPERIMENT_ID,
                "resource": EXPECTED_LEASE_RESOURCE,
                "host": platform.node(),
                "owner_pid": os.getpid(),
                "candidate_binary_sha256": EXPECTED_CANDIDATE_BINARY_SHA256,
                "comparator_binary_sha256": EXPECTED_FSF_BINARY_SHA256,
                "network_sha256": EXPECTED_NETWORK_SHA256,
            }
            paths.lease.write_text(json.dumps(lease), encoding="utf-8")
            snapshot_entries = []
            for index in (1, 2):
                snapshot_path = root / f"snapshot-{index}.json"
                snapshot_path.write_text(
                    json.dumps(
                        {
                            "schema": EXPECTED_RESOURCE_SNAPSHOT_SCHEMA,
                            "host": platform.node(),
                            "foreign_variant_load": False,
                            "foreign_active_lease": False,
                        }
                    ),
                    encoding="utf-8",
                )
                snapshot_entries.append(
                    {
                        "foreign_variant_load": False,
                        "foreign_active_lease": False,
                        "path": str(snapshot_path.resolve()),
                        "snapshot_sha256": sha256_file(snapshot_path),
                    }
                )
            authorization: dict[str, object] = {
                "schema": STRENGTH_AUTH_SCHEMA,
                "authorized": True,
                "profile": PROFILE,
                "referee": REFEREE,
                "experiment_id": EXPERIMENT_ID,
                "evidence_class": EVIDENCE_CLASS,
                "candidate_commit": EXPECTED_CANDIDATE_COMMIT,
                "candidate_tree": EXPECTED_CANDIDATE_TREE,
                "candidate_binary_sha256": EXPECTED_CANDIDATE_BINARY_SHA256,
                "comparator_binary_sha256": EXPECTED_FSF_BINARY_SHA256,
                "network_sha256": EXPECTED_NETWORK_SHA256,
                "book_sha256": EXPECTED_BOOK_SHA256,
                "certification_status": "PASS",
                "certification_receipt_sha256": EXPECTED_CERTIFICATION_RECEIPT_SHA256,
                "runner_sha256": sha256_file(ROOT / "tools" / "strength" / "run_fsf_same_net_3tc_v1.py"),
                "runner_tests_sha256": sha256_file(TEST_PATH),
                "runner_git_blob_sha256": hashlib.sha256(
                    (ROOT / "tools" / "strength" / "run_fsf_same_net_3tc_v1.py").read_bytes().replace(b"\r\n", b"\n")
                ).hexdigest(),
                "runner_tests_git_blob_sha256": hashlib.sha256(TEST_PATH.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                "schedule_sha256": EXPECTED_SCHEDULE_SHA256,
                "preregistration_sha256": EXPECTED_PREREGISTRATION_SHA256,
                "referee_cli_sha256": "62377837474f166edfae5dcc5801b19bdf0ee28c89ac4bc66832d535be73ae9f",
                "referee_probe_sha256": "fd45f1f066ce6ff3017a193d5333ccc95e676f9fc795cdd74722abac7564b109",
                "qt_core_sha256": "9cf7924077f1ac8758a456e780d9f408c779e76e58680a77ef30ef9807295c43",
                "python_executable_sha256": EXPECTED_PYTHON_SHA256,
                "python_dll_sha256": EXPECTED_PYTHON_DLL_SHA256,
                "lease_sha256": sha256_file(paths.lease),
                "time_controls_ms": {name: list(value) for name, value in TIME_CONTROLS_MS.items()},
                "time_control_order": ["VSTC", "STC", "LTC"],
                "threads_per_engine": 1,
                "hash_mib_per_engine": 512,
                "games_per_pair": 2,
                "minimum_games_exclusive": 100,
                "maximum_games": 64000,
                "target_displayed_los": "100.0",
                "loss_displayed_los": "0.0",
                "controllers": 1,
                "concurrency": 1,
                "time_margin_ms": TIME_MARGIN_MS,
                "no_completed_pair_timeout_seconds": NO_COMPLETED_PAIR_TIMEOUT_SECONDS,
                "sprt": False,
                "score_adjudication": False,
                "tablebases": False,
                "output_root_create_once": True,
                "host": platform.node(),
                "implementation_merge_commit": "a" * 40,
                "implementation_merge_tree": "b" * 40,
                "exact_head_review_status": "PASS",
                "postmerge_ci_status": "PASS",
                "postmerge_ci_run": "12345",
                "strength_games_before_authorization": 0,
                "resource_snapshots": snapshot_entries,
                "paths": {
                    "candidate": str(paths.candidate.resolve()),
                    "comparator": str(paths.comparator.resolve()),
                    "network": str(paths.network.resolve()),
                    "book": str(paths.book.resolve()),
                    "cli": str(paths.cli.resolve()),
                    "probe": str(paths.probe.resolve()),
                    "qt_bin": str(paths.qt_bin.resolve()),
                    "output_dir": str(paths.output_dir.resolve()),
                    "lease": str(paths.lease.resolve()),
                },
            }
            paths.authorization.write_text(json.dumps(authorization), encoding="utf-8")
            validate_final_authorization(
                authorization,
                paths=paths,
                authorization_sha256=sha256_file(paths.authorization),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
