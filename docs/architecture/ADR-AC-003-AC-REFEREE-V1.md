# ADR-AC-003: AC_REFEREE_V1

- Status: accepted for local correctness and match-service certification
- Date: 2026-08-29
- Rules profile: `LICHESS_ANTICHESS_V1`
- Candidate source base: official Stockfish development commit
  `8bc5caa2e4b1d4c189b1428e93158b10d3edb0b6`

## Decision

Local Antichess games use `AC_REFEREE_V1`, a hash-pinned patch over an exact
Cute Chess source revision. The referee is independent of the candidate engine
and is derived from the frozen scalachess rule and service contract. It is not
derived from Fairy-Stockfish.

The unmodified Cute Chess `antichess` board is rejected for this profile. Its
name and compulsory-capture move generator are insufficient evidence because
the unmodified implementation:

- makes threefold repetition an automatic board result instead of separating a
  claimable third occurrence from automatic fivefold repetition;
- inherits orthodox `WesternBoard::winPossible()` behavior at timeout and
  service-result boundaries;
- omits the profile's opposite-bishop, blocked-pawn, and one-knight-each
  insufficient-material rules;
- does not preserve the exact accept-and-strip FEN castling-rights boundary; and
- omits scalachess's terminal-winner `#` marker from Antichess SAN.

## Immutable source and patch identity

- Repository: `https://github.com/cutechess/cutechess.git`
- Base commit: `5e84232be4546aaedc9d87a96c91867a1da06ada`
- Base tree: `d0912f7c5355837bec16a9c57dc5da29ce42765d`
- Base commit date: 2026-07-14
- Patch:
  `tools/referee/patches/cutechess-5e84232-lichess-antichess-v1.patch`
- Patch bytes: `13,741`
- Patch SHA-256:
  `b8d20a4aa6c4a4a287772cec08b7e952feca88be9120ce11c45a7a3ccfa2a972`
- Derived tree: `639664d19717604326fa5fef21356556db86e27b`

The verifier reconstructs the derived tree through a temporary Git index,
checks every patched source blob, and then checks the probe behavior. A similar
variant name, an unpinned Cute Chess build, or a patch that merely applies is
not `AC_REFEREE_V1`.

## Board and service boundaries

The patched board enforces compulsory capture, unrestricted choice among all
legal captures, non-royal and capturable kings, no check, no castling, en
passant, and promotion to bishop, knight, rook, queen, or king. Syntactically
valid castling-rights text is accepted at the FEN input boundary and stripped
from the canonical state.

Board result precedence is:

1. the side to move wins when it has no piece or no legal move;
2. exact Antichess insufficient material is an automatic draw;
3. a halfmove clock of 100 is an automatic draw; and
4. a fifth occurrence is an automatic repetition draw.

The match service immediately and result-blindly claims a draw at the third
occurrence. This policy is intentionally outside the board result so the
claimable and automatic states remain independently testable.

For timeout, resignation, disconnect, and cannot-lose claims, `winPossible()`
uses the side-specific one-knight-each color-complex rule and the automatic
material state. Effective en passant is included when determining whether
blocked pawns can still capture.

## Notation and protocol boundary

The referee emits ordinary Antichess UCI coordinates, including the `k`
promotion suffix for promotion to a non-royal king. SAN has no check marker.
It appends `#` only when the resulting Antichess position has a winner, matching
the pinned scalachess dumper. PGN must declare `Variant "Antichess"`; a real
pair smoke and PGN replay audit are required before this ADR can support a P4
pass.

The exact UCI option mapping remains part of the match evidence. The client
must send `setoption name UCI_Variant value antichess`; merely having an
internal board called `antichess` does not prove that a runner activates it.

## Current executable evidence

- Referee probe bytes: `1,215,441`
- Referee probe SHA-256:
  `fd45f1f066ce6ff3017a193d5333ccc95e676f9fc795cdd74722abac7564b109`
- Local CLI bytes: `2,290,682`
- Local CLI SHA-256:
  `62377837474f166edfae5dcc5801b19bdf0ee28c89ac4bc66832d535be73ae9f`
- CLI identity: Cute Chess 1.5.1, Qt 6.11.1, Windows x86-64

The frozen verification covers rules and history states, accepted and rejected
FENs, illegal moves, explicit compulsory-capture context, exact SAN, and
service-result outcomes. Binary hashes are local build evidence, not portable
release artifacts.

## OpenBench and release boundary

`AC_REFEREE_V1` is approved only for the project's local panel and correctness
fixtures. It does not prove that production OpenBench maps the public
`antichess` option to this profile, applies the threefold service policy, or
uses this patch. Official OpenBench remains fail-closed until its exact runner,
client, and referee mapping are inspected and certified.
