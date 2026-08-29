#!/usr/bin/env python3
"""Verify the local-only legacy-v1 loader, including fail-closed mutations."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "antichess" / "fixtures" / "legacy-evaluator-v1.json"
EXPECTED_NET_BYTES = 953_248
EXPECTED_NET_SHA256 = "dd3cbe53cd4e1ca5b7f41cf090873ebe732d84d27f9ed7b14c62ff7a633712cc"
EXPECTED_DESCRIPTION_BYTES = 80
PREFIX = "antichess-info "


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run(engine: Path, commands: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(engine)],
        input="\n".join([*commands, "quit", ""]),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def probe_commands(network: Path) -> list[str]:
    return [
        "uci",
        f"setoption name EvalFile value {network}",
        "setoption name Antichess_Evaluator value legacy-v1",
        "isready",
        "position startpos",
        "antichess-info",
        "eval",
        "go depth 1",
    ]


def diagnostic(output: str) -> dict[str, str]:
    lines = [line for line in output.splitlines() if line.startswith(PREFIX)]
    require(len(lines) == 1, f"expected one Antichess diagnostic, got {len(lines)}")
    fields: dict[str, str] = {}
    for item in lines[0][len(PREFIX) :].split("|"):
        key, separator, value = item.partition("=")
        require(bool(separator), f"malformed diagnostic field: {item!r}")
        fields[key] = value
    return fields


def mutate_u32(data: bytes, offset: int, value: int) -> bytes:
    mutable = bytearray(data)
    mutable[offset : offset + 4] = struct.pack("<I", value)
    return bytes(mutable)


def mutations(data: bytes) -> dict[str, tuple[bytes, str]]:
    description_size = struct.unpack_from("<I", data, 8)[0]
    transformer_hash_offset = 12 + description_size
    first_layer_hash_offset = (
        transformer_hash_offset
        + 4
        + 512 * 2
        + 768 * 512 * 2
        + 768 * 8 * 4
    )
    return {
        "bad-version": (
            mutate_u32(data, 0, 0),
            "Unsupported Antichess legacy network version",
        ),
        "bad-architecture": (
            mutate_u32(data, 4, 0),
            "Incompatible Antichess legacy network architecture",
        ),
        "oversize-description": (
            mutate_u32(data, 8, 4097),
            "Invalid Antichess legacy network framing",
        ),
        "bad-transformer": (
            mutate_u32(data, transformer_hash_offset, 0),
            "Incompatible Antichess legacy feature transformer",
        ),
        "bad-layer-stack": (
            mutate_u32(data, first_layer_hash_offset, 0),
            "Incompatible Antichess legacy layer stack",
        ),
        "truncated": (
            data[:-1],
            "Invalid Antichess legacy network framing",
        ),
        "appended-byte": (
            data + b"\x00",
            "Invalid Antichess legacy network framing",
        ),
    }


def verify_positive(engine: Path, network: Path) -> int:
    completed = run(engine, probe_commands(network))
    require(completed.returncode == 0, f"positive probe exited {completed.returncode}")
    fields = diagnostic(completed.stdout)
    require(fields["evaluator"] == "legacy-v1", "legacy evaluator option did not persist")
    require(fields["network_loaded"] == "1", "valid legacy network was not loaded")
    require(fields["network_format"] == "legacy-v1", "valid legacy format was not exposed")
    require(fields["network_file"] == network.name, "loaded network filename drift")
    require(
        fields["network_description_bytes"] == str(EXPECTED_DESCRIPTION_BYTES),
        "legacy description size drift",
    )
    require(
        "info string Antichess legacy-v1 raw value 5" in completed.stdout,
        "start-position legacy value drift",
    )
    bestmoves = re.findall(r"^bestmove (\S+)$", completed.stdout, flags=re.MULTILINE)
    require(len(bestmoves) == 1 and bestmoves[0] != "(none)", "valid network search was refused")
    return 7


def verify_claim_horizon(
    engine: Path, network: Path, fixture: dict[str, object]
) -> int:
    history = [str(move) for move in fixture["history_before_search"]]
    searchmoves = [str(move) for move in fixture["searchmoves"]]
    initial_fen = str(fixture["initial_fen"])
    expected = fixture["expected"]
    require(isinstance(expected, dict), f"{fixture['id']}: malformed expected result")

    position = f"position fen {initial_fen} moves {' '.join(history)}"
    child_position = f"{position} {' '.join(searchmoves)}"
    completed = run(
        engine,
        [
            "uci",
            f"setoption name EvalFile value {network}",
            "setoption name Antichess_Evaluator value legacy-v1",
            "isready",
            position,
            f"go depth {fixture['depth']} searchmoves {' '.join(searchmoves)}",
            child_position,
            "eval",
        ],
    )
    require(completed.returncode == 0, f"{fixture['id']}: claim-horizon probe failed")
    match = re.search(
        r"^info depth \d+ .* score (mate|cp) (-?\d+) .* pv (\S+)$",
        completed.stdout,
        flags=re.MULTILINE,
    )
    require(match is not None, f"{fixture['id']}: missing search result")
    require(match.group(1) == expected["score_type"], f"{fixture['id']}: score type drift")
    require(int(match.group(2)) == expected["score"], f"{fixture['id']}: claim floor drift")
    require(match.group(3) == expected["bestmove"], f"{fixture['id']}: PV drift")
    require(
        re.findall(r"^bestmove (\S+)$", completed.stdout, flags=re.MULTILINE)
        == [expected["bestmove"]],
        f"{fixture['id']}: bestmove drift",
    )
    require(
        f"info string Antichess legacy-v1 raw value {fixture['expected_child_raw']}"
        in completed.stdout,
        f"{fixture['id']}: child legacy value drift",
    )
    return 5


def verify_rejection(engine: Path, network: Path, expected_error: str, case_id: str) -> int:
    completed = run(engine, probe_commands(network))
    require(completed.returncode == 0, f"{case_id}: engine exited {completed.returncode}")
    fields = diagnostic(completed.stdout)
    require(expected_error in completed.stdout, f"{case_id}: expected loader error was absent")
    require(fields["evaluator"] == "legacy-v1", f"{case_id}: evaluator option drift")
    require(fields["network_loaded"] == "0", f"{case_id}: corrupt network remained loaded")
    require(fields["network_format"] == "none", f"{case_id}: corrupt format was exposed")
    require(fields["network_file"] == "none", f"{case_id}: corrupt filename was exposed")
    require(fields["network_description_bytes"] == "0", f"{case_id}: corrupt description leaked")
    require(
        "info string Antichess legacy-v1 evaluator is not ready" in completed.stdout,
        f"{case_id}: eval did not fail closed",
    )
    require(
        "info string Antichess legacy-v1 evaluator is not ready; search refused"
        in completed.stdout,
        f"{case_id}: search refusal was absent",
    )
    bestmoves = re.findall(r"^bestmove (\S+)$", completed.stdout, flags=re.MULTILINE)
    require(bestmoves == ["(none)"], f"{case_id}: corrupt network produced {bestmoves!r}")
    return 9


def verify_transactional_clear(engine: Path, valid: Path, invalid: Path, expected_error: str) -> int:
    completed = run(
        engine,
        [
            f"setoption name EvalFile value {valid}",
            "setoption name Antichess_Evaluator value legacy-v1",
            "isready",
            f"setoption name EvalFile value {invalid}",
            "isready",
            "position startpos",
            "antichess-info",
            "eval",
            "go depth 1",
        ],
    )
    require(completed.returncode == 0, "transactional-clear probe failed")
    require(
        "info string Antichess evaluator: legacy-v1 network loaded" in completed.stdout,
        "transactional-clear probe never loaded the valid network",
    )
    require(expected_error in completed.stdout, "transactional-clear loader error was absent")
    fields = diagnostic(completed.stdout)
    require(fields["network_loaded"] == "0", "failed reload retained the prior network")
    require(fields["network_format"] == "none", "failed reload retained the prior format")
    require(fields["network_file"] == "none", "failed reload retained the prior filename")
    require(
        re.findall(r"^bestmove (\S+)$", completed.stdout, flags=re.MULTILINE) == ["(none)"],
        "failed reload still searched with the prior network",
    )
    return 7


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", required=True, type=Path)
    parser.add_argument("--network", required=True, type=Path)
    args = parser.parse_args()

    engine = args.engine.resolve()
    network = args.network.resolve()
    require(engine.is_file(), f"engine not found: {engine}")
    require(network.is_file(), f"network not found: {network}")

    network_bytes = network.read_bytes()
    require(len(network_bytes) == EXPECTED_NET_BYTES, "legacy network size mismatch")
    require(
        hashlib.sha256(network_bytes).hexdigest() == EXPECTED_NET_SHA256,
        "legacy network SHA-256 mismatch",
    )

    fixture_document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    check_count = verify_positive(engine, network)
    for fixture in fixture_document["claim_horizon_cases"]:
        check_count += verify_claim_horizon(engine, network, fixture)
    mutation_cases = mutations(network_bytes)
    with tempfile.TemporaryDirectory(prefix="antichess-legacy-loader-") as temporary:
        temporary_path = Path(temporary)
        written: dict[str, tuple[Path, str]] = {}
        for case_id, (payload, expected_error) in mutation_cases.items():
            path = temporary_path / f"{case_id}.nnue"
            path.write_bytes(payload)
            written[case_id] = (path, expected_error)
            check_count += verify_rejection(engine, path, expected_error, case_id)

        invalid_path, expected_error = written["bad-version"]
        check_count += verify_transactional_clear(engine, network, invalid_path, expected_error)

    print(
        "legacy-v1 loader verification passed: "
        f"1 positive, {len(fixture_document['claim_horizon_cases'])} claim-horizon, "
        f"{len(mutation_cases)} rejected mutations, 1 transactional clear, "
        f"{check_count} checks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
