# Incident ledger

## INC-DIALECT-001 — Hidden Antichess insufficient-material rules

- **Symptom:** the public variant page documented the main win conditions but
  did not expose the executable implementation's Antichess-specific automatic
  draw and one-sided cannot-win classifiers.
- **False inference:** no insufficient-material rule applied because orthodox
  mating material is irrelevant when the king is non-royal.
- **Cause:** discovery initially stopped at public prose and headline terminal
  rules instead of tracing the pinned `autoDraw`, `isInsufficientMaterial`,
  `playerHasInsufficientMaterial`, and `opponentHasInsufficientMaterial` paths
  through scalachess and lila clock/disconnection handling.
- **Prevention:** every terminal predicate and every external result path must
  be enumerated from the pinned executable authority, with positive and
  near-negative fixtures. Public prose is discovery evidence, not a complete
  executable contract.
- **Gate:** P2 remains open; P4 must include automatic-draw and flag/disconnect
  perspective fixtures. Any baseline omitting them is invalid.

## INC-DIALECT-002 - Malformed en-passant text crosses a permissive wrapper

- **Symptom:** the pinned low-level scalachess FEN reader accepted `z9` in the
  en-passant field and canonicalized it to `-`, while the independent chessops
  parser rejected the same input.
- **False inference:** every string accepted by `Fen.read` is valid FEN and is
  therefore part of the Lichess Antichess position contract.
- **Cause:** scalachess `FullFen` is an opaque string wrapper, not a validating
  constructor. `FullFen.parts` uses `Square.fromKey` and represents an invalid
  token as no square; lila entry points also pass cleaned strings through this
  permissive layer.
- **Prevention:** separate valid-position semantics from transport syntax.
  Antichess-Stockfish accepts and normalizes valid but ineffective EP fields,
  while every project-owned input boundary rejects malformed EP tokens before
  rules execution. The negative fixture is mandatory for candidate, referee,
  dataset decoder, and model container tooling.
- **Gate:** P2 parser policy is closed. P3/P4 remain blocked until the public
  engine and referee demonstrate fail-closed rejection with the same fixture.

## INC-BASELINE-001 - Variant-name and legal-move conformance masked terminal drift

- **Symptom:** the upstream-derived candidate exposed an exact `antichess` UCI
  option and matched every frozen legal-move set, yet failed seven of 211
  candidate checks.
- **False inference:** a matching variant name, mandatory-capture perft, and
  ordinary search smoke establish a valid Lichess Antichess baseline.
- **Cause:** generic engine paths classified 50-move and repetition outcomes as
  claimable rather than automatic, omitted the pinned Antichess-specific
  automatic and one-sided insufficient-material predicates, and accepted an
  out-of-board en-passant token.
- **Prevention:** freeze full terminal, history, material-perspective, and parser
  fixtures before source changes; run them through both the UCI binary and the
  exact-source binding; preserve the failing receipt before repair.
- **Gate:** P4 is `FAIL_CURRENT_CANDIDATE` and the project state is
  `NO_VALID_BASELINE` until all seven discrepancies close without regression.
