#!/usr/bin/env python3
"""Fail-closed primitives for the Antichess same-network S3 panel."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PROFILE = "LICHESS_ANTICHESS_V1"
REFEREE = "AC_REFEREE_V1"
CERT_PREREG_SCHEMA = "ANTICHESS_S3_FSF_PANEL_CERT_V1_PREREG"
STRENGTH_AUTH_SCHEMA = "ANTICHESS_S3_FSF_SAME_NET_3TC_V1_AUTHORIZATION"
SCHEDULE_SEED = "ANTICHESS_S3_FSF_SAME_NET_3TC_V1"
EXPECTED_BOOK_LINES = 202
EXPECTED_PREREG_SHA256 = (
    "0aa9229ba4eb7c5ed0fc851774848ea6642856666c76e0947e36f0db72aab9ee"
)
EXPECTED_NETWORK_SHA256 = (
    "dd3cbe53cd4e1ca5b7f41cf090873ebe732d84d27f9ed7b14c62ff7a633712cc"
)
EXPECTED_BOOK_SHA256 = (
    "6ec92e4e39a86f8d74504f7556fb27c02fe50fb2cac04951eb5ec01c8f1c2ec2"
)
EXPECTED_CANDIDATE_COMMIT = "d08da0c88b7b933eb3c94e6c10a91e0a04f9f769"
EXPECTED_CANDIDATE_TREE = "31fbae40bd620737a44ee336f8f8596649c027f9"
EXPECTED_OFFICIAL_ANCESTOR = "8bc5caa2e4b1d4c189b1428e93158b10d3edb0b6"
EXPECTED_FSF_COMMIT = "6d9d0f5724677dc3aba3c577b0b482b6ec11e44a"
EXPECTED_FSF_TREE = "aa4112ea6784cef03fb9b5f87bba632de6168faa"
EXPECTED_FSF_BINARY_SHA256 = (
    "ee0081d77a555ef073e56a04fff604af8d6408a1e2d0afc2e61cea23c11bb902"
)
EXPECTED_REFEREE_PROBE_SHA256 = (
    "fd45f1f066ce6ff3017a193d5333ccc95e676f9fc795cdd74722abac7564b109"
)
EXPECTED_REFEREE_CLI_SHA256 = (
    "62377837474f166edfae5dcc5801b19bdf0ee28c89ac4bc66832d535be73ae9f"
)
EXPECTED_QT_CORE_SHA256 = (
    "9cf7924077f1ac8758a456e780d9f408c779e76e58680a77ef30ef9807295c43"
)
TIME_CONTROLS_MS = {
    "VSTC": (2000, 20),
    "STC": (10000, 100),
    "LTC": (30000, 300),
}
UCI_MOVE_RE = re.compile(r"^[a-h][1-8][a-h][1-8][nbrqk]?$")
PERFT_MOVE_RE = re.compile(r"^([a-h][1-8][a-h][1-8][nbrqk]?):\s*(\d+)\s*$")
PERFT_TOTAL_RE = re.compile(r"^Nodes searched\s*:\s*(\d+)\s*$")
FORBIDDEN_LOG_PATTERNS = {
    "crash": re.compile(r"\bcrash(?:ed)?\b", re.IGNORECASE),
    "disconnect": re.compile(r"\bdisconnect(?:ed)?\b", re.IGNORECASE),
    "illegal_move": re.compile(r"\billegal move\b", re.IGNORECASE),
    "stall": re.compile(r"\bstall(?:ed)?\b", re.IGNORECASE),
    "time_loss": re.compile(
        r"\blost on time\b|\bloses on time\b|\bforfeit(?:ed|s)? on time\b|"
        r"\btime forfeit\b|\btime loss\b",
        re.IGNORECASE,
    ),
    "controller_timeout": re.compile(r"\bcontroller timeout\b", re.IGNORECASE),
}


class ContractError(RuntimeError):
    """Raised whenever frozen S3 evidence is incomplete or inconsistent."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON object required: {path}")
    return value


def write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as destination:
        destination.write(canonical_json_bytes(value))


@dataclass(frozen=True)
class Opening:
    source_index: int
    source_epd: str
    fen: str
    schedule_key: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_index": self.source_index,
            "source_epd": self.source_epd,
            "fen": self.fen,
            "schedule_key": self.schedule_key,
        }


@dataclass(frozen=True)
class WldStatistics:
    wins: int
    losses: int
    draws: int
    total: int
    elo: float | None
    elo95: float | None
    los: float | None
    displayed_los: str | None


def normalize_epd_book(
    data: bytes,
    *,
    expected_lines: int = EXPECTED_BOOK_LINES,
    seed: str = SCHEDULE_SEED,
) -> tuple[list[Opening], str]:
    """Validate the exact four-field EPD framing and derive the frozen order."""

    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as error:
        raise ContractError("opening suite is not strict ASCII") from error
    raw_lines = text.splitlines()
    require(len(raw_lines) == expected_lines, f"opening line count {len(raw_lines)} != {expected_lines}")
    require(all(raw_lines), "opening suite contains a blank line")
    require(len(set(raw_lines)) == len(raw_lines), "opening suite contains duplicate source lines")

    normalized: list[str] = []
    for index, line in enumerate(raw_lines, start=1):
        require(line == line.strip(), f"opening {index}: leading or trailing whitespace")
        require("\t" not in line and "  " not in line, f"opening {index}: non-canonical spacing")
        fields = line.split(" ")
        require(len(fields) == 4 and all(fields), f"opening {index}: expected exactly four EPD fields")
        normalized.append(line + " 0 1")
    require(
        len(set(normalized)) == len(normalized),
        "opening suite contains duplicates after six-field normalization",
    )

    openings = []
    for index, (epd, fen) in enumerate(zip(raw_lines, normalized, strict=True), start=1):
        key = hashlib.sha256(f"{seed}\n{index}\n{fen}".encode("ascii")).hexdigest()
        openings.append(Opening(index, epd, fen, key))
    openings.sort(key=lambda opening: (opening.schedule_key, opening.source_index))
    schedule_sha256 = sha256_bytes(canonical_json_bytes([opening.as_dict() for opening in openings]))
    return openings, schedule_sha256


def parse_pipe_diagnostic(output: str, prefix: str) -> dict[str, str]:
    lines = [line for line in output.splitlines() if line.startswith(prefix)]
    require(len(lines) == 1, f"expected one {prefix.strip()} diagnostic, got {len(lines)}")
    fields: dict[str, str] = {}
    for item in lines[0][len(prefix) :].split("|"):
        key, separator, value = item.partition("=")
        require(bool(separator) and bool(key), f"malformed diagnostic field: {item!r}")
        require(key not in fields, f"duplicate diagnostic field: {key}")
        fields[key] = value
    return fields


def parse_candidate_diagnostics(output: str, expected_count: int) -> list[dict[str, str]]:
    prefix = "antichess-info "
    lines = [line for line in output.splitlines() if line.startswith(prefix)]
    require(len(lines) == expected_count, f"candidate diagnostics {len(lines)} != {expected_count}")
    return [parse_pipe_diagnostic(line, prefix) for line in lines]


def parse_fsf_perft_sections(output: str, expected_count: int) -> list[list[str]]:
    """Extract depth-one root move lists from Fairy-Stockfish perft output."""

    sections: list[list[str]] = []
    current: list[str] = []
    counts: list[int] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        move_match = PERFT_MOVE_RE.fullmatch(line)
        if move_match:
            move, count = move_match.groups()
            require(move not in current, f"duplicate Fairy-Stockfish root move: {move}")
            current.append(move)
            counts.append(int(count))
            continue
        total_match = PERFT_TOTAL_RE.fullmatch(line)
        if total_match:
            total = int(total_match.group(1))
            require(all(count == 1 for count in counts), "depth-one perft child count is not one")
            require(total == len(current), f"perft total {total} != root move count {len(current)}")
            sections.append(sorted(current))
            current, counts = [], []
    require(not current and not counts, "unterminated Fairy-Stockfish perft section")
    require(len(sections) == expected_count, f"Fairy-Stockfish perft sections {len(sections)} != {expected_count}")
    return sections


def legal_moves_from_fields(fields: Mapping[str, str], *, label: str) -> list[str]:
    require("legal" in fields, f"{label}: missing legal field")
    moves = [] if fields["legal"] == "" else fields["legal"].split(",")
    require(len(set(moves)) == len(moves), f"{label}: duplicate legal move")
    require(all(UCI_MOVE_RE.fullmatch(move) for move in moves), f"{label}: malformed UCI legal move")
    return sorted(moves)


def parse_board(fen: str) -> tuple[dict[str, str], str | None]:
    fields = fen.split()
    require(len(fields) == 6, f"expected six-field FEN, got {len(fields)}")
    ranks = fields[0].split("/")
    require(len(ranks) == 8, "FEN board must have eight ranks")
    board: dict[str, str] = {}
    for rank_index, rank_text in enumerate(ranks):
        file_index = 0
        for token in rank_text:
            if token.isdigit():
                require(token != "0", "zero-width FEN run")
                file_index += int(token)
            else:
                require(token in "pnbrqkPNBRQK", f"unsupported FEN piece: {token}")
                require(file_index < 8, "FEN rank overflow")
                square = f"{'abcdefgh'[file_index]}{8 - rank_index}"
                board[square] = token
                file_index += 1
        require(file_index == 8, f"FEN rank width {file_index} != 8")
    require(fields[1] in {"w", "b"}, "invalid side-to-move field")
    ep = None if fields[3] == "-" else fields[3]
    if ep is not None:
        require(re.fullmatch(r"[a-h][36]", ep) is not None, "invalid en-passant field")
    return board, ep


def move_is_capture(fen: str, move: str) -> bool:
    require(UCI_MOVE_RE.fullmatch(move) is not None, f"malformed UCI move: {move}")
    board, ep = parse_board(fen)
    source, target = move[:2], move[2:4]
    piece = board.get(source)
    require(piece is not None, f"move source is empty: {move}")
    target_piece = board.get(target)
    if target_piece is not None:
        require(piece.isupper() != target_piece.isupper(), f"move captures own piece: {move}")
        return True
    return piece.lower() == "p" and source[0] != target[0] and ep == target


def audit_mandatory_capture(
    fen: str,
    legal_moves: Sequence[str],
    *,
    referee_must_capture: bool | None = None,
) -> bool:
    flags = [move_is_capture(fen, move) for move in legal_moves]
    has_capture = any(flags)
    if has_capture:
        require(all(flags), "quiet move survived while a capture was legal")
    if referee_must_capture is not None:
        require(referee_must_capture == has_capture, "referee must-capture marker disagrees with board audit")
    return has_capture


def scan_forbidden_log(text: str) -> dict[str, int]:
    return {name: len(pattern.findall(text)) for name, pattern in FORBIDDEN_LOG_PATTERNS.items()}


def _erf(value: float) -> float:
    coefficient = 8 * (math.pi - 3) / (3 * math.pi * (4 - math.pi))
    value2 = value * value
    exponent = -value2 * (4 / math.pi + coefficient * value2) / (1 + coefficient * value2)
    return math.copysign(math.sqrt(1 - math.exp(exponent)), value)


def _erf_inv(value: float) -> float:
    coefficient = 8 * (math.pi - 3) / (3 * math.pi * (4 - math.pi))
    logarithm = math.log(1 - value * value)
    intermediate = 2 / (math.pi * coefficient) + logarithm / 2
    return math.copysign(
        math.sqrt(math.sqrt(intermediate * intermediate - logarithm / coefficient) - intermediate),
        value,
    )


def _phi(value: float) -> float:
    return 0.5 * (1 + _erf(value / math.sqrt(2)))


def _phi_inv(probability: float) -> float:
    require(0 <= probability <= 1, "normal probability outside [0, 1]")
    return math.sqrt(2) * _erf_inv(2 * probability - 1)


def _elo(probability: float) -> float:
    if probability <= 0:
        return 0.0
    return -400 * math.log10(1 / probability - 1)


def wld_statistics(wins: int, losses: int, draws: int) -> WldStatistics:
    require(all(isinstance(value, int) and value >= 0 for value in (wins, losses, draws)), "WLD counts must be non-negative integers")
    total = wins + losses + draws
    require(total > 0, "WLD total must be positive")
    win_rate = wins / total
    loss_rate = losses / total
    draw_rate = draws / total
    mean = win_rate + draw_rate / 2
    stdev = math.sqrt(
        win_rate * (1 - mean) ** 2
        + loss_rate * mean**2
        + draw_rate * (0.5 - mean) ** 2
    ) / math.sqrt(total)
    if stdev == 0:
        return WldStatistics(wins, losses, draws, total, None, None, None, None)
    mean_min = mean + _phi_inv(0.025) * stdev
    mean_max = mean + _phi_inv(0.975) * stdev
    try:
        elo = _elo(mean)
        elo95 = (_elo(mean_max) - _elo(mean_min)) / 2
    except ValueError:
        # The frozen legacy formatter catches this domain failure and emits no
        # statistic at all.  Preserve that fail-closed behavior.
        return WldStatistics(wins, losses, draws, total, None, None, None, None)
    los = _phi((mean - 0.5) / stdev)
    return WldStatistics(wins, losses, draws, total, elo, elo95, los, "%.1f" % (100 * los))


def validate_completed_pair(
    games: Sequence[Mapping[str, Any]],
    *,
    candidate: str,
    comparator: str,
    opening_fen: str,
    time_control: str,
) -> None:
    require(len(games) == 2, "a completed opening pair must contain exactly two games")
    expected_colors = {(candidate, comparator), (comparator, candidate)}
    actual_colors: set[tuple[str, str]] = set()
    for index, game in enumerate(games, start=1):
        require(game.get("variant") == "Antichess", f"game {index}: Variant tag drift")
        require(game.get("fen") == opening_fen, f"game {index}: opening FEN drift")
        require(game.get("time_control") == time_control, f"game {index}: time control drift")
        require(game.get("result") in {"1-0", "0-1", "1/2-1/2"}, f"game {index}: unfinished result")
        require(game.get("terminal_marker") is True, f"game {index}: missing terminal marker")
        require(not game.get("defects"), f"game {index}: defects are present")
        actual_colors.add((str(game.get("white")), str(game.get("black"))))
    require(actual_colors == expected_colors, "pair is not exactly color-swapped")


def validate_strength_authorization(document: Mapping[str, Any]) -> None:
    """Reject preregistration or incomplete evidence as a strength launch token."""

    require(document.get("schema") == STRENGTH_AUTH_SCHEMA, "wrong strength authorization schema")
    require(document.get("authorized") is True, "strength panel is not explicitly authorized")
    require(document.get("profile") == PROFILE, "authorization profile drift")
    require(document.get("referee") == REFEREE, "authorization referee drift")
    require(document.get("candidate_commit") == EXPECTED_CANDIDATE_COMMIT, "candidate commit drift")
    require(document.get("candidate_tree") == EXPECTED_CANDIDATE_TREE, "candidate tree drift")
    require(document.get("network_sha256") == EXPECTED_NETWORK_SHA256, "network hash drift")
    require(document.get("book_sha256") == EXPECTED_BOOK_SHA256, "book hash drift")
    require(document.get("certification_status") == "PASS", "panel-input certification did not pass")
    for key in (
        "candidate_binary_sha256",
        "comparator_binary_sha256",
        "certification_receipt_sha256",
        "runner_sha256",
        "schedule_sha256",
    ):
        value = document.get(key)
        require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None, f"missing or malformed {key}")
    require(document["comparator_binary_sha256"] == EXPECTED_FSF_BINARY_SHA256, "comparator binary drift")
    require(document.get("time_controls_ms") == {name: list(value) for name, value in TIME_CONTROLS_MS.items()}, "time-control contract drift")
    require(document.get("threads_per_engine") == 1, "Threads contract drift")
    require(document.get("hash_mib_per_engine") == 512, "Hash contract drift")
    require(document.get("games_per_pair") == 2, "pair-size contract drift")
    require(document.get("minimum_games_exclusive") == 100, "minimum game gate drift")
    require(document.get("maximum_games") == 64000, "maximum game gate drift")
    require(document.get("target_displayed_los") == "100.0", "LOS pass gate drift")
    require(document.get("loss_displayed_los") == "0.0", "LOS loss gate drift")


def assert_exact_hash(path: Path, expected: str, label: str) -> str:
    require(path.is_file(), f"{label} not found: {path}")
    actual = sha256_file(path)
    require(actual == expected.lower(), f"{label} SHA-256 {actual} != {expected.lower()}")
    return actual


def complete_legal_set_equal(*move_sets: Iterable[str]) -> bool:
    normalized = [tuple(sorted(moves)) for moves in move_sets]
    return bool(normalized) and all(value == normalized[0] for value in normalized[1:])
