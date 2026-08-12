# ADR-AC-001: Lichess Antichess terminal classification

Status: accepted for implementation on 2026-08-12.

## Context

Fairy-Stockfish currently combines board-terminal variant rules, optional
draws, and search-cycle handling. That composition cannot represent the pinned
Lichess Antichess contract safely: losing every piece or having no legal move
is decisive, 100 halfmoves and the fifth occurrence are automatic draws, the
third occurrence is only claimable, and Antichess has separate automatic and
color-specific insufficient-material predicates.

The executable authority is scalachess at
`cbffc9d7e2c6f8ba33381c5403e1b4f992199626`, with lila at
`13895e5856db0f854f6ab76394fffce852ebd5c9` for service and presentation
semantics.

## Decision

The built-in `antichess` mapping will carry an explicit immutable
`LICHESS_ANTICHESS_V1` rule-profile identity. `giveaway`, `suicide`, `losers`,
and variants derived through `variants.ini` will not inherit that identity.

The engine will keep four distinct concepts:

1. board-terminal variant outcomes, which are the only terminal predicates
   legal move generation may inspect;
2. automatic draw facts: the Antichess insufficient-position predicate, 100
   halfmoves, and fifth repetition;
3. claimable draw facts, currently third repetition;
4. color-specific cannot-win facts, used only by timeout, resignation,
   disconnect, and cannot-lose adjudication.

Final classification receives an already-known legal-move state and never
generates moves. It resolves in this order:

1. loss-of-all-pieces or no-legal-move Antichess win;
2. automatic Antichess insufficient-position draw;
3. automatic 100-halfmove draw;
4. automatic fifth-repetition draw;
5. claimed third-repetition draw;
6. ongoing.

This matches scalachess `Position.status`, which evaluates `variantEnd` before
`autoDraw`. When automatic draw facts overlap, the public reason follows lila:
insufficient material, then 50 moves, then repetition. Internal records retain
the exact trigger set so a fifth occurrence is not mislabeled as merely a
claim.

The opposite-complex bishop rule remains a separate automatic-position
predicate. It includes the pinned blocked-pawn conditions. It does not make the
legacy player/opponent cannot-win predicates true. The exactly-one-knight-each
parity rule is color-specific and does not end a playable game.

Search may treat an available third-repetition claim as a virtual draw option,
but must continue looking for a win and must not store a history-dependent
claim as an exact transposition-table result. Protocol and referee APIs expose
claimable and automatic outcomes separately.

Bindings will add an explicit automatic-outcome API. Existing
`is_immediate_game_end` keeps its move-generation-safe board-terminal meaning;
tests will migrate to the explicit API instead of creating a compatibility
alias with misleading semantics.

## Consequences

- Automatic outcomes never suppress perft or legal-move enumeration.
- The exact profile is not inferred from `mustCapture`, NNUE aliases, or a
  shared variant template.
- Other Fairy-Stockfish variants retain their current terminal and insufficient
  material behavior.
- The independent referee must consume the same ordered classification before
  P4 can pass.
