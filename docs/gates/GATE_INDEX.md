# Gate index

Allowed terminal states are `GO_NEXT_PHASE`, `BLOCKED_DISCOVERY`,
`NO_VALID_BASELINE`, `REJECTED_ENGINEERING`, `REJECTED_MODEL`,
`REJECTED_STRENGTH`, `REJECTED_RELEASE`, and `RELEASED_MONITORED`.

This file is a human-readable index. Committed receipts are authoritative and
append-only; a gate transition adds a new receipt or addendum.

| Gate | Scope | Status | Closure evidence |
| --- | --- | --- | --- |
| P0 | Root, repository, worktree, remotes, namespaces, resources | PASS | Public repository created from preserved upstream ancestry; D0 receipt |
| P1 | Primary research and authority dossier | PASS | Pinned Lichess/scalachess/lila sources and explicit negative profiles |
| P2 | Executable dialect, source, reference, referee, evaluator, distribution | IN_PROGRESS | Parser/EP/claim boundaries and referee remain open |
| P3 | Pristine reproducible build and UCI surface | PENDING | Clean release/debug builds, options, network-independent smoke |
| P4 | Differential legal/result/notation correctness | PENDING | Full move sets, terminals, clocks, persistence, special moves |
| P5 | Evaluator and legacy-network boundary | PENDING | Classical baseline plus isolated positive/negative loader receipt |
| P6 | Sanitizers, deterministic bench, CI, baseline manifest/tag | PENDING | No unresolved correctness or asset dependency |
| P7 | Search-hypothesis readiness | BLOCKED_BY_P6 | One hypothesis per branch and preregistered local experiment |
| P8 | Antichess DATAGEN schema and labels | BLOCKED_BY_P7 | Own magic/schema, physical records, golden perspective labels |
| P9 | Producer/consumer handshake and G0 | BLOCKED_BY_P8 | Exact counts, framing, legality, results, recovery, quarantine |
| P10 | Official public-build DATAGEN canary | BLOCKED_BY_P9 | Actual worker/referee path proves the versioned dialect contract |
| P11 | Leased scale and split audit | BLOCKED_BY_P10 | Unique chunks, exact totals, trajectory-level split evidence |
| P12 | NNUE V2 state/content/topology contract | BLOCKED_BY_P11 | Decoder/scalar parity and fail-closed quantized container |
| P13 | Training reproducibility and local model selection | BLOCKED_BY_P12 | Frozen split, multiple seeds, fixed-work, exact resume |
| P14 | STC/LTC strength and winner ancestry | BLOCKED_BY_P13 | Preregistered official science, no optional stopping |
| P15 | Release draft and owner G15 | BLOCKED_BY_P14 | Dual clean builds, SBOM, licenses, assets reverified |
| P16 | Publication and post-release monitoring | BLOCKED_BY_P15 | Immutable stable tag plus rollback/monitor receipts |

## Current stop conditions

- No search, evaluation, pruning, NNUE, book, Elo, or campaign work before P6.
- No official OpenBench Antichess work before a versioned client/server/referee
  mapping passes the same differential fixtures in the production path.
- No redistribution or release alias for the legacy network while its license
  remains unresolved.
