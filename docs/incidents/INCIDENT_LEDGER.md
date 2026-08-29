# Incident ledger

## INC-DIALECT-001 — Hidden Antichess insufficient-material rules

- **Symptom:** the public variant page documented the headline win conditions
  but not the executable implementation's automatic draw and one-sided
  cannot-win classifiers.
- **False inference:** no insufficient-material rule applied because orthodox
  mating material is irrelevant when the king is non-royal.
- **Cause:** discovery initially stopped at public prose instead of tracing
  `autoDraw`, `isInsufficientMaterial`, and the service result paths.
- **Prevention:** enumerate every terminal and service-result predicate from a
  pinned executable authority and require positive and near-negative fixtures.
- **Gate:** P2 and P4.

## INC-DIALECT-002 — Malformed en-passant text crossed a permissive wrapper

- **Symptom:** a low-level scalachess wrapper canonicalized `z9` to no
  en-passant square while chessops rejected it.
- **False inference:** every string accepted by the wrapper was valid public
  FEN.
- **Cause:** the wrapper assumed prevalidated transport text.
- **Prevention:** every project-owned boundary rejects malformed tokens before
  rules execution; valid but ineffective en-passant fields canonicalize to
  `-`.
- **Gate:** P2, P3, P4, P8, and P12.

## INC-BASELINE-001 — Legal-move conformance masked terminal drift

- **Symptom:** a historical candidate matched mandatory-capture legal sets but
  disagreed on repetition, move-count, material, and parser outcomes.
- **False inference:** a matching name, perft, and ordinary search smoke proved
  the exact Lichess profile.
- **Cause:** terminal, history, service, and parser semantics were not yet part
  of the baseline manifest.
- **Prevention:** freeze full legal, terminal, history, material-perspective,
  notation, and parser fixtures before implementation.
- **Gate:** P2 through P6.

## INC-SOURCE-001 — An unapproved source base advanced through correctness work

- **Symptom:** substantial work was performed on a Fairy-Stockfish-derived
  branch before the source-base decision had an explicit owner go.
- **False inference:** dialect fidelity and legacy-loader affinity were enough
  to select a production source base.
- **Cause:** source selection was treated as an engineering ranking instead of
  an owner-controlled scope decision.
- **Prevention:** P0 requires an immutable owner decision. A source-base no-go
  archives the lineage and allows only a hashed contract allowlist to cross.
- **Gate:** P0; the old lineage is `REJECTED_ENGINEERING`.

## INC-ORACLE-001 — Browser review slot timeout was not a review verdict

- **Symptom:** the first browser-only Pro review attempt exhausted its slot
  before producing a model response.
- **False inference:** the architecture was rejected or the review requirement
  was satisfied by the failed session.
- **Cause:** browser session availability, not model analysis or repository
  content.
- **Prevention:** preserve the failed session classification, retry once with a
  minimal non-secret bundle, verify requested/resolved model identity, and
  hash the completed transcript. Continue locally when review infrastructure
  remains unavailable, as owner-authorized.
- **Gate:** architecture decisions before P3, P8, P12, P15.
