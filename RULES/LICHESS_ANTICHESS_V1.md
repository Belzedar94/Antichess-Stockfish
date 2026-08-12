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
- orthodox checkmating-material rules do not apply, but the pinned Antichess
  implementation has its own forced-impossibility draw and one-sided
  cannot-win classifiers, described below.

### Antichess-specific insufficient material

An automatic draw is declared when the board contains only bishops and pawns,
each side's bishops occupy a single square colour, the two sides' bishops are
on opposite square colours, and every remaining pawn is both blocked by a pawn
and unable to interact with the opposite bishop colour under the pinned
implementation.

Separate one-sided classifiers are used when a player flags, disconnects,
resigns, or claims that the opponent cannot win. The pinned implementation has
turn- and square-colour-dependent cases for exactly one knight per side. These
classifiers do not by themselves replace the automatic-draw predicate. Their
exact player/opponent perspective and clock result must be fixture-tested.

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

The project input boundary is deliberately fail-closed:

- a syntactically valid FEN containing castling-right text is accepted, but
  the rights are ignored and canonical output contains `-`;
- a syntactically valid, effective en-passant square is accepted and retained;
- a syntactically valid but ineffective en-passant square is accepted and
  canonicalized to `-`;
- a malformed en-passant token, including `z9`, is rejected before it reaches
  the rules implementation.

The last rule is stricter than the pinned low-level scalachess `FullFen`
wrapper, which assumes already-validated text and can treat a malformed token
as an absent en-passant square. It does not change legal play for any valid
FEN. The independent parser rejects the malformed token, and every public
Antichess-Stockfish entry point must do the same. See `INC-DIALECT-002`.

A threefold claim is available only for the current position after the move
that creates the third occurrence; this profile does not add a claim by an
announced future move. Lichess may immediately submit that claim for a bot or
for a player whose auto-claim preference applies. The deterministic match
runner claim policy and result-reason encoding remain **OPEN-P3** and must be
versioned as part of the referee contract.

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
14. Antichess-specific automatic insufficient-material positives and
    near-negative cases;
15. one-sided cannot-win cases combined with flag, disconnect, resignation,
    and draw-claim results;
16. positions invalid only under orthodox king-safety rules;
17. rejection or explicit separation of `suicide`, `giveaway`, and `losers`.

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
