#!/usr/bin/env python3
"""Certify exact inputs for the Antichess vs Fairy-Stockfish S3 panel."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.strength.panel_contract_v1 import (  # noqa: E402
    CERT_PREREG_SCHEMA,
    ContractError,
    EXPECTED_BOOK_LINES,
    EXPECTED_BOOK_SHA256,
    EXPECTED_CANDIDATE_COMMIT,
    EXPECTED_CANDIDATE_TREE,
    EXPECTED_FSF_BINARY_SHA256,
    EXPECTED_FSF_COMMIT,
    EXPECTED_FSF_TREE,
    EXPECTED_NETWORK_SHA256,
    EXPECTED_OFFICIAL_ANCESTOR,
    EXPECTED_PREREG_SHA256,
    EXPECTED_QT_CORE_SHA256,
    EXPECTED_REFEREE_CLI_SHA256,
    EXPECTED_REFEREE_PROBE_SHA256,
    PROFILE,
    REFEREE,
    assert_exact_hash,
    audit_mandatory_capture,
    complete_legal_set_equal,
    legal_moves_from_fields,
    load_json,
    normalize_epd_book,
    parse_candidate_diagnostics,
    parse_fsf_perft_sections,
    parse_pipe_diagnostic,
    require,
    sha256_file,
    validate_strength_authorization,
    write_json_exclusive,
)


EXPECTED_PYTHON = (3, 12, 0)
EXPECTED_PYTHON_SHA256 = (
    "42ac541168e97dedb9aabd8be335539fc41c682e414b9e8d137b164fb68683b0"
)
EXPECTED_NETWORK_BYTES = 953_248
EXPECTED_BOOK_BYTES = 11_862
BUILD_SCHEMA = "ANTICHESS_S3_CANDIDATE_WINDOWS_BUILD_V1"
IMPLEMENTATION_FREEZE_SCHEMA = "ANTICHESS_S3_PANEL_CERT_V2_IMPLEMENTATION_FREEZE"
SMOKE_AUTHORIZATION_SCHEMA = "ANTICHESS_S3_PAIR_PLUMBING_SMOKE_V1_AUTHORIZATION"
V2_ADDENDUM_SCHEMA = "ANTICHESS_S3_FSF_PANEL_CERT_V2_ADDENDUM"
EXPECTED_V2_ADDENDUM_SHA256 = (
    "21f571ffc89b034398361a84afe56272a7382b6ce3b870c33afb1bfb68312c7e"
)
FSF_NEGATIVE_NETWORK_BASENAME = "antichess-missing-fsf-network.nnue"


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    require(completed.returncode == 0, f"git {' '.join(arguments)} failed in {root}: {completed.stdout}")
    return completed.stdout.strip()


def is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", ancestor, descendant],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    require(completed.returncode in {0, 1}, f"git ancestry probe failed in {root}")
    return completed.returncode == 0


def git_object_exists(root: Path, object_name: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", object_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    require(completed.returncode in {0, 1, 128}, f"git object probe failed in {root}")
    return completed.returncode == 0


def run_text(binary: Path, commands: Sequence[str], *, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(binary)],
        input="\n".join([*commands, "quit", ""]),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def save_transcript(path: Path, completed: subprocess.CompletedProcess[str]) -> None:
    path.write_text(completed.stdout, encoding="utf-8", errors="strict", newline="\n")


def common_candidate_options(network: Path) -> list[str]:
    return [
        "uci",
        "setoption name UCI_Variant value antichess",
        f"setoption name EvalFile value {network}",
        "setoption name Antichess_Evaluator value legacy-v1",
        "setoption name Antichess_Search value alpha-beta-v1",
        "setoption name Threads value 1",
        "setoption name Hash value 512",
        "ucinewgame",
        "isready",
    ]


def common_fsf_options(network: Path) -> list[str]:
    return [
        "uci",
        "setoption name UCI_Variant value antichess",
        "setoption name Use NNUE value true",
        f"setoption name EvalFile value {network}",
        "setoption name Threads value 1",
        "setoption name Hash value 512",
        "ucinewgame",
        "isready",
    ]


def verify_candidate_network(candidate: Path, network: Path, output_dir: Path) -> dict[str, Any]:
    positive = run_text(
        candidate,
        [
            *common_candidate_options(network),
            "position startpos",
            "antichess-info",
            "eval",
            "go depth 1",
        ],
    )
    save_transcript(output_dir / "candidate-network-positive.log", positive)
    require(positive.returncode == 0, f"candidate positive load exited {positive.returncode}")
    fields = parse_candidate_diagnostics(positive.stdout, 1)[0]
    expected = {
        "profile": PROFILE,
        "uci_variant": "antichess",
        "evaluator": "legacy-v1",
        "search": "alpha-beta-v1",
        "threads": "1",
        "hash_mb": "512",
        "network_loaded": "1",
        "network_format": "legacy-v1",
        "network_file": network.name,
        "tt_enabled": "1",
    }
    for key, value in expected.items():
        require(fields.get(key) == value, f"candidate positive load {key} drift")
    require(str(network) in positive.stdout, "candidate did not report the exact resolved network path")
    require("Loaded Antichess legacy-v1 network" in positive.stdout, "candidate load marker absent")
    bestmoves = re.findall(r"^bestmove (\S+)$", positive.stdout, flags=re.MULTILINE)
    require(len(bestmoves) == 1 and bestmoves[0] != "(none)", "candidate positive probe produced no playing bestmove")

    missing = output_dir / "missing-candidate-network.nnue"
    require(not missing.exists(), "negative candidate network path unexpectedly exists")
    negative = run_text(
        candidate,
        [
            *common_candidate_options(missing),
            "position startpos",
            "antichess-info",
            "eval",
            "go depth 1",
        ],
    )
    save_transcript(output_dir / "candidate-network-negative.log", negative)
    require(negative.returncode == 0, f"candidate fail-closed probe exited {negative.returncode}")
    negative_fields = parse_candidate_diagnostics(negative.stdout, 1)[0]
    require(negative_fields.get("network_loaded") == "0", "candidate retained a network after missing-file load")
    require(negative_fields.get("network_format") == "none", "candidate exposed a missing network format")
    require("network" in negative.stdout.lower() and "not ready" in negative.stdout.lower(), "candidate negative load error absent")
    negative_bestmoves = re.findall(r"^bestmove (\S+)$", negative.stdout, flags=re.MULTILINE)
    require(negative_bestmoves == ["(none)"], f"candidate missing network produced {negative_bestmoves!r}")
    return {
        "positive_return_code": positive.returncode,
        "positive_bestmove": bestmoves[0],
        "negative_return_code": negative.returncode,
        "negative_bestmoves": negative_bestmoves,
    }


def verify_fsf_network(comparator: Path, network: Path, output_dir: Path) -> dict[str, Any]:
    positive = run_text(
        comparator,
        [*common_fsf_options(network), "position startpos", "go depth 1"],
    )
    save_transcript(output_dir / "fsf-network-positive.log", positive)
    require(positive.returncode == 0, f"Fairy-Stockfish positive load exited {positive.returncode}")
    require("option name UCI_Variant type combo" in positive.stdout, "Fairy-Stockfish lacks UCI_Variant")
    require(" var antichess" in positive.stdout, "Fairy-Stockfish option surface lacks antichess")
    require("option name Use NNUE type check" in positive.stdout, "Fairy-Stockfish lacks Use NNUE")
    require("option name Hash type spin" in positive.stdout and "max 33554432" in positive.stdout, "Fairy-Stockfish Hash capacity drift")
    require("info string variant antichess " in positive.stdout, "Fairy-Stockfish did not activate exact antichess")
    require(f"info string NNUE evaluation using {network} enabled" in positive.stdout, "Fairy-Stockfish did not report the exact network")
    require("classical evaluation enabled" not in positive.stdout, "Fairy-Stockfish silently selected classical evaluation")
    bestmoves = re.findall(r"^bestmove (\S+)$", positive.stdout, flags=re.MULTILINE)
    require(len(bestmoves) == 1 and bestmoves[0] != "(none)", "Fairy-Stockfish positive probe produced no playing bestmove")

    missing = output_dir / FSF_NEGATIVE_NETWORK_BASENAME
    require(not missing.exists(), "negative Fairy-Stockfish network path unexpectedly exists")
    negative = run_text(
        comparator,
        [*common_fsf_options(missing), "position startpos", "go depth 1"],
    )
    save_transcript(output_dir / "fsf-network-negative.log", negative)
    require(negative.returncode != 0, "Fairy-Stockfish silently survived a missing required NNUE")
    require("was not loaded successfully" in negative.stdout, "Fairy-Stockfish missing-network error absent")
    require("engine will be terminated now" in negative.stdout.lower(), "Fairy-Stockfish fail-closed termination marker absent")
    require(not re.search(r"^bestmove \S+$", negative.stdout, flags=re.MULTILINE), "Fairy-Stockfish searched after a missing-network failure")
    return {
        "positive_return_code": positive.returncode,
        "positive_bestmove": bestmoves[0],
        "negative_return_code": negative.returncode,
        "negative_bestmoves": [],
    }


def gather_focused_cases() -> list[dict[str, Any]]:
    core = load_json(ROOT / "tests/antichess/fixtures/core-v1.json")
    material = load_json(ROOT / "tests/antichess/fixtures/material-boundaries-v1.json")
    repetition = load_json(ROOT / "tests/antichess/fixtures/repetition-boundaries-v1.json")
    notation = load_json(ROOT / "tests/antichess/fixtures/notation-v1.json")
    parser_boundaries = load_json(ROOT / "tests/antichess/fixtures/parser-boundaries-v1.json")
    cases: list[dict[str, Any]] = []

    def add(prefix: str, fixtures: Iterable[dict[str, Any]]) -> None:
        for fixture in fixtures:
            fen = fixture.get("fen", fixture.get("initial_fen"))
            require(isinstance(fen, str), f"{prefix}/{fixture.get('id')}: missing FEN")
            cases.append(
                {
                    "id": f"{prefix}/{fixture['id']}",
                    "fen": fen,
                    "moves": [str(move) for move in fixture.get("moves", [])],
                }
            )

    add("core-position", core["position_fixtures"])
    add("core-history", core["history_fixtures"])
    add("material-history", material["history_cases"])
    add("repetition-position", repetition["position_cases"])
    add("repetition-history", repetition["history_cases"])
    add("notation", notation["cases"])
    add("move-rejection-context", core["move_rejection_fixtures"])
    accepted = [
        fixture
        for fixture in [*core["parser_fixtures"], *parser_boundaries["cases"]]
        if fixture["project_policy"] == "accept"
    ]
    add("accepted-parser", accepted)
    require(len({case["id"] for case in cases}) == len(cases), "focused case IDs are not unique")
    return cases


def position_command(case: dict[str, Any]) -> str:
    suffix = "" if not case["moves"] else " moves " + " ".join(case["moves"])
    return f"position fen {case['fen']}{suffix}"


def run_referee_cases(
    probe: Path,
    qt_bin: Path,
    cases: Sequence[dict[str, Any]],
    log_path: Path,
) -> list[dict[str, str]]:
    environment = os.environ.copy()
    environment["PATH"] = str(qt_bin) + os.pathsep + environment.get("PATH", "")
    diagnostics: list[dict[str, str]] = []
    with log_path.open("x", encoding="utf-8", newline="\n") as log:
        for case in cases:
            completed = subprocess.run(
                [str(probe), case["fen"], *case["moves"]],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
            log.write(f"case={case['id']} return_code={completed.returncode}\n")
            log.write(completed.stdout)
            if not completed.stdout.endswith("\n"):
                log.write("\n")
            require(completed.returncode == 0, f"{case['id']}: AC_REFEREE_V1 exited {completed.returncode}")
            diagnostics.append(parse_pipe_diagnostic(completed.stdout, "referee-info "))
    return diagnostics


def run_candidate_legal_sets(
    candidate: Path,
    network: Path,
    cases: Sequence[dict[str, Any]],
    log_path: Path,
) -> list[dict[str, str]]:
    commands = common_candidate_options(network)
    for case in cases:
        commands.extend([position_command(case), "antichess-info"])
    completed = run_text(candidate, commands, timeout=max(120, len(cases) * 2))
    save_transcript(log_path, completed)
    require(completed.returncode == 0, f"candidate legal-set batch exited {completed.returncode}")
    diagnostics = parse_candidate_diagnostics(completed.stdout, len(cases))
    for case, fields in zip(cases, diagnostics, strict=True):
        require(fields.get("profile") == PROFILE, f"{case['id']}: candidate profile drift")
        require(fields.get("network_loaded") == "1", f"{case['id']}: candidate network disappeared")
        require(fields.get("evaluator") == "legacy-v1", f"{case['id']}: candidate evaluator drift")
        require(fields.get("search") == "alpha-beta-v1", f"{case['id']}: candidate search drift")
        require(fields.get("threads") == "1" and fields.get("hash_mb") == "512", f"{case['id']}: candidate resources drift")
    return diagnostics


def run_fsf_legal_sets(
    comparator: Path,
    network: Path,
    cases: Sequence[dict[str, Any]],
    log_path: Path,
) -> list[list[str]]:
    commands = common_fsf_options(network)
    for case in cases:
        commands.extend([position_command(case), "go perft 1"])
    completed = run_text(comparator, commands, timeout=max(120, len(cases) * 3))
    save_transcript(log_path, completed)
    require(completed.returncode == 0, f"Fairy-Stockfish legal-set batch exited {completed.returncode}")
    return parse_fsf_perft_sections(completed.stdout, len(cases))


def compare_legal_sets(
    cases: Sequence[dict[str, Any]],
    referee: Sequence[dict[str, str]],
    candidate: Sequence[dict[str, str]],
    comparator: Sequence[Sequence[str]],
    *,
    require_ongoing: bool,
) -> tuple[list[dict[str, Any]], int]:
    require(len(cases) == len(referee) == len(candidate) == len(comparator), "legal-set batch cardinality drift")
    records: list[dict[str, Any]] = []
    mandatory_count = 0
    for case, ref_fields, candidate_fields, fsf_moves in zip(cases, referee, candidate, comparator, strict=True):
        ref_moves = legal_moves_from_fields(ref_fields, label=f"{case['id']}/referee")
        candidate_moves = legal_moves_from_fields(candidate_fields, label=f"{case['id']}/candidate")
        fsf_moves_sorted = sorted(fsf_moves)
        require(
            complete_legal_set_equal(ref_moves, candidate_moves, fsf_moves_sorted),
            f"{case['id']}: three-way legal-set mismatch: referee={ref_moves!r} candidate={candidate_moves!r} comparator={fsf_moves_sorted!r}",
        )
        require(candidate_fields.get("fen") == ref_fields.get("fen"), f"{case['id']}: canonical FEN mismatch")
        if require_ongoing:
            require(ref_fields.get("end") == "0", f"{case['id']}: opening is terminal")
            require(ref_fields.get("variant_end") == "0", f"{case['id']}: opening is a variant end")
            require(ref_fields.get("automatic_draw") == "0", f"{case['id']}: opening is an automatic draw")
            require(bool(ref_moves), f"{case['id']}: opening has an empty legal set")
        is_mandatory = audit_mandatory_capture(
            ref_fields["fen"],
            ref_moves,
            referee_must_capture=ref_fields.get("must_capture") == "1",
        )
        mandatory_count += int(is_mandatory)
        records.append(
            {
                "canonical_fen": ref_fields["fen"],
                "id": case["id"],
                "legal_moves": ref_moves,
                "mandatory_capture": is_mandatory,
            }
        )
    return records, mandatory_count


def verify_build_manifest(
    manifest_path: Path,
    expected_manifest_sha256: str,
    candidate: Path,
) -> dict[str, Any]:
    assert_exact_hash(manifest_path, expected_manifest_sha256, "candidate build manifest")
    manifest = load_json(manifest_path)
    require(manifest.get("schema") == BUILD_SCHEMA, "candidate build manifest schema drift")
    require(manifest.get("source_commit") == EXPECTED_CANDIDATE_COMMIT, "build source commit drift")
    require(manifest.get("source_tree") == EXPECTED_CANDIDATE_TREE, "build source tree drift")
    require(manifest.get("source_date_epoch") == 1788236859, "build epoch drift")
    require(manifest.get("clean_runs") == 2, "build manifest does not contain two clean runs")
    require(manifest.get("byte_identical") is True, "candidate dual build was not byte-identical")
    selected_hash = manifest.get("selected_binary_sha256")
    require(isinstance(selected_hash, str) and re.fullmatch(r"[0-9a-f]{64}", selected_hash) is not None, "build manifest selected hash missing")
    assert_exact_hash(candidate, selected_hash, "candidate Windows binary")
    return manifest


def verify_implementation_freeze(
    freeze_path: Path,
    expected_freeze_sha256: str,
) -> tuple[dict[str, Any], str]:
    freeze_sha256 = assert_exact_hash(
        freeze_path,
        expected_freeze_sha256,
        "certification implementation freeze",
    )
    freeze = load_json(freeze_path)
    require(freeze.get("schema") == IMPLEMENTATION_FREEZE_SCHEMA, "implementation-freeze schema drift")
    require(freeze.get("status") == "IMPLEMENTED_UNEXECUTED", "implementation freeze is not unexecuted")
    require(freeze.get("preregistration_sha256") == EXPECTED_PREREG_SHA256, "implementation freeze preregistration drift")
    require(freeze.get("v2_addendum_sha256") == EXPECTED_V2_ADDENDUM_SHA256, "implementation freeze v2 addendum drift")
    require(freeze.get("certification_execution_count") == 0, "implementation freeze already records a certification execution")
    require(freeze.get("plumbing_smoke_games") == 0, "implementation freeze already records a plumbing smoke")
    require(freeze.get("strength_games") == 0, "implementation freeze records strength games")
    files = freeze.get("files")
    require(isinstance(files, dict) and files, "implementation freeze has no file identities")
    for relative_path, expected_sha256 in files.items():
        require(isinstance(relative_path, str) and isinstance(expected_sha256, str), "malformed implementation-freeze file entry")
        assert_exact_hash(ROOT / relative_path, expected_sha256, f"frozen implementation file {relative_path}")
    return freeze, freeze_sha256


def run_checked_subprocess(command: Sequence[str], log_path: Path, *, timeout: int) -> str:
    completed = subprocess.run(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    log_path.write_text(completed.stdout, encoding="utf-8", newline="\n")
    require(completed.returncode == 0, f"subprocess exited {completed.returncode}: {' '.join(map(str, command))}")
    return completed.stdout


def run_certification(args: argparse.Namespace) -> int:
    output_dir = args.output_dir.resolve()
    require(not output_dir.exists(), f"refusing to overwrite evidence directory: {output_dir}")
    output_dir.mkdir(parents=True)
    started_at = utc_now()
    started = time.monotonic()

    prereg_path = args.prereg.resolve()
    v2_addendum_path = args.v2_addendum.resolve()
    candidate = args.candidate.resolve()
    comparator = args.comparator.resolve()
    network = args.network.resolve()
    book = args.book.resolve()
    probe = args.referee_probe.resolve()
    cli = args.cutechess_cli.resolve()
    qt_bin = args.qt_bin.resolve()
    candidate_root = args.candidate_source_root.resolve()
    fsf_root = args.fsf_source_root.resolve()
    cutechess_root = args.cutechess_root.resolve()
    build_manifest_path = args.candidate_build_manifest.resolve()
    implementation_freeze_path = args.implementation_freeze.resolve()

    require(tuple(sys.version_info[:3]) == EXPECTED_PYTHON, f"Python {sys.version_info[:3]} != {EXPECTED_PYTHON}")
    python_sha = assert_exact_hash(Path(sys.executable), EXPECTED_PYTHON_SHA256, "normative Python executable")
    prereg_sha = assert_exact_hash(prereg_path, EXPECTED_PREREG_SHA256, "S3 certification preregistration")
    prereg = load_json(prereg_path)
    require(prereg.get("schema") == CERT_PREREG_SCHEMA, "certification preregistration schema drift")
    require(prereg.get("status") == "PREREGISTERED_INPUTS_UNEXECUTED", "certification preregistration status drift")
    require(prereg["target_panel"]["authorized_by_this_preregistration"] is False, "certification prereg unexpectedly authorizes strength")
    v2_addendum_sha256 = assert_exact_hash(
        v2_addendum_path,
        EXPECTED_V2_ADDENDUM_SHA256,
        "S3 certification v2 addendum",
    )
    v2_addendum = load_json(v2_addendum_path)
    require(v2_addendum.get("schema") == V2_ADDENDUM_SCHEMA, "certification v2 addendum schema drift")
    require(v2_addendum.get("status") == "PREREGISTERED_UNEXECUTED", "certification v2 addendum status drift")
    require(
        v2_addendum["change_control"]["new_value"] == FSF_NEGATIVE_NETWORK_BASENAME,
        "certification v2 negative basename drift",
    )
    require(
        v2_addendum["change_control"]["all_other_v1_inputs_and_decision_rules_unchanged"] is True,
        "certification v2 changed more than the preregistered negative input",
    )
    try:
        validate_strength_authorization(prereg)
    except ContractError:
        prereg_strength_refusal = True
    else:
        raise ContractError("strength authorization validator accepted the certification preregistration")

    require(network.stat().st_size == EXPECTED_NETWORK_BYTES, "legacy network byte size drift")
    require(book.stat().st_size == EXPECTED_BOOK_BYTES, "opening suite byte size drift")
    identities = {
        "book_sha256": assert_exact_hash(book, EXPECTED_BOOK_SHA256, "external opening suite"),
        "candidate_build_manifest_sha256": assert_exact_hash(build_manifest_path, args.expected_build_manifest_sha256.lower(), "candidate build manifest"),
        "comparator_binary_sha256": assert_exact_hash(comparator, EXPECTED_FSF_BINARY_SHA256, "Fairy-Stockfish comparator"),
        "network_sha256": assert_exact_hash(network, EXPECTED_NETWORK_SHA256, "external legacy network"),
        "preregistration_sha256": prereg_sha,
        "python_executable_sha256": python_sha,
        "referee_cli_sha256": assert_exact_hash(cli, EXPECTED_REFEREE_CLI_SHA256, "AC_REFEREE_V1 CLI"),
        "referee_probe_sha256": assert_exact_hash(probe, EXPECTED_REFEREE_PROBE_SHA256, "AC_REFEREE_V1 probe"),
        "qt_core_sha256": assert_exact_hash(qt_bin / "Qt6Core.dll", EXPECTED_QT_CORE_SHA256, "Qt6Core runtime"),
        "v2_addendum_sha256": v2_addendum_sha256,
    }
    build_manifest = verify_build_manifest(
        build_manifest_path,
        args.expected_build_manifest_sha256.lower(),
        candidate,
    )
    identities["candidate_binary_sha256"] = build_manifest["selected_binary_sha256"]
    implementation_freeze, implementation_freeze_sha256 = verify_implementation_freeze(
        implementation_freeze_path,
        args.expected_implementation_freeze_sha256.lower(),
    )
    identities["implementation_freeze_sha256"] = implementation_freeze_sha256

    require(git(candidate_root, "rev-parse", f"{EXPECTED_CANDIDATE_COMMIT}^{{tree}}") == EXPECTED_CANDIDATE_TREE, "candidate Git tree drift")
    require(is_ancestor(candidate_root, EXPECTED_OFFICIAL_ANCESTOR, EXPECTED_CANDIDATE_COMMIT), "official Stockfish source is not candidate ancestry")
    require(git(fsf_root, "rev-parse", "HEAD") == EXPECTED_FSF_COMMIT, "Fairy-Stockfish source commit drift")
    require(git(fsf_root, "rev-parse", "HEAD^{tree}") == EXPECTED_FSF_TREE, "Fairy-Stockfish source tree drift")
    fsf_known_to_candidate_repository = git_object_exists(candidate_root, EXPECTED_FSF_COMMIT)
    require(
        not fsf_known_to_candidate_repository
        or not is_ancestor(candidate_root, EXPECTED_FSF_COMMIT, EXPECTED_CANDIDATE_COMMIT),
        "Fairy-Stockfish became candidate ancestry",
    )

    write_json_exclusive(
        output_dir / "preflight.json",
        {
            "build_manifest": build_manifest,
            "implementation_freeze": implementation_freeze,
            "v2_addendum": v2_addendum,
            "candidate_commit": EXPECTED_CANDIDATE_COMMIT,
            "candidate_tree": EXPECTED_CANDIDATE_TREE,
            "host": {
                "machine": platform.machine(),
                "node": platform.node(),
                "platform": platform.platform(),
            },
            "identities": identities,
            "preregistration_strength_refusal": prereg_strength_refusal,
            "fairy_stockfish_object_known_to_candidate_repository": fsf_known_to_candidate_repository,
            "profile": PROFILE,
            "referee": REFEREE,
            "started_at": started_at,
        },
    )

    self_test_output = run_checked_subprocess(
        [sys.executable, str(ROOT / "tests/antichess/test_s3_panel_harness_v1.py")],
        output_dir / "harness-self-tests.log",
        timeout=60,
    )
    require("Ran 21 tests" in self_test_output and "OK" in self_test_output, "harness self-test summary drift")

    referee_output = run_checked_subprocess(
        [
            sys.executable,
            str(ROOT / "tools/referee/verify_cutechess_referee.py"),
            "--probe",
            str(probe),
            "--cutechess-root",
            str(cutechess_root),
            "--qt-bin",
            str(qt_bin),
        ],
        output_dir / "referee-verification.log",
        timeout=300,
    )
    require("879 checks" in referee_output, "AC_REFEREE_V1 did not report the frozen 879 checks")

    network_results = {
        "candidate": verify_candidate_network(candidate, network, output_dir),
        "comparator": verify_fsf_network(comparator, network, output_dir),
    }

    focused_cases = gather_focused_cases()
    focused_referee = run_referee_cases(probe, qt_bin, focused_cases, output_dir / "focused-referee.log")
    focused_candidate = run_candidate_legal_sets(candidate, network, focused_cases, output_dir / "focused-candidate.log")
    focused_comparator = run_fsf_legal_sets(comparator, network, focused_cases, output_dir / "focused-fsf.log")
    focused_records, focused_mandatory = compare_legal_sets(
        focused_cases,
        focused_referee,
        focused_candidate,
        focused_comparator,
        require_ongoing=False,
    )
    write_json_exclusive(
        output_dir / "focused-legal-audit.json",
        {"cases": focused_records, "mandatory_capture_positions": focused_mandatory},
    )

    openings, schedule_sha = normalize_epd_book(book.read_bytes())
    require(len(openings) == EXPECTED_BOOK_LINES, "normalized opening count drift")
    schedule_cases = [
        {"id": f"book/{opening.source_index:03d}", "fen": opening.fen, "moves": []}
        for opening in openings
    ]
    book_referee = run_referee_cases(probe, qt_bin, schedule_cases, output_dir / "book-referee.log")
    book_candidate = run_candidate_legal_sets(candidate, network, schedule_cases, output_dir / "book-candidate.log")
    book_comparator = run_fsf_legal_sets(comparator, network, schedule_cases, output_dir / "book-fsf.log")
    book_records, book_mandatory = compare_legal_sets(
        schedule_cases,
        book_referee,
        book_candidate,
        book_comparator,
        require_ongoing=True,
    )
    require(book_mandatory > 0, "opening suite never exercises compulsory capture")
    write_json_exclusive(
        output_dir / "opening-schedule.json",
        {
            "book_sha256": identities["book_sha256"],
            "openings": [opening.as_dict() for opening in openings],
            "schedule_sha256": schedule_sha,
            "seed": "ANTICHESS_S3_FSF_SAME_NET_3TC_V1",
        },
    )
    write_json_exclusive(
        output_dir / "book-legal-audit.json",
        {"cases": book_records, "mandatory_capture_positions": book_mandatory},
    )

    smoke_summary: dict[str, Any] | None = None
    if args.run_plumbing_smoke:
        smoke_dir = output_dir / "plumbing-smoke"
        smoke_authorization_path = output_dir / "plumbing-smoke-authorization.json"
        write_json_exclusive(
            smoke_authorization_path,
            {
                "authorized": True,
                "candidate_binary_sha256": identities["candidate_binary_sha256"],
                "comparator_binary_sha256": identities["comparator_binary_sha256"],
                "evidence_class": "S3_PAIR_PLUMBING_SMOKE_NOT_STRENGTH",
                "games": 2,
                "implementation_freeze_sha256": implementation_freeze_sha256,
                "network_sha256": identities["network_sha256"],
                "output_dir": str(smoke_dir),
                "preregistration_sha256": prereg_sha,
                "profile": PROFILE,
                "qt_core_sha256": identities["qt_core_sha256"],
                "referee": REFEREE,
                "referee_cli_sha256": identities["referee_cli_sha256"],
                "schema": SMOKE_AUTHORIZATION_SCHEMA,
                "strength_games": 0,
            },
        )
        smoke_authorization_sha256 = sha256_file(smoke_authorization_path)
        smoke_output = run_checked_subprocess(
            [
                sys.executable,
                str(ROOT / "tools/strength/run_fsf_pair_smoke_v1.py"),
                "--cli",
                str(cli),
                "--candidate",
                str(candidate),
                "--comparator",
                str(comparator),
                "--net",
                str(network),
                "--qt-bin",
                str(qt_bin),
                "--output-dir",
                str(smoke_dir),
                "--authorization",
                str(smoke_authorization_path),
                "--expected-authorization-sha256",
                smoke_authorization_sha256,
            ],
            output_dir / "plumbing-smoke-runner.log",
            timeout=300,
        )
        audit_output = run_checked_subprocess(
            [
                sys.executable,
                str(ROOT / "tools/strength/audit_fsf_pair_smoke_v1.py"),
                "--pgn",
                str(smoke_dir / "games.pgn"),
                "--launch",
                str(smoke_dir / "launch.json"),
                "--probe",
                str(probe),
                "--qt-bin",
                str(qt_bin),
                "--output",
                str(smoke_dir / "audit.json"),
            ],
            output_dir / "plumbing-smoke-audit.log",
            timeout=300,
        )
        smoke_summary = {
            "audit_output": audit_output.strip(),
            "audit_sha256": sha256_file(smoke_dir / "audit.json"),
            "authorization_sha256": smoke_authorization_sha256,
            "pgn_sha256": sha256_file(smoke_dir / "games.pgn"),
            "raw_log_sha256": sha256_file(smoke_dir / "raw.log"),
            "runner_output": smoke_output.strip(),
        }

    require(args.run_plumbing_smoke and smoke_summary is not None, "certification PASS requires the preregistered plumbing smoke")
    result = {
        "book": {
            "legal_positions": len(book_records),
            "mandatory_capture_positions": book_mandatory,
            "schedule_sha256": schedule_sha,
        },
        "candidate_commit": EXPECTED_CANDIDATE_COMMIT,
        "candidate_tree": EXPECTED_CANDIDATE_TREE,
        "elapsed_seconds": time.monotonic() - started,
        "evidence_class": "S3_INPUT_CERTIFICATION_NOT_STRENGTH",
        "finished_at": utc_now(),
        "focused": {
            "legal_positions": len(focused_records),
            "mandatory_capture_positions": focused_mandatory,
        },
        "identities": identities,
        "network_probes": network_results,
        "plumbing_smoke": smoke_summary,
        "profile": PROFILE,
        "referee": REFEREE,
        "referee_checks": 879,
        "status": "PASS_ADMITS_SEPARATE_S3_STRENGTH_PREREGISTRATION_ONLY",
        "strength_games": 0,
    }
    write_json_exclusive(output_dir / "certification-result.json", result)
    print(
        f"S3 panel-input certification PASS: {len(focused_records)} focused and "
        f"{len(book_records)} book positions, {book_mandatory} book capture positions, "
        f"schedule={schedule_sha}; no strength games"
    )
    return 0


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=ROOT / "tests/antichess/fixtures/s3-fsf-panel-cert-v1-prereg.json")
    parser.add_argument(
        "--v2-addendum",
        type=Path,
        default=ROOT / "tests/antichess/fixtures/s3-fsf-panel-cert-v2-addendum.json",
    )
    parser.add_argument("--candidate-source-root", required=True, type=Path)
    parser.add_argument("--candidate-build-manifest", required=True, type=Path)
    parser.add_argument("--expected-build-manifest-sha256", required=True)
    parser.add_argument("--implementation-freeze", required=True, type=Path)
    parser.add_argument("--expected-implementation-freeze-sha256", required=True)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--fsf-source-root", required=True, type=Path)
    parser.add_argument("--comparator", required=True, type=Path)
    parser.add_argument("--network", required=True, type=Path)
    parser.add_argument("--book", required=True, type=Path)
    parser.add_argument("--referee-probe", required=True, type=Path)
    parser.add_argument("--cutechess-root", required=True, type=Path)
    parser.add_argument("--cutechess-cli", required=True, type=Path)
    parser.add_argument("--qt-bin", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-plumbing-smoke", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    try:
        return run_certification(args)
    except Exception as error:
        output_dir = args.output_dir.resolve()
        if output_dir.is_dir() and not (output_dir / "certification-failure.json").exists():
            write_json_exclusive(
                output_dir / "certification-failure.json",
                {
                    "error": str(error),
                    "evidence_class": "S3_INPUT_CERTIFICATION_FAILURE_NOT_STRENGTH",
                    "failed_at": utc_now(),
                    "status": "CERTIFICATION_FAIL_CLOSED_NO_STRENGTH_PANEL",
                },
            )
        print(f"s3-panel-certification-error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
