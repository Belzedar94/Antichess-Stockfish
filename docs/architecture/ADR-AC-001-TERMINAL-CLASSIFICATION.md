# ADR-AC-001: Lichess Antichess terminal classification

Status: accepted for implementation on the official Stockfish source line.

## Context

Official Stockfish assumes orthodox royal kings, check-based legality,
checkmate/stalemate terminals, orthodox draw handling, and a board-oriented
transposition key. Those assumptions cannot directly represent the pinned
Lichess Antichess profile.

The executable rules authority is scalachess at
`cbffc9d7e2c6f8ba33381c5403e1b4f992199626`, with lila at
`13895e5856db0f854f6ab76394fffce852ebd5c9` for service and presentation
semantics.

## Decision

The built-in `antichess` mapping carries the immutable
`LICHESS_ANTICHESS_V1` identity. `giveaway`, `suicide`, and `losers` are not
aliases.

The engine keeps four distinct concepts:

1. board-terminal variant outcomes;
2. automatic draw facts: Antichess insufficient position, 100 halfmoves, and
   fifth repetition;
3. claimable draw facts, currently third repetition;
4. color-specific cannot-win facts used by external service adjudication.

Final classification receives an already-known legal-move state and never
generates moves. It resolves in this order:

1. no pieces or no legal move: the side to move wins;
2. automatic Antichess insufficient-position draw;
3. automatic 100-halfmove draw;
4. automatic fifth-repetition draw;
5. claimed third-repetition draw;
6. ongoing.

When several automatic draw facts overlap, the public reason follows lila:
insufficient material, then 50 moves, then repetition. Internal records retain
the complete trigger set.

Search may treat an available third-repetition claim as a virtual draw option,
but it must continue looking for a win. A history-dependent claim may not be
stored as an exact transposition-table value under a board-only key. Until a
verified repetition-context key exists, the exact profile suppresses TT value
reads and writes throughout a reversible segment.

King promotions use an explicit move encoding; they must not masquerade as
castling. Castling is disabled by profile policy. The parser is transactional
and supports zero, one, or multiple kings of either color without invoking
orthodox king-safety checks.

The initial correctness evaluator is network-independent and deliberately
separate from the official chess NNUE. A legacy compatibility backend may be
added only after its bytes, container, features, perspective, value domain,
and license are proven. Loader failure must never fall back silently.

## Consequences

- Automatic outcomes never suppress perft or legal-move enumeration.
- Mandatory captures are generated in two stages; quiet moves are generated
  only when no capture exists.
- Null move, mate-distance assumptions, SEE, Syzygy, orthodox WDL, king safety,
  and pruning are quarantined until separately audited.
- The independent match referee must consume the same ordered classification
  before P4 can pass.
- Official Stockfish ancestry and build health do not establish a valid
  Antichess baseline.
