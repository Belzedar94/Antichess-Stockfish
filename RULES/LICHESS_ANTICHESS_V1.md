# LICHESS_ANTICHESS_V1

Status: **selected by the project owner; executable conformance still in P2/P3**.

This document freezes the public rules identity of Antichess-Stockfish. It is
derived from the pinned Lichess/scalachess implementation in
[`AUTHORITY.lock.json`](AUTHORITY.lock.json), not from a generic use of the
word “antichess”. If prose and the pinned primary implementation disagree, the
disagreement blocks the gate and must be resolved in a receipt; it must not be
silently changed to make the candidate pass.

## Public identity

- Profile ID: `LICHESS_ANTICHESS_V1`
- Public name and UCI token: `antichess`
- PGN Variant tag: `Antichess`
- Canonical initial FEN:
  `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1`
- `suicide`, `giveaway`, and `losers` are distinct profiles. They are neither
  accepted aliases nor evidence for this profile.

## Move legality

1. Capturing is compulsory. If the side to move has at least one legal
   capture, every quiet move is suppressed.
2. When several captures exist, all of them remain legal. There is no maximum
   capture rule, capture priority, or forced continuation by the same piece.
3. The king is an ordinary, capturable piece. Check, check evasion,
   checkmate, attacked-square restrictions, and king-facing restrictions do
   not exist.
4. Kingless positions, adjacent kings, and multiple same-colour kings created
   by promotion belong to the supported state space.
5. Castling is unavailable. The canonical initial position has no castling
   rights.
6. En-passant capture exists and participates in compulsory-capture selection.
7. Pawns promote to queen, rook, bishop, knight, or king. Canonical UCI
   promotion suffixes are `q`, `r`, `b`, `n`, and `k`; capture promotions use
   the same suffixes.

## Results and precedence

For the side whose turn it is:

- having no pieces is a variant win;
- having no legal moves is a variant win even when pieces remain;
- neither condition is orthodox stalemate, checkmate, or insufficient
  material.

The result is effective on the transition that creates the terminal state.
Variant termination precedes an automatic repetition or fifty-move draw that
would otherwise become effective on the same position.

The history rules are:

- third occurrence: a draw is claimable, not automatic;
- fifth occurrence: the draw is automatic;
- 100 halfmoves without a pawn move or capture: the fifty-move draw is
  automatic;
- no orthodox insufficient-material draw applies.

Any service-wide maximum game length is an operational platform limit and is
not part of this rules profile unless separately versioned by the referee
contract.

## Position and notation boundary

The following are closed requirements:

- canonical output never advertises castling rights;
- the full halfmove and fullmove counters are preserved in FEN;
- repetition cannot be reconstructed from a lone FEN, so fixtures that test
  repetition include the complete preceding move sequence;
- a directly loaded terminal position must produce the same status as the
  equivalent played transition;
- UCI and PGN round trips must preserve king promotions.

The following parser policies remain **OPEN-P3** until checked against the
pinned authority and all three executable roles:

- whether an input FEN containing non-empty castling rights is rejected or
  accepted and canonicalized to `-`;
- acceptance and canonicalization of malformed or ineffective en-passant
  fields;
- exact claim-on-current-position versus claim-by-announced-move behavior;
- the match runner’s explicit claim action and its result-reason encoding.

No strength work may begin while an OPEN-P3 item remains.

## Repetition identity

Differential fixtures must prove the exact position identity used for third
and fifth occurrence, including:

- board contents and side to move;
- absence of castling state;
- effective versus ineffective en-passant state;
- promoted and multiple kings;
- kingless positions.

## Required fixture families

The frozen suite must compare complete sorted legal-move sets and exact result
states, not only perft counts:

1. compulsory capture and quiet suppression;
2. free choice among multiple captures;
3. king moving into attack, adjacent kings, king capture, and kingless play;
4. multiple kings following king promotion;
5. no castling, including a FEN carrying castling-right text;
6. en passant as one capture and as the only capture;
7. every quiet and capture promotion to `Q/R/B/N/K`;
8. capture of the final opposing piece;
9. no legal moves with pieces remaining;
10. threefold claim availability without automatic termination;
11. fifth-occurrence automatic draw;
12. fifty-move threshold;
13. variant-win versus automatic-draw precedence;
14. positions invalid only under orthodox king-safety rules;
15. rejection or explicit separation of `suicide`, `giveaway`, and `losers`.

## Orthodox-assumption quarantine

Mate scores, SEE, null move, pruning, material, king safety, orthodox WDL,
adjudication, and evaluation-sign assumptions are untrusted until each has its
own fixture-backed audit. They are not disabled or retained in bulk. P2–P6 may
only change correctness plumbing; all strength hypotheses remain gated.

## Future data and model contract

No NNUE or DATAGEN contract is inferred from this rules document. P8+ must
define result labels from a declared side-to-move or trajectory perspective,
prove loss-objective inversion with golden examples, and separately justify
every symmetry or augmentation. Legacy-network loader compatibility supplies
none of that evidence.
