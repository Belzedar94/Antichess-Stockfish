# Gate index

Allowed terminal states are `GO_NEXT_PHASE`, `BLOCKED_DISCOVERY`,
`NO_VALID_BASELINE`, `REJECTED_ENGINEERING`, `REJECTED_MODEL`,
`REJECTED_STRENGTH`, `REJECTED_RELEASE`, and `RELEASED_MONITORED`.

Current project state: **`NO_VALID_BASELINE`**.

This file is a human-readable index. Committed receipts are authoritative and
append-only; a gate transition requires a new receipt or addendum.

| Gate | Scope | Status | Closure evidence |
| --- | --- | --- | --- |
| P0 | Root, owner source-base decision, repository, worktrees, remotes, namespaces, resource boundaries | PASS | Official pin, clean branch transition, rejected-line archive, D0 receipt |
| P1 | Primary research and authority dossier | PASS | Pinned Lichess/scalachess/lila sources, independent chessops pin, negative profiles |
| P2 | Executable dialect, source architecture, reference, referee, evaluator, distribution | PASS | Frozen primary contract, patched `AC_REFEREE_V1`, exact legacy compatibility, and a fail-closed no-redistribution boundary for the unresolved 2024 network license |
| P3 | Candidate clean reproducible build and UCI surface | PASS | Candidate `95e4efec4`: two clean builds are byte-identical, debug `-Werror` passes, and the Antichess-only bench repeats exactly |
| P4 | Differential legal/result/notation correctness | PASS | Candidate, pinned primary, declared-gap independent reference, and `AC_REFEREE_V1` agree; exact-binary clocked pair and 100-ply PGN replay pass |
| P5 | Evaluator and legacy-network boundary | PASS | Scalar full-refresh parity covers 58 exact values and all material buckets; loader fails closed transactionally; unresolved license forbids redistribution/default/alias |
| P6 | Sanitizers, deterministic digest, CI, baseline manifest/tag | IN_PROGRESS | Local digest and build evidence pass; pinned Linux sanitizers, official CI, manifest, and engineering tag remain open |
| P7 | Search-hypothesis readiness | BLOCKED_BY_P6 | One hypothesis per branch and preregistered local experiment |
| P8 | Antichess DATAGEN schema and labels | BLOCKED_BY_P7 | Own magic/schema, physical records, golden perspective labels |
| P9 | Producer/consumer handshake and G0 | BLOCKED_BY_P8 | Exact counts, framing, legality, results, recovery, quarantine |
| P10 | Official public-build DATAGEN canary | BLOCKED_BY_P9 | Production path proves the exact versioned dialect contract |
| P11 | Leased scale and split audit | BLOCKED_BY_P10 | Unique chunks, exact totals, trajectory-level split evidence |
| P12 | NNUE V2 state/content/topology contract | BLOCKED_BY_P11 | Decoder/scalar parity and fail-closed quantized container |
| P13 | Training reproducibility and local model selection | BLOCKED_BY_P12 | Frozen split, multiple seeds, fixed-work, exact resume |
| P14 | STC/LTC strength and winner ancestry | BLOCKED_BY_P13 | Preregistered official science, no optional stopping |
| P15 | Release draft and owner G15 | BLOCKED_BY_P14 | Dual clean builds, SBOM, licenses, assets reverified |
| P16 | Publication and post-release monitoring | BLOCKED_BY_P15 | Immutable stable tag plus rollback and monitoring receipts |

## Current stop conditions

- No search, evaluation tuning, NNUE, data generation, book, Elo, or campaign
  work before P6.
- No official OpenBench Antichess work before a versioned client/server/referee
  mapping passes the same differential fixtures in the production path.
- No redistribution or release alias for the legacy network while its license
  and exact compatibility remain unresolved.
- Local ASan/UBSan runtimes are unavailable; P6 requires a pinned Linux CI job
  rather than a local sanitizer claim.
- No Fairy-Stockfish implementation commit or file may enter candidate
  ancestry.
